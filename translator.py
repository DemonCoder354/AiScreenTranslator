"""Translation through an OpenAI-compatible server: LM Studio or the Gemini API."""

from __future__ import annotations

import base64
import json
import logging
import re
import threading
import time
from dataclasses import dataclass

import openai

from i18n import tr
from languages import Language, find_language

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text from {src} to {tgt}.\n"
    "Rules:\n"
    "{output}"
    "- Preserve the original formatting: line breaks, empty lines between paragraphs, "
    "lists, numbers and punctuation.\n"
    "- The text comes from OCR and may contain small recognition errors; translate the "
    "intended meaning.\n"
    "- Keep names, URLs, e-mail addresses and code unchanged."
)
AUTO_SOURCE = "the source language (detect it automatically)"
OUTPUT_RULE = "- Output ONLY the translation: no explanations, notes, quotes or the original text.\n"
# With an unknown source the model also names the language: it knows far more
# languages than the local detector, and the window shows it.
OUTPUT_RULE_DETECT = (
    "- Your answer has two parts. Line 1: \"LANG: <code>\", the ISO 639-1 code of the "
    "source language (ISO 639-3 if it has none; zh-TW for Traditional Chinese). Then, from "
    "line 2 on, the full translation, and nothing else: no explanations, notes, quotes or "
    "the original text.\n")
_LANG_LINE_RE = re.compile(r"^[\W_]*lang(?:uage)?[\s*_]*[:=][\s*_`\"']*"
                           r"([A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,4})?)[\W_]*$",
                           re.IGNORECASE)

# A plain line format instead of JSON: about a third fewer tokens to generate,
# and every token costs ~80 ms with a 26B model on a mid-range GPU.
DEFINE_PROMPT = (
    "You are a concise monolingual dictionary, like the dictionary panel of Google Translate.\n"
    "The user sends a word and the text it appears in. The word is in {lang}.\n"
    "Answer ONLY in {lang} (the language of the word itself, never in another "
    "language{except_}), in exactly these {count} lines, without markdown or any other text:\n"
    "lemma: <dictionary form of the word>\n"
    "{translation}"
    "ipa: <IPA pronunciation of the lemma, without slashes or brackets>\n"
    "pos: <short part of speech>\n"
    "definition: <one short sentence: the meaning of the word as used in the text>\n"
    "example: <one short natural example sentence with the word in this meaning, "
    "different from the text>\n"
    "synonyms: <up to 6 common words or phrases that could replace the word in this text, "
    "separated by \"; \". Only real synonyms of this meaning, best first: no antonyms, "
    "no explanations, no made-up words. Fewer is fine; - if there are none>"
)
AUTO_WORD_LANGUAGE = "the same language as the word"
DEFINE_TRANSLATION_LINE = ("translation: <2-4 common general translations of the lemma into "
                           "{target}, regardless of the text, most common first, separated by "
                           "\", \"; fewer if there are no more real equivalents>\n")
MAX_TRANSLATIONS = 4
MAX_SYNONYMS = 6

OCR_PROMPT = (
    "You are a precise OCR engine. Transcribe all readable text in the image exactly as "
    "written, in its original language. Do not translate, explain, summarize or correct it.\n"
    "Rules:\n"
    "- Join the wrapped lines of one paragraph into a single line, and rejoin words "
    "hyphenated at a line end.\n"
    "- Put headings, list items and separate paragraphs on their own lines, with an empty "
    "line between paragraphs.\n"
    "- Keep diacritics, punctuation, numbers and symbols. Write formulas as plain Unicode "
    "text (Δl₀, x², α), never LaTeX, $ signs or Markdown.\n"
    "- Skip page numbers and stray marks that are not text.\n"
    "- Output the text only, without quotes or code fences. If there is no readable text, "
    "output exactly: {no_text}"
)
NO_TEXT = "[NO TEXT]"

IDIOMS_PROMPT = (
    "You find idioms in a text written in {lang}. List every idiom, phrasal verb and fixed "
    "multi-word expression whose meaning differs from the meanings of its separate words.\n"
    "Rules:\n"
    "- Copy each expression exactly as it appears in the text, with the same word forms.\n"
    "- One expression per line, without numbering, quotes or explanations.\n"
    "- Skip ordinary word combinations, names, terms and single words.\n"
    "- If there are none, output exactly: -"
)
MAX_IDIOM_TEXT = 4000  # characters of the text searched for idioms

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_LINE_RE = re.compile(r"^[\s*_#>-]*(lemma|translation|ipa|transcription|pronunciation|pos|"
                      r"part of speech|definition|example|synonyms)[\s*_]*:\s*(.*)$",
                      re.IGNORECASE)
