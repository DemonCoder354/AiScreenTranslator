"""Interface strings in English and Russian; ``tr(key)`` returns the current language's text."""

from __future__ import annotations

UI_LANGUAGES = {"en": "English", "ru": "Русский"}  # code -> name shown in its own language
DEFAULT_UI_LANGUAGE = "en"

_language = DEFAULT_UI_LANGUAGE

# key: (English, Russian)
_STRINGS: dict[str, tuple[str, str]] = {
    # ---------------------------------------------------------------- tray menu
    "menu.capture": ("Translate screen area", "Перевести область"),
    "menu.capture_key": ("Translate screen area ({key})", "Перевести область ({key})"),
    "menu.manual": ("Type text", "Ввести текст"),
    "menu.manual_key": ("Type text ({key})", "Ввести текст ({key})"),
    "menu.provider": ("Translation model", "Модель перевода"),
    "menu.provider_local": ("Local (LM Studio)", "Локальная (LM Studio)"),
    "menu.provider_gemini": ("Cloud (Gemini API)", "Облако (Gemini API)"),
    "menu.source": ("Default source language", "Язык оригинала по умолчанию"),
    "menu.target": ("Default target language", "Целевой язык по умолчанию"),
    "menu.settings": ("Settings…", "Настройки…"),
    "menu.api_key": ("Gemini API key…", "Ключ Gemini API…"),
    "menu.data_folder": ("Settings and log folder", "Папка настроек и журнала"),
    "menu.quit": ("Quit", "Выход"),
    "lang.auto": ("Auto-detect", "Автоопределение"),
    "menu.all_languages": ("All languages", "Все языки"),
    "lang.top": ("Most spoken", "Самые распространённые"),
    "tray.tooltip": ("ScreenTranslator: {keys}, into {target}, {engine}",
                     "ScreenTranslator: {keys}, перевод на {target}, {engine}"),
    "tray.no_keys": ("no hotkeys", "клавиши не назначены"),
    "notify.key_saved": ("Key saved. You can translate now.", "Ключ сохранён. Можно переводить."),
    "notify.hotkey_failed": (
        "{errors}.\nThe program may already be running. Change the hotkeys in config.json "
        "or use the tray menu.",
        "{errors}.\nВозможно, программа уже запущена. Измените клавиши в config.json "
        "или используйте меню в трее."),
    "notify.running": (
        "Running in the background. {capture}: translate a screen area, {manual}: type text.",
        "Работает в фоне. {capture}: перевести область экрана, {manual}: ввести текст."),
    "status.translating": ("Translating…", "Перевожу…"),
    "status.recognizing": ("Recognizing text…", "Распознаю текст…"),
    "capture.hint": ("Select an area with text   ·   Esc: cancel",
                     "Выделите область с текстом   ·   Esc: отмена"),

    # ------------------------------------------------------------ result window
    "win.target_tip": ("Target language", "Язык перевода"),
    "win.close_tip": ("Quit the translator (Esc only hides the window)",
                      "Выключить переводчик (Esc только прячет окно)"),
    "win.settings_tip": ("Settings", "Настройки"),
    "win.translate": ("Translate  ·  Ctrl+Enter", "Перевести  ·  Ctrl+Enter"),
    "win.copy_translation": ("Copy translation", "Копировать перевод"),
    "win.copy_original": ("Copy original", "Копировать оригинал"),
    "win.copied": ("✓  Copied", "✓  Скопировано"),
    "win.caption_original": ("ORIGINAL", "ОРИГИНАЛ"),
    "win.caption_text": ("TEXT", "ТЕКСТ"),
    "win.caption_translation": ("TRANSLATION", "ПЕРЕВОД"),
    "win.manual_prompt": ("Type or paste text and press Ctrl+Enter.",
                          "Введите или вставьте текст и нажмите Ctrl+Enter."),
    "win.placeholder": ("Type or paste text…", "Введите или вставьте текст…"),
    "win.hint_manual": ("Double-click a word: dictionary  ·  Esc",
                        "Двойной клик по слову: словарь  ·  Esc"),
    "win.hint_capture": ("Click a word: dictionary  ·  Esc", "Клик по слову: словарь  ·  Esc"),
    "win.same_language": ("The text is already in the target language: the original is shown.",
                          "Текст уже на целевом языке: показан оригинал."),
    "win.unsure_language": (
        "The language was not detected reliably, so the model detected it itself. "
        "You can choose it in the list on the left.",
        "Язык не определён уверенно, модель определила его сама. "
        "Его можно выбрать в списке слева."),
    "win.source_manual_tip": ("Source language (chosen manually)",
                              "Язык оригинала (выбран вручную)"),
    "win.auto_item": ("Auto  ·  {label}", "Авто  ·  {label}"),
    "win.source_found_tip": ("Source language detected automatically: {name}",
                             "Язык оригинала определён автоматически: {name}"),
    "win.source_auto_tip": ("Source language is detected automatically",
                            "Язык оригинала определяется автоматически"),

    # ---------------------------------------------------------- dictionary card
    "popup.title": ("DICTIONARY · {lang}", "СЛОВАРЬ · {lang}"),
    "popup.close_tip": ("Close (Esc)", "Закрыть (Esc)"),
    "popup.volume_tip": ("Pronunciation volume", "Громкость озвучки"),
    "popup.speak_word": ("Pronounce the word", "Произнести слово"),
    "popup.speak_example": ("Pronounce the example", "Произнести пример"),
    "popup.synonyms": ("SYNONYMS", "СИНОНИМЫ"),
    "popup.translation_tip": ("Translation of the word", "Перевод слова"),
    "popup.looking_up": ("Looking up…", "Ищу значение…"),
    "popup.example": ("“{text}”", "«{text}»"),

    # ----------------------------------------------------------------- settings
    "settings.title": ("ScreenTranslator settings", "Настройки ScreenTranslator"),
    "settings.volume": ("Pronunciation volume", "Громкость озвучки"),
    "settings.language": ("Interface language", "Язык интерфейса"),
    "settings.api_key": ("Gemini API key…", "Ключ Gemini API…"),
    "settings.close": ("Close", "Закрыть"),
    "settings.tab_general": ("General", "Основные"),
    "settings.tab_models": ("Models", "Модели"),
    "models.step": ("Step", "Шаг"),
    "models.step_text": ("Translation", "Перевод"),
    "models.step_dictionary": ("Dictionary and idioms", "Словарь и идиомы"),
    "models.step_vision": ("Reading images", "Чтение картинок"),
    "models.hint": (
        "Models are tried from the top: when one is out of quota or overloaded, the next one "
        "answers. Drag a model or use the arrows to change the order. Used in cloud mode "
        "(Gemini API).",
        "Модели пробуются сверху вниз: если у модели кончился лимит или она перегружена, "
        "отвечает следующая. Порядок меняется перетаскиванием или стрелками. Работает в "
        "облачном режиме (Gemini API)."),
    "models.up": ("Move up", "Выше"),
    "models.down": ("Move down", "Ниже"),
    "models.remove": ("Remove", "Удалить"),
    "models.add": ("Add", "Добавить"),
    "models.add_placeholder": ("Model from AI Studio or your own model ID",
                               "Модель из AI Studio или свой ID модели"),
    "models.refresh": ("Refresh list", "Обновить список"),
    "models.reset": ("Default order", "По умолчанию"),
    "models.loading": ("Loading models from AI Studio…", "Загружаю модели из AI Studio…"),
    "models.loaded": ("Models available with your key: {count}",
                      "Доступно моделей по вашему ключу: {count}"),
    "models.load_failed": ("Could not load the model list: {error}",
                           "Не удалось загрузить список моделей: {error}"),
    "models.no_key": ("Enter the Gemini API key to load the model list.",
                      "Введите ключ Gemini API, чтобы загрузить список моделей."),
    "models.duplicate": ("This model is already in the list.", "Эта модель уже в списке."),
    "models.last": ("At least one model must stay in the list.",
                    "В списке должна остаться хотя бы одна модель."),

    # ------------------------------------------------------------------ API key
    "key.title": ("ScreenTranslator: Gemini API key", "ScreenTranslator: ключ Gemini API"),
    "key.intro": (
        "Translation needs a free Google Gemini API key.<br><br>"
        "1. Open <a href='{url}' style='color:{color}'>aistudio.google.com/apikey</a> "
        "and sign in with a Google account.<br>"
        "2. Click <b>Create API key</b> and copy the key.<br>"
        "3. Paste it here and click Save.",
        "Для перевода нужен бесплатный ключ Google Gemini API.<br><br>"
        "1. Откройте <a href='{url}' style='color:{color}'>aistudio.google.com/apikey</a> "
        "и войдите в Google-аккаунт.<br>"
        "2. Нажмите <b>Create API key</b> и скопируйте ключ.<br>"
        "3. Вставьте его сюда и нажмите «Сохранить»."),
    "key.placeholder": ("Gemini API key", "Ключ Gemini API"),
    "key.show": ("Show", "Показать"),
    "key.note": (
        "The key is stored only on this computer, in the {variable} environment variable "
        "of your Windows account. Do not share it with anyone.",
        "Ключ хранится только на этом компьютере, в переменной среды {variable} "
        "вашей учётной записи Windows. Никому его не передавайте."),
    "key.save": ("Save", "Сохранить"),
    "key.cancel": ("Cancel", "Отмена"),
    "key.invalid": ("This does not look like a key: copy it in full.",
                    "Это не похоже на ключ: скопируйте его целиком."),
    "key.save_failed": ("Cannot save the key: {error}", "Не удалось сохранить ключ: {error}"),

    # ------------------------------------------------------------ pronunciation
    "speech.no_voice": (
        "No Windows voice for this language. Add one in Settings → Time & language → "
        "Speech → Add voices, or choose the cloud (Gemini) in the tray menu.",
        "Нет голоса Windows для этого языка. Добавьте его: Параметры → Время и язык → "
        "Речь → Добавить голоса, или выберите облако (Gemini) в меню трея."),
    "speech.timeout": ("Gemini did not answer in time (pronunciation).",
                       "Gemini не ответил вовремя (озвучка)."),
    "speech.no_audio": ("Gemini returned no audio.", "Gemini не вернул звук."),
    "speech.bad_key": ("Gemini API rejected the key (tray menu → Gemini API key…).",
                       "Gemini API не принял ключ (меню трея → Ключ Gemini API…)."),
    "speech.quota": ("Gemini pronunciation limit reached. Try again later.",
                     "Исчерпан лимит озвучки Gemini. Попробуйте позже."),
    "speech.model": ("Pronunciation model “{model}” is unavailable (gemini_speech_model).",
                     "Модель озвучки «{model}» недоступна (gemini_speech_model)."),
    "speech.other": ("Gemini pronunciation: {reason}", "Озвучка Gemini: {reason}"),
    "speech.offline": ("No connection to Gemini for pronunciation. Check the internet.",
                       "Нет связи с Gemini для озвучки. Проверьте интернет."),
    "speech.cloud_only": ("Gemini pronunciation works when the cloud is selected in the tray menu.",
                          "Озвучка Gemini работает, когда в меню трея выбрано облако."),
    "speech.no_key": ("Gemini API key not found (tray menu → Gemini API key…).",
                      "Не найден ключ Gemini API (меню трея → Ключ Gemini API…)."),
    "speech.no_device": ("Cannot open the audio device.", "Не удалось открыть звуковое устройство."),

    # ------------------------------------------------------------------- errors
    "err.no_translator": ("The translator is not initialized.", "Переводчик не инициализирован."),
    "err.no_ocr": ("OCR is not initialized.", "OCR не инициализирован."),
    "err.no_text": ("No text recognized. Try selecting a larger area or one with more contrast.",
                    "Текст не распознан. Попробуйте выделить область крупнее "
                    "или с более контрастным текстом."),
    "err.unexpected": ("Unexpected error, details in logs/app.log (tray menu → Settings and "
                       "log folder).",
                       "Непредвиденная ошибка, подробности в logs/app.log (меню трея → Папка "
                       "настроек и журнала)."),
    "err.no_key": (
        "Gemini API key not found: the {variable} environment variable is not set.\n"
        "Enter the key in the tray menu → Gemini API key…, or switch to the local model.",
        "Не найден ключ Gemini API: переменная окружения {variable} не задана.\n"
        "Введите ключ в меню трея → Ключ Gemini API…, или переключитесь на локальную модель."),
    "err.no_vision": ("{service}: the model cannot read images.",
                      "{service}: модель не умеет читать картинки."),
    "err.no_models": ("No models available.", "Нет доступных моделей."),
    "err.timeout": (
        "{service} did not answer in time. The model may be too slow or the text too long "
        "(request_timeout in config.json).",
        "{service} не ответил вовремя. Модель может быть слишком медленной "
        "или текст слишком длинный (request_timeout в config.json)."),
    "err.empty": ("The model returned an empty answer.", "Модель вернула пустой ответ."),
    "err.server": ("{service} returned an error: {error}", "{service} вернул ошибку: {error}"),
    "err.lm_no_model": ("No model is loaded in LM Studio.\n"
                        "Load a model on the Developer / My Models tab.",
                        "В LM Studio не загружена ни одна модель.\n"
                        "Загрузите модель на вкладке Developer / My Models."),
    "err.offline": ("No connection to {service}. Check your internet connection.",
                    "Нет связи с {service}. Проверьте подключение к интернету."),
    "err.lm_offline": ("No connection to LM Studio ({url}).\nStart LM Studio, load a model "
                       "and start the server (Developer → Start Server).",
                       "Нет связи с LM Studio ({url}).\nЗапустите LM Studio, загрузите модель "
                       "и включите сервер (Developer → Start Server)."),
    "err.bad_key": ("{service} rejected the key. Check it in the tray menu → Gemini API key…\n"
                    "Details: {detail}",
                    "{service} не принял ключ. Проверьте его: меню трея → Ключ Gemini API…\n"
                    "Подробности: {detail}"),
    "err.overloaded": ("{service} models are overloaded right now. Try again in a minute.\n"
                       "Details: {detail}",
                       "Модели {service} сейчас перегружены. Попробуйте через минуту.\n"
                       "Подробности: {detail}"),
    "err.quota": (
        "The free {service} request limit is used up for all models in the list. Wait a "
        "minute (the daily limit resets at midnight Pacific time) or switch to the local "
        "model in the tray menu.",
        "Исчерпан лимит бесплатных запросов {service} у всех моделей из списка. Подождите "
        "минуту (дневной лимит обновляется в полночь по тихоокеанскому времени, около 9:00 "
        "по Центральной Европе) или переключитесь на локальную модель в меню трея."),
    "err.model_missing": ("Model “{model}” was not found in {service}. Check the gemini_* model "
                          "lists in config.json.\nDetails: {detail}",
                          "Модель «{model}» не найдена в {service}. Проверьте списки моделей "
                          "gemini_* в config.json.\nПодробности: {detail}"),
    "err.status": ("{service} returned error {code}: {detail}",
                   "{service} вернул ошибку {code}: {detail}"),
    "err.lm_model": ("The model is not loaded in LM Studio or its name is wrong.\n"
                     "Details: {detail}",
                     "Модель не загружена в LM Studio или имя модели неверное.\n"
                     "Подробности: {detail}"),
    "err.bad_format": ("The model answered in the wrong format.",
                       "Модель вернула ответ не в том формате."),
    "err.no_definition": ("The model gave no definition.", "Модель не дала определения."),
    "err.tesseract_missing": ("Tesseract not found: {path}\n"
                              "Install Tesseract or set tesseract_path in config.json.",
                              "Tesseract не найден: {path}\n"
                              "Установите Tesseract или укажите путь в config.json "
                              "(tesseract_path)."),
    "err.tessdata_missing": ("tessdata folder not found: {path}",
                             "Папка tessdata не найдена: {path}"),
    "err.tesseract_run": ("Cannot run Tesseract. Check tesseract_path.",
                          "Не удалось запустить Tesseract. Проверьте tesseract_path."),
    "err.tesseract": ("Tesseract error: {error}", "Ошибка Tesseract: {error}"),
    "hk.empty_part": ("Empty part in the hotkey {text}", "Пустая часть в сочетании клавиш {text}"),
    "hk.many_keys": ("Several main keys in the hotkey {text}",
                     "Несколько основных клавиш в сочетании {text}"),
    "hk.unknown": ("Unknown key {part} in {text}", "Неизвестная клавиша {part} в {text}"),
    "hk.no_main": ("No main key in the hotkey {text}", "В сочетании нет основной клавиши: {text}"),
    "hk.taken": ("The hotkey {hotkey} is already used by another program",
                 "Сочетание {hotkey} уже занято другой программой"),
}


def set_language(code: str) -> None:
    """Switch the interface language; unknown codes fall back to English."""
    global _language
    _language = code if code in UI_LANGUAGES else DEFAULT_UI_LANGUAGE


def language() -> str:
    """Current interface language code."""
    return _language


def tr(key: str, /, **values: object) -> str:
    """Text for ``key`` in the current language, with ``{placeholders}`` filled in.

    ``key`` is positional-only, so a placeholder may also be called ``{key}``.
    """
    english, russian = _STRINGS[key]
    text = russian if _language == "ru" else english
    return text.format(**values) if values else text