_KEYS = {"lemma": "lemma", "translation": "translation", "ipa": "ipa",
         "transcription": "ipa", "pronunciation": "ipa",
         "pos": "pos", "part of speech": "pos", "definition": "definition",
         "example": "example", "synonyms": "synonyms"}


@dataclass(frozen=True)
class Translation:
    """A translated text.

    Attributes:
        text: The translation.
        source: Source language: the one asked for, or the one the model found
            (None if the model did not say).
    """

    text: str
    source: Language | None


@dataclass(frozen=True)
class WordInfo:
    """Dictionary entry for a clicked word, written in the word's own language.

    Attributes:
        word: The word as clicked.
        lemma: Dictionary (base) form.
        part_of_speech: Short part-of-speech label.
        definition: One-sentence meaning in context.
        synonyms: A few synonyms (may be empty).
        ipa: IPA transcription of the lemma without slashes ("" if unknown).
        example: A short example sentence ("" if none).
        translation: The word translated into the target language ("" if not asked).
    """

    word: str
    lemma: str
    part_of_speech: str
    definition: str
    synonyms: tuple[str, ...]
    ipa: str = ""
    example: str = ""
    translation: str = ""


LOCAL_SERVICE = "LM Studio"


class TranslationError(Exception):
    """Translation failed; the message is user-facing (Russian)."""


class _ModelUnavailable(TranslationError):
    """This model cannot answer now (quota, overload, unknown id): try the next one.

    Attributes:
        cooldown: Seconds to skip the model before trying it again.
    """

    def __init__(self, message: str, cooldown: float) -> None:
        super().__init__(message)
        self.cooldown = cooldown


# Gemini 2.5 models can switch reasoning off completely; newer ones only lower it.
_REASONING_OFF_PREFIXES = ("gemini-2.5",)


class Translator:
    """Translates text with a model served by LM Studio.

    Args:
        base_url: LM Studio server URL, e.g. ``http://localhost:1234/v1``.
        model_name: Model id; empty selects the first model reported by the server.
        temperature: Sampling temperature.
        timeout: Request timeout in seconds.
        disable_reasoning: Ask reasoning models to answer without "thinking" first.
        api_key: API key; LM Studio ignores it, but the client requires one.
        service: Server name used in error messages ("LM Studio", "Gemini API").
        reasoning_effort: Value sent when ``disable_reasoning`` is on: "none" for
            LM Studio, "minimal" for Gemini 3 models that cannot switch it off.
        text_models: Models for translation, in order of
            preference. When one hits its quota or is overloaded, the next one
            answers. Empty: just ``model_name`` (LM Studio).
        vision_models: Models that read screenshots, in the same way; empty
            disables :meth:`transcribe`.
        dictionary_models: Models for :meth:`define`, in the same way; empty means
            ``text_models``.
    """

    def __init__(self, base_url: str, model_name: str = "", temperature: float = 0.2,
                 timeout: float = 60.0, disable_reasoning: bool = True, *,
                 api_key: str = "lm-studio", service: str = LOCAL_SERVICE,
                 reasoning_effort: str = "none", text_models: tuple[str, ...] = (),
                 vision_models: tuple[str, ...] = (),
                 dictionary_models: tuple[str, ...] = ()) -> None:
        self.base_url = base_url
        self.model_name = model_name
        self.temperature = temperature
        self.disable_reasoning = disable_reasoning
        self.service = service
        self.reasoning_effort = reasoning_effort
        self.text_models = tuple(text_models)
        self.vision_models = tuple(vision_models)
        self.dictionary_models = tuple(dictionary_models)
        self.last_model = ""  # model that answered the latest request (for logs)
        self._cooldown_until: dict[str, float] = {}
        self._no_reasoning_param: set[str] = set()  # models that rejected reasoning_effort
        # No retries: an unreachable server or an exhausted quota must be reported quickly.
        self._client = openai.OpenAI(base_url=base_url, api_key=api_key,
                                     timeout=timeout, max_retries=0)
        self._resolved_model: str | None = model_name or None
        self._lock = threading.Lock()

    def translate(self, text: str, source: Language | None, target: Language) -> Translation:
        """Translate ``text`` into ``target``.

        Args:
            text: Text to translate.
            source: Source language, or None to let the model detect it.
            target: Target language.

        Returns:
            The translated text with formatting preserved, and the source language
            (found by the model when ``source`` is None).

        Raises:
            TranslationError: If the server is unreachable, no model is loaded,
                the request times out or the model returns nothing.
        """
        if source is not None and source.code == target.code:
            return Translation(text, source)
        system = SYSTEM_PROMPT.format(
            src=source.english_name if source else AUTO_SOURCE,
            tgt=target.english_name,
            output=OUTPUT_RULE if source else OUTPUT_RULE_DETECT,
        )
        log.info("Translating %d chars %s -> %s", len(text),
                 source.code if source else "auto", target.code)
        raw = self._complete(self._text_candidates(), system, text)
        if source is not None:
            return Translation(raw, source)
        translated, found = _split_language_line(raw)
        log.info("Model says the source is %s", found.code if found else "unknown")
        if not translated.strip():
            # Some models stop after the language line: ask again without it.
            log.warning("Only a language line came back; translating again")
            if found is not None and found.code == target.code:
                return Translation(text, found)
            system = SYSTEM_PROMPT.format(src=found.english_name if found else AUTO_SOURCE,
                                          tgt=target.english_name, output=OUTPUT_RULE)
            translated = self._complete(self._text_candidates(), system, text)
        return Translation(translated, found)

    def define(self, word: str, context: str, language: Language | None,
               target: Language | None = None) -> WordInfo:
        """Explain ``word`` in its own language: short definition and a few synonyms.

        Args:
            word: The clicked word.
            context: Text the word appears in, used to pick the right meaning.
            language: Language of the word, or None to let the model infer it.
            target: Language to translate the word into; None, or the word's own
                language, skips the translation.

        Raises:
            TranslationError: On the same server problems as :meth:`translate`, or
                if the model's answer is not a usable dictionary entry.
        """
        if target is not None and language is not None and target.code == language.code:
            target = None
        system = DEFINE_PROMPT.format(
            lang=language.english_name if language else AUTO_WORD_LANGUAGE,
            count="seven" if target else "six",
            except_=", except the translation line" if target else "",
            translation=DEFINE_TRANSLATION_LINE.format(target=target.english_name)
            if target else "")
        user = f"Word: {word}\nText: {context[:1500]}"
        log.info("Defining %r (%s)", word, language.code if language else "auto")
        models = self.dictionary_models or self._text_candidates()
        return _parse_word_info(word, self._complete(models, system, user))

    def find_idioms(self, text: str, language: Language | None) -> list[str]:
        """Return the idioms and fixed expressions of ``text`` as written there.

        Raises:
            TranslationError: On the same server problems as :meth:`translate`.
        """
        system = IDIOMS_PROMPT.format(
            lang=language.english_name if language else AUTO_WORD_LANGUAGE)
        models = self.dictionary_models or self._text_candidates()
        log.info("Looking for idioms in %d chars", len(text))
        raw = self._complete(models, system, text[:MAX_IDIOM_TEXT], temperature=0.0)
        idioms = []
        for line in raw.splitlines():
            phrase = line.strip().lstrip("-*•0123456789.) ").strip().strip("\"'«»„“”").strip()
            if len(phrase.split()) >= 2 and phrase not in idioms:
                idioms.append(phrase)
        return idioms

    @property
    def vision(self) -> bool:
        """True if some model can read images (enables :meth:`transcribe`)."""
        return bool(self.vision_models)

    def transcribe(self, png: bytes, language: Language | None = None) -> str:
        """Read the text on a PNG screenshot with the model; "" if it has no text.

        Args:
            png: The image, PNG-encoded.
            language: Language chosen by the user, passed as a hint; None = any.

        Raises:
            TranslationError: On server problems, or if the model cannot read images.
        """
        if not self.vision:
            raise TranslationError(tr("err.no_vision", service=self.service))
        hint = f" The text is in {language.english_name}." if language else ""
        content = [
            {"type": "text", "text": "Transcribe the text in this image." + hint},
            {"type": "image_url",
             "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}},
        ]
        log.info("Transcribing a %d KB image", len(png) // 1024)
        text = _strip_fences(self._complete(self.vision_models, OCR_PROMPT.format(no_text=NO_TEXT),
                                            content, temperature=0.0))
        return "" if text.strip() == NO_TEXT else text

    def _text_candidates(self) -> tuple[str, ...]:
        return self.text_models or (self._model(),)

    def _complete(self, models: tuple[str, ...], system: str,
                  user: str | list[dict[str, object]], temperature: float | None = None) -> str:
        """Ask the first available model of ``models``; fall over to the next one.

        A model that ran out of quota or is overloaded is skipped for a while, so
        the following requests go straight to the next model.

        Raises:
            TranslationError: If no model could answer.
        """
        now = time.monotonic()
        ready = [m for m in models if self._cooldown_until.get(m, 0.0) <= now]
        # If every model is cooling down, try them anyway: a limit may have reset.
        order = ready + [m for m in models if m not in ready]
        error: TranslationError | None = None
        for model in order:
            try:
                result = self._complete_once(model, system, user, temperature)
            except _ModelUnavailable as exc:
                self._cooldown_until[model] = time.monotonic() + exc.cooldown
                log.warning("%s unavailable for %.0f s, trying the next model: %s",
                            model, exc.cooldown, exc)
                error = exc
                continue
            self._cooldown_until.pop(model, None)
            self.last_model = model
            log.info("Answered by %s", model)
            return result
        raise error or TranslationError(tr("err.no_models"))

    def _complete_once(self, model: str, system: str, user: str | list[dict[str, object]],
                       temperature: float | None = None) -> str:
        """Run one chat request and return the cleaned answer text.

        Not streamed on purpose: LM Studio adds ~2 s before the first streamed
        token, and the next plain request after a streamed one is slow as well;
        answers are short, so streaming would not make the cloud faster either.

        Raises:
            _ModelUnavailable: If this model is out of quota, overloaded or unknown.
            TranslationError: With a user-facing message for every other problem.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            response = self._create(model, messages, temperature)
        except openai.APITimeoutError as exc:
            raise TranslationError(tr("err.timeout", service=self.service)) from exc
        except openai.APIConnectionError as exc:
            raise TranslationError(self._unreachable_message()) from exc
        except openai.APIStatusError as exc:
            self._resolved_model = self.model_name or None  # re-resolve next time
            message = self._status_message(exc, model)
            cooldown = self._cooldown_for(exc)
            if cooldown:
                raise _ModelUnavailable(message, cooldown) from exc
            raise TranslationError(message) from exc

        content = response.choices[0].message.content if response.choices else None
        result = _THINK_RE.sub("", content or "").strip()
        if not result:
            raise TranslationError(tr("err.empty"))
        return result

    def _create(self, model: str, messages: list[dict[str, object]],  # noqa: ANN202 - SDK type
                temperature: float | None = None, **extra: object):
        """Send the chat request, with model reasoning switched off when enabled.

        Reasoning models (Gemma 4, Qwen 3, ...) otherwise "think" for hundreds of
        tokens before a one-line translation: ~90 s instead of ~3 s in LM Studio.
        If a server rejects ``reasoning_effort``, the request is repeated without it
        and the parameter is not sent again.
        """
        kwargs: dict[str, object] = dict(extra)
        kwargs["temperature"] = self.temperature if temperature is None else temperature
        if self.disable_reasoning and model not in self._no_reasoning_param:
            off = self.service != LOCAL_SERVICE and model.startswith(_REASONING_OFF_PREFIXES)
            kwargs["reasoning_effort"] = "none" if off else self.reasoning_effort
        try:
            return self._client.chat.completions.create(
                model=model, messages=messages, **kwargs)
        except openai.BadRequestError as exc:
            if "reasoning_effort" not in kwargs or "reasoning" not in str(exc).lower():
                raise
            log.warning("%s rejected reasoning_effort, retrying without it: %s", model, exc)
            self._no_reasoning_param.add(model)
            del kwargs["reasoning_effort"]
            return self._client.chat.completions.create(
                model=model, messages=messages, **kwargs)

    def close(self) -> None:
        """Close HTTP connections, aborting a request in progress (safe from any thread)."""
        self._client.close()

    def _model(self) -> str:
        """Return the configured model, or the first model reported by the server."""
        with self._lock:
            if self._resolved_model:
                return self._resolved_model
            try:
                models = list(self._client.models.list(timeout=5.0))
            except openai.APIConnectionError as exc:
                raise TranslationError(self._unreachable_message()) from exc
            except openai.APIError as exc:
                raise TranslationError(tr("err.server", service=self.service, error=exc)) from exc
            llms = [m.id for m in models if "embed" not in m.id.lower()]
            if not llms:
                raise TranslationError(tr("err.lm_no_model"))
            self._resolved_model = llms[0]
            log.info("Using model %s", self._resolved_model)
            return self._resolved_model

    def _unreachable_message(self) -> str:
        if self.service != LOCAL_SERVICE:
            return tr("err.offline", service=self.service)
        return tr("err.lm_offline", url=self.base_url)

    def _cooldown_for(self, exc: openai.APIStatusError) -> float:
        """Seconds to skip a cloud model after this error; 0 if the next model won't help."""
        if self.service == LOCAL_SERVICE:
            return 0.0
        text = str(exc.body or exc.message or "").lower()
        if exc.status_code == 429:
            # A per-day quota stays exhausted for hours; a per-minute one for seconds.
            return 3600.0 if "perday" in text or "per day" in text else 60.0
        if exc.status_code in (500, 502, 503, 504):
            return 30.0  # overloaded ("high demand"), usually short
        if exc.status_code == 404:
            return 3600.0  # unknown or retired model id
        return 0.0

    def _status_message(self, exc: openai.APIStatusError, model: str = "") -> str:
        detail = str(exc.message or exc)
        body = exc.body
        if isinstance(body, list) and body and isinstance(body[0], dict):
            body = body[0]  # Gemini wraps some errors in a list
        if isinstance(body, dict):
            inner = body.get("error", body)
            if isinstance(inner, dict) and inner.get("message"):
                detail = str(inner["message"])
            elif isinstance(inner, str):
                detail = inner
        log.error("%s status %s: %s", self.service, exc.status_code, detail)
        lowered = detail.lower()
        if self.service != LOCAL_SERVICE:
            if exc.status_code in (401, 403) or "api key" in lowered:
                return tr("err.bad_key", service=self.service, detail=detail)
            if exc.status_code in (500, 502, 503, 504):
                return tr("err.overloaded", service=self.service, detail=detail)
            if exc.status_code == 429:
                return tr("err.quota", service=self.service)
            if exc.status_code == 404 or ("model" in lowered and "not found" in lowered):
                return tr("err.model_missing", model=model or self.model_name,
                          service=self.service, detail=detail)
            return tr("err.status", service=self.service, code=exc.status_code, detail=detail)
        if "model" in lowered and ("load" in lowered or "not found" in lowered):
            return tr("err.lm_model", detail=detail)
        return tr("err.status", service=LOCAL_SERVICE, code=exc.status_code, detail=detail)


def _split_language_line(raw: str) -> tuple[str, Language | None]:
    """Split the "LANG: xx" line off a translation; the text is kept whole without one.

    The returned text is empty when the model sent only the language line.
    """
    lines = raw.split("\n")
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is None:
        return raw, None
    match = _LANG_LINE_RE.match(lines[first].strip())
    if not match:
        return raw, None
    return "\n".join(lines[first + 1:]).lstrip("\n"), find_language(match.group(1))


def _strip_fences(text: str) -> str:
    """Remove a Markdown code fence some models wrap plain text in, and inline LaTeX."""
    match = re.fullmatch(r"\s*```[\w-]*\n(.*?)\n?```\s*", text, re.DOTALL)
    text = match.group(1).strip() if match else text.strip()
    return _INLINE_MATH_RE.sub(lambda m: _latex_to_unicode(m.group(1)), text)


# Only $...$ with LaTeX markup inside, so prices such as "$5 or $10" stay intact.
_INLINE_MATH_RE = re.compile(r"\$([^$\n]{0,40}[\\_^][^$\n]{0,40})\$")
_LATEX_SYMBOLS = {
    "Delta": "Δ", "delta": "δ", "alpha": "α", "beta": "β", "gamma": "γ", "lambda": "λ",
    "mu": "μ", "pi": "π", "sigma": "σ", "omega": "ω", "Omega": "Ω", "theta": "θ",
    "rho": "ρ", "varphi": "φ", "phi": "φ", "cdot": "·", "times": "×", "pm": "±",
    "approx": "≈", "leq": "≤", "geq": "≥", "neq": "≠", "infty": "∞", "circ": "°",
}
_SUB = str.maketrans("0123456789+-=()aeoxn", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₙ")
_SUP = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")


def _latex_to_unicode(math: str) -> str:
    r"""Turn simple inline LaTeX such as ``\Delta l_0`` or ``x^{2}`` into ``Δl₀`` / ``x²``."""
    math = re.sub(r"\\([A-Za-z]+)\s*", lambda m: _LATEX_SYMBOLS.get(m.group(1), m.group(1)), math)
    math = re.sub(r"_\{?([0-9a-z+\-=()]+)\}?", lambda m: m.group(1).translate(_SUB), math)
    math = re.sub(r"\^\{?([0-9n+\-=()]+)\}?", lambda m: m.group(1).translate(_SUP), math)
    return math.replace("{", "").replace("}", "")


def _clean_synonyms(word: str, lemma: str, synonyms: list[str]) -> tuple[str, ...]:
    """Drop empty items, templates with gaps, repeats and the word itself; keep at most
    MAX_SYNONYMS."""
    cleaned: list[str] = []
    skip = {word.lower(), lemma.lower(), "-", "—", "–"}
    for item in synonyms:
        item = re.sub(r"\s*\(.*?\)", "", str(item)).strip().strip(".*\"'")  # drop "(notes)"
        if "_" in item or "…" in item or "..." in item:
            continue  # a template with a gap ("llover a _"), not a real synonym
        if item and item.lower() not in skip and item not in cleaned:
            cleaned.append(item)
    return tuple(cleaned[:MAX_SYNONYMS])


def _parse_word_lines(word: str, raw: str) -> WordInfo | None:
    """Parse the ``key: value`` answer; None if it has no such lines."""
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        match = _LINE_RE.match(line)
        if match:
            fields[_KEYS[match.group(1).lower()]] = match.group(2).strip().strip("*").strip()
    if not fields:
        return None
    lemma = fields.get("lemma") or word
    items = re.split(r"\s*;\s*", fields.get("synonyms", ""))
    if len(items) == 1 and "," in items[0]:
        items = items[0].split(",")
    return WordInfo(
        word=word,
        lemma=lemma,
        part_of_speech=fields.get("pos", ""),
        definition=fields.get("definition", ""),
        synonyms=_clean_synonyms(word, lemma, items),
        ipa=_clean_ipa(fields.get("ipa", "")),
        example=fields.get("example", "").strip("\"'«»„“”"),
        translation=_clean_translation(fields.get("translation", "")),
    )


def _parse_word_info(word: str, raw: str) -> WordInfo:
    """Build the final :class:`WordInfo` from the line format, or from JSON as a fallback."""
    info = _parse_word_lines(word, raw)
    if info is not None and info.definition:
        return info
    match = _JSON_RE.search(raw)
    try:
        data = json.loads(match.group(0) if match else raw)
    except ValueError as exc:
        log.warning("Unparsable definition for %r: %r", word, raw[:300])
        raise TranslationError(tr("err.bad_format")) from exc
    if not isinstance(data, dict) or not str(data.get("definition", "")).strip():
        raise TranslationError(tr("err.no_definition"))
    synonyms = data.get("synonyms") or []
    if not isinstance(synonyms, list):
        synonyms = [synonyms]
    lemma = str(data.get("lemma") or word).strip()
    return WordInfo(
        word=word,
        lemma=lemma,
        part_of_speech=str(data.get("part_of_speech") or "").strip(),
        definition=str(data["definition"]).strip(),
        synonyms=_clean_synonyms(word, lemma, synonyms),
        ipa=_clean_ipa(str(data.get("ipa") or "")),
        example=str(data.get("example") or "").strip(),
        translation=_clean_translation(str(data.get("translation") or "")),
    )


def _clean_translation(text: str) -> str:
    """Join up to :data:`MAX_TRANSLATIONS` distinct variants with ", "; "-" means none."""
    variants: list[str] = []
    for item in re.split(r"\s*[,;/]\s*", text):
        item = item.strip().strip("\"'«»„“”").strip()
        if item and item not in ("-", "—") and item.lower() not in map(str.lower, variants):
            variants.append(item)
    return ", ".join(variants[:MAX_TRANSLATIONS])


def _clean_ipa(ipa: str) -> str:
    """Strip the slashes or brackets models often add around IPA; "-" means none."""
    ipa = ipa.strip().strip("/[]").strip()
    return "" if ipa in ("", "-", "—") else ipa
