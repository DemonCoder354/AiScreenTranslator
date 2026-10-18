"""Registry of supported languages shared by OCR, detection, translation and UI.

Every national language of the world's countries and the other languages with
more than about 100,000 speakers that the cloud models translate; dialects and
regional variants are not listed separately.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    """A supported language.

    Attributes:
        code: ISO 639-1 code, or ISO 639-3 where there is none (e.g. ``"pl"``, ``"ceb"``).
        english_name: Name used inside LLM prompts and in the English interface.
        native_name: Name of the language in the language itself.
        russian_name: Name in the Russian interface.
        tesseract: Tesseract traineddata code; "" if Tesseract cannot read it.
        lingua: Name of the ``lingua.Language`` enum member; "" if lingua cannot detect it.
    """

    code: str
    english_name: str
    native_name: str
    russian_name: str
    tesseract: str = ""
    lingua: str = ""

    @property
    def label(self) -> str:
        """Short upper-case label (e.g. ``"PL"``)."""
        return self.code.upper()

    def name(self, ui_language: str) -> str:
        """Name of the language in the interface language ``ui_language``."""
        return self.russian_name if ui_language == "ru" else self.english_name

    def display_name(self, ui_language: str) -> str:
        """``"German · Deutsch"``; just the name when both spellings are the same."""
        name = self.name(ui_language)
        if name.casefold() == self.native_name.casefold():
            return name
        return f"{name} · {self.native_name}"


def _lang(code: str, english: str, native: str, russian: str,
          tesseract: str = "", lingua: str = "") -> Language:
    return Language(code, english, native, russian, tesseract, lingua)


LANGUAGES: tuple[Language, ...] = (
    _lang("ab", "Abkhaz", "Аԥсуа бызшәа", "Абхазский"),
    _lang("ace", "Acehnese", "Bahsa Acèh", "Ачехский"),
    _lang("aa", "Afar", "Qafaraf", "Афарский"),
    _lang("af", "Afrikaans", "Afrikaans", "Африкаанс", "afr", "AFRIKAANS"),
    _lang("ak", "Akan (Twi)", "Akan", "Акан (тви)"),
    _lang("sq", "Albanian", "Shqip", "Албанский", "sqi", "ALBANIAN"),
    _lang("am", "Amharic", "አማርኛ", "Амхарский", "amh"),
    _lang("ar", "Arabic", "العربية", "Арабский", "ara", "ARABIC"),
    _lang("hy", "Armenian", "Հայերեն", "Армянский", "hye", "ARMENIAN"),
    _lang("as", "Assamese", "অসমীয়া", "Ассамский", "asm"),
    _lang("ast", "Asturian", "Asturianu", "Астурийский"),
    _lang("av", "Avar", "Авар мацӀ", "Аварский"),
    _lang("ay", "Aymara", "Aymar aru", "Аймара"),
    _lang("az", "Azerbaijani", "Azərbaycan dili", "Азербайджанский", "aze", "AZERBAIJANI"),
    _lang("ban", "Balinese", "Basa Bali", "Балийский"),
    _lang("bal", "Balochi", "بلوچی", "Белуджский"),
    _lang("bm", "Bambara", "Bamanankan", "Бамбара"),
    _lang("ba", "Bashkir", "Башҡорт теле", "Башкирский"),
    _lang("eu", "Basque", "Euskara", "Баскский", "eus", "BASQUE"),
    _lang("bbc", "Batak Toba", "Hata Batak Toba", "Батакский (тоба)"),
    _lang("be", "Belarusian", "Беларуская", "Белорусский", "bel", "BELARUSIAN"),
    _lang("bem", "Bemba", "Ichibemba", "Бемба"),
    _lang("bn", "Bengali", "বাংলা", "Бенгальский", "ben", "BENGALI"),
    _lang("bho", "Bhojpuri", "भोजपुरी", "Бходжпури"),
    _lang("bik", "Bikol", "Bikol", "Бикольский"),
    _lang("bi", "Bislama", "Bislama", "Бислама"),
    _lang("brx", "Bodo", "बड़ो", "Бодо"),
    _lang("bs", "Bosnian", "Bosanski", "Боснийский", "bos", "BOSNIAN"),
    _lang("br", "Breton", "Brezhoneg", "Бретонский", "bre"),
    _lang("bug", "Buginese", "Basa Ugi", "Бугийский"),
    _lang("bg", "Bulgarian", "Български", "Болгарский", "bul", "BULGARIAN"),
    _lang("my", "Burmese", "မြန်မာ", "Бирманский", "mya"),
    _lang("bua", "Buryat", "Буряад хэлэн", "Бурятский"),
    _lang("kea", "Cape Verdean Creole", "Kriolu", "Кабувердиану"),
    _lang("ca", "Catalan", "Català", "Каталанский", "cat", "CATALAN"),
    _lang("ceb", "Cebuano", "Cebuano", "Себуанский", "ceb"),
    _lang("ce", "Chechen", "Нохчийн мотт", "Чеченский"),
    _lang("ny", "Chichewa", "Chichewa", "Чичева (ньянджа)"),
    _lang("zh", "Chinese (Simplified)", "简体中文", "Китайский (упрощённый)", "chi_sim", "CHINESE"),
    _lang("zh-tw", "Chinese (Traditional)", "繁體中文", "Китайский (традиционный)", "chi_tra"),
    _lang("cv", "Chuvash", "Чӑвашла", "Чувашский"),
    _lang("zdj", "Comorian", "Shikomori", "Коморский"),
    _lang("co", "Corsican", "Corsu", "Корсиканский", "cos"),
    _lang("crh", "Crimean Tatar", "Qırımtatarca", "Крымскотатарский"),
    _lang("hr", "Croatian", "Hrvatski", "Хорватский", "hrv", "CROATIAN"),
    _lang("cs", "Czech", "Čeština", "Чешский", "ces", "CZECH"),
    _lang("dag", "Dagbani", "Dagbanli", "Дагбани"),
    _lang("da", "Danish", "Dansk", "Датский", "dan", "DANISH"),
    _lang("dv", "Dhivehi", "ދިވެހި", "Мальдивский (дивехи)", "div"),
    _lang("doi", "Dogri", "डोगरी", "Догри"),
    _lang("nl", "Dutch", "Nederlands", "Нидерландский", "nld", "DUTCH"),
    _lang("dyu", "Dyula", "Julakan", "Дьюла"),
    _lang("dz", "Dzongkha", "རྫོང་ཁ", "Дзонг-кэ", "dzo"),
    _lang("en", "English", "English", "Английский", "eng", "ENGLISH"),
    _lang("eo", "Esperanto", "Esperanto", "Эсперанто", "epo", "ESPERANTO"),
    _lang("et", "Estonian", "Eesti", "Эстонский", "est", "ESTONIAN"),
    _lang("ee", "Ewe", "Eʋegbe", "Эве"),
    _lang("fo", "Faroese", "Føroyskt", "Фарерский", "fao"),
    _lang("fj", "Fijian", "Vosa Vakaviti", "Фиджийский"),
    _lang("tl", "Filipino", "Filipino", "Филиппинский (тагальский)", "fil", "TAGALOG"),
    _lang("fi", "Finnish", "Suomi", "Финский", "fin", "FINNISH"),
    _lang("fon", "Fon", "Fɔngbè", "Фон"),
    _lang("fr", "French", "Français", "Французский", "fra", "FRENCH"),
    _lang("fy", "Frisian", "Frysk", "Западнофризский", "fry"),
    _lang("ff", "Fula", "Fulfulde", "Фула"),
    _lang("gaa", "Ga", "Gã", "Га"),
    _lang("gl", "Galician", "Galego", "Галисийский", "glg"),
    _lang("lg", "Ganda", "Luganda", "Луганда", "", "GANDA"),
    _lang("ka", "Georgian", "ქართული", "Грузинский", "kat", "GEORGIAN"),
    _lang("de", "German", "Deutsch", "Немецкий", "deu", "GERMAN"),
    _lang("el", "Greek", "Ελληνικά", "Греческий", "ell", "GREEK"),
    _lang("kl", "Greenlandic", "Kalaallisut", "Гренландский"),
    _lang("gn", "Guarani", "Avañeʼẽ", "Гуарани"),
    _lang("gu", "Gujarati", "ગુજરાતી", "Гуджарати", "guj", "GUJARATI"),
    _lang("ht", "Haitian Creole", "Kreyòl ayisyen", "Гаитянский креольский", "hat"),
    _lang("ha", "Hausa", "Hausa", "Хауса"),
    _lang("he", "Hebrew", "עברית", "Иврит", "heb", "HEBREW"),
    _lang("hil", "Hiligaynon", "Hiligaynon", "Хилигайнон"),
    _lang("hi", "Hindi", "हिन्दी", "Хинди", "hin", "HINDI"),
    _lang("hmn", "Hmong", "Hmoob", "Хмонг"),
    _lang("hu", "Hungarian", "Magyar", "Венгерский", "hun", "HUNGARIAN"),
    _lang("iba", "Iban", "Jaku Iban", "Ибанский"),
    _lang("is", "Icelandic", "Íslenska", "Исландский", "isl", "ICELANDIC"),
    _lang("ig", "Igbo", "Igbo", "Игбо"),
    _lang("ilo", "Ilocano", "Ilokano", "Илоканский"),
    _lang("id", "Indonesian", "Bahasa Indonesia", "Индонезийский", "ind", "INDONESIAN"),
    _lang("iu", "Inuktitut", "ᐃᓄᒃᑎᑐᑦ", "Инуктитут", "iku"),
    _lang("ga", "Irish", "Gaeilge", "Ирландский", "gle", "IRISH"),
    _lang("it", "Italian", "Italiano", "Итальянский", "ita", "ITALIAN"),
    _lang("ja", "Japanese", "日本語", "Японский", "jpn", "JAPANESE"),
    _lang("jv", "Javanese", "Basa Jawa", "Яванский", "jav"),
    _lang("kbd", "Kabardian", "Адыгэбзэ", "Кабардино-черкесский"),
    _lang("kab", "Kabyle", "Taqbaylit", "Кабильский"),
    _lang("kn", "Kannada", "ಕನ್ನಡ", "Каннада", "kan"),
    _lang("pam", "Kapampangan", "Kapampangan", "Пампанганский"),
    _lang("kaa", "Karakalpak", "Qaraqalpaqsha", "Каракалпакский"),
    _lang("ksw", "Karen", "ကညီကျိာ်", "Каренский"),
    _lang("ks", "Kashmiri", "کٲشُر", "Кашмири"),
    _lang("kk", "Kazakh", "Қазақ тілі", "Казахский", "kaz", "KAZAKH"),
    _lang("km", "Khmer", "ខ្មែរ", "Кхмерский", "khm"),
    _lang("ki", "Kikuyu", "Gĩkũyũ", "Кикуйю"),
    _lang("rw", "Kinyarwanda", "Ikinyarwanda", "Руанда (киньяруанда)"),
    _lang("gil", "Kiribati", "Taetae ni Kiribati", "Кирибати"),
    _lang("rn", "Kirundi", "Ikirundi", "Рунди"),
    _lang("kv", "Komi", "Коми кыв", "Коми"),
    _lang("kg", "Kongo", "Kikongo", "Конго"),
    _lang("kok", "Konkani", "कोंकणी", "Конкани"),
    _lang("ko", "Korean", "한국어", "Корейский", "kor", "KOREAN"),
    _lang("kri", "Krio", "Krio", "Крио"),
    _lang("ku", "Kurdish (Kurmanji)", "Kurdî", "Курдский (курманджи)", "kmr"),
    _lang("ckb", "Kurdish (Sorani)", "کوردی", "Курдский (сорани)"),
    _lang("ky", "Kyrgyz", "Кыргызча", "Киргизский", "kir"),
    _lang("lo", "Lao", "ລາວ", "Лаосский", "lao"),
    _lang("la", "Latin", "Latina", "Латинский", "lat", "LATIN"),
    _lang("lv", "Latvian", "Latviešu", "Латышский", "lav", "LATVIAN"),
    _lang("ln", "Lingala", "Lingála", "Лингала"),
    _lang("lt", "Lithuanian", "Lietuvių", "Литовский", "lit", "LITHUANIAN"),
    _lang("lua", "Luba-Kasai", "Tshiluba", "Луба-касаи"),
    _lang("luo", "Luo", "Dholuo", "Луо"),
    _lang("lb", "Luxembourgish", "Lëtzebuergesch", "Люксембургский", "ltz"),
    _lang("mk", "Macedonian", "Македонски", "Македонский", "mkd", "MACEDONIAN"),
    _lang("mad", "Madurese", "Basa Madhura", "Мадурский"),
    _lang("mai", "Maithili", "मैथिली", "Майтхили"),
    _lang("vmw", "Makhuwa", "Emakhuwa", "Макуа"),
    _lang("mg", "Malagasy", "Malagasy", "Малагасийский"),
    _lang("ms", "Malay", "Bahasa Melayu", "Малайский", "msa", "MALAY"),
    _lang("ml", "Malayalam", "മലയാളം", "Малаялам", "mal"),
    _lang("mt", "Maltese", "Malti", "Мальтийский", "mlt"),
    _lang("mnk", "Mandinka", "Mandinka", "Мандинка"),
    _lang("mi", "Maori", "Te Reo Māori", "Маори", "mri", "MAORI"),
    _lang("arn", "Mapudungun", "Mapudungun", "Мапудунгун"),
    _lang("mr", "Marathi", "मराठी", "Маратхи", "mar", "MARATHI"),
    _lang("chm", "Mari", "Марий йылме", "Марийский"),
    _lang("mh", "Marshallese", "Kajin M̧ajeļ", "Маршалльский"),
    _lang("mfe", "Mauritian Creole", "Kreol Morisien", "Маврикийский креольский"),
    _lang("mni", "Meitei (Manipuri)", "ꯃꯩꯇꯩꯂꯣꯟ", "Манипури (мейтей)"),
    _lang("men", "Mende", "Mɛnde", "Менде"),
    _lang("min", "Minangkabau", "Baso Minangkabau", "Минангкабау"),
    _lang("lus", "Mizo", "Mizo ṭawng", "Мизо"),
    _lang("mn", "Mongolian", "Монгол", "Монгольский", "mon", "MONGOLIAN"),
    _lang("mos", "Mooré", "Mooré", "Мооре"),
    _lang("nah", "Nahuatl", "Nāhuatl", "Науатль"),
    _lang("na", "Nauruan", "Dorerin Naoero", "Науруанский"),
    _lang("nv", "Navajo", "Diné bizaad", "Навахо"),
    _lang("nd", "Ndebele (Northern)", "isiNdebele", "Северный ндебеле"),
    _lang("nr", "Ndebele (Southern)", "isiNdebele seSewula", "Южный ндебеле"),
    _lang("ng", "Ndonga (Oshiwambo)", "Oshindonga", "Ндонга (овамбо)"),
    _lang("ne", "Nepali", "नेपाली", "Непальский", "nep"),
    _lang("new", "Newari", "नेपाल भाषा", "Неварский"),
    _lang("nso", "Northern Sotho", "Sesotho sa Leboa", "Северный сото (сепеди)"),
    _lang("no", "Norwegian", "Norsk", "Норвежский", "nor", "BOKMAL"),
    _lang("oc", "Occitan", "Occitan", "Окситанский", "oci"),
    _lang("or", "Odia", "ଓଡ଼ିଆ", "Ория", "ori"),
    _lang("om", "Oromo", "Afaan Oromoo", "Оромо"),
    _lang("os", "Ossetian", "Ирон æвзаг", "Осетинский"),
    _lang("pau", "Palauan", "Tekoi er a Belau", "Палау"),
    _lang("pag", "Pangasinan", "Salitan Pangasinan", "Пангасинанский"),
    _lang("pap", "Papiamento", "Papiamentu", "Папьяменто"),
    _lang("ps", "Pashto", "پښتو", "Пушту", "pus"),
    _lang("fa", "Persian", "فارسی", "Персидский", "fas", "PERSIAN"),
    _lang("pis", "Pijin", "Pijin", "Соломонский пиджин"),
    _lang("pl", "Polish", "Polski", "Польский", "pol", "POLISH"),
    _lang("pt", "Portuguese", "Português", "Португальский", "por", "PORTUGUESE"),
    _lang("pa", "Punjabi", "ਪੰਜਾਬੀ", "Панджаби", "pan", "PUNJABI"),
    _lang("kek", "Q'eqchi'", "Qʼeqchiʼ", "Кекчи"),
    _lang("qu", "Quechua", "Runa Simi", "Кечуа", "que"),
    _lang("quc", "K'iche'", "Kʼicheʼ", "Киче"),
    _lang("rom", "Romani", "Romani čhib", "Цыганский (романи)"),
    _lang("ro", "Romanian", "Română", "Румынский", "ron", "ROMANIAN"),
    _lang("rm", "Romansh", "Rumantsch", "Романшский"),
    _lang("ru", "Russian", "Русский", "Русский", "rus", "RUSSIAN"),
    _lang("sah", "Sakha (Yakut)", "Саха тыла", "Якутский"),
    _lang("sm", "Samoan", "Gagana Sāmoa", "Самоанский"),
    _lang("sg", "Sango", "Sängö", "Санго"),
    _lang("sa", "Sanskrit", "संस्कृतम्", "Санскрит", "san"),
    _lang("sat", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ", "Сантали"),
    _lang("sc", "Sardinian", "Sardu", "Сардинский"),
    _lang("gd", "Scottish Gaelic", "Gàidhlig", "Шотландский гэльский", "gla"),
    _lang("sr", "Serbian", "Српски", "Сербский", "srp", "SERBIAN"),
    _lang("st", "Sesotho", "Sesotho", "Сесото", "", "SOTHO"),
    _lang("crs", "Seychellois Creole", "Kreol Seselwa", "Сейшельский креольский"),
    _lang("shn", "Shan", "တႆး", "Шанский"),
    _lang("sn", "Shona", "ChiShona", "Шона", "", "SHONA"),
    _lang("sid", "Sidamo", "Sidaamu Afoo", "Сидамо"),
    _lang("sd", "Sindhi", "سنڌي", "Синдхи", "snd"),
    _lang("si", "Sinhala", "සිංහල", "Сингальский", "sin"),
    _lang("sk", "Slovak", "Slovenčina", "Словацкий", "slk", "SLOVAK"),
    _lang("sl", "Slovenian", "Slovenščina", "Словенский", "slv", "SLOVENE"),
    _lang("so", "Somali", "Soomaali", "Сомали", "", "SOMALI"),
    _lang("snk", "Soninke", "Sooninkanxanne", "Сонинке"),
    _lang("es", "Spanish", "Español", "Испанский", "spa", "SPANISH"),
    _lang("srn", "Sranan Tongo", "Sranantongo", "Сранан-тонго"),
    _lang("su", "Sundanese", "Basa Sunda", "Сунданский", "sun"),
    _lang("sus", "Susu", "Sosoxui", "Сусу"),
    _lang("sw", "Swahili", "Kiswahili", "Суахили", "swa", "SWAHILI"),
    _lang("ss", "Swati", "SiSwati", "Свати"),
    _lang("sv", "Swedish", "Svenska", "Шведский", "swe", "SWEDISH"),
    _lang("tg", "Tajik", "Тоҷикӣ", "Таджикский", "tgk"),
    _lang("zgh", "Tamazight", "ⵜⴰⵎⴰⵣⵉⵖⵜ", "Тамазигхтский (берберский)"),
    _lang("ta", "Tamil", "தமிழ்", "Тамильский", "tam", "TAMIL"),
    _lang("tt", "Tatar", "Татар теле", "Татарский", "tat"),
    _lang("te", "Telugu", "తెలుగు", "Телугу", "tel", "TELUGU"),
    _lang("tem", "Temne", "KʌThemnɛ", "Темне"),
    _lang("tet", "Tetum", "Tetun", "Тетум"),
    _lang("th", "Thai", "ไทย", "Тайский", "tha", "THAI"),
    _lang("bo", "Tibetan", "བོད་ཡིག", "Тибетский", "bod"),
    _lang("ti", "Tigrinya", "ትግርኛ", "Тигринья", "tir"),
    _lang("tpi", "Tok Pisin", "Tok Pisin", "Ток-писин"),
    _lang("to", "Tongan", "Lea faka-Tonga", "Тонганский", "ton"),
    _lang("ts", "Tsonga", "Xitsonga", "Тсонга", "", "TSONGA"),
    _lang("tn", "Tswana", "Setswana", "Тсвана", "", "TSWANA"),
    _lang("tcy", "Tulu", "ತುಳು", "Тулу"),
    _lang("tum", "Tumbuka", "Chitumbuka", "Тумбука"),
    _lang("tr", "Turkish", "Türkçe", "Турецкий", "tur", "TURKISH"),
    _lang("tk", "Turkmen", "Türkmençe", "Туркменский"),
    _lang("tvl", "Tuvaluan", "Te Ggana Tuuvalu", "Тувалу"),
    _lang("udm", "Udmurt", "Удмурт кыл", "Удмуртский"),
    _lang("uk", "Ukrainian", "Українська", "Украинский", "ukr", "UKRAINIAN"),
    _lang("ur", "Urdu", "اردو", "Урду", "urd", "URDU"),
    _lang("ug", "Uyghur", "ئۇيغۇرچە", "Уйгурский", "uig"),
    _lang("uz", "Uzbek", "Oʻzbekcha", "Узбекский", "uzb"),
    _lang("ve", "Venda", "Tshivenḓa", "Венда"),
    _lang("vi", "Vietnamese", "Tiếng Việt", "Вьетнамский", "vie", "VIETNAMESE"),
    _lang("war", "Waray", "Winaray", "Варайский"),
    _lang("wal", "Wolaytta", "Wolayttatto", "Воламо"),
    _lang("cy", "Welsh", "Cymraeg", "Валлийский", "cym", "WELSH"),
    _lang("wo", "Wolof", "Wolof", "Волоф"),
    _lang("xh", "Xhosa", "isiXhosa", "Коса", "", "XHOSA"),
    _lang("yi", "Yiddish", "ייִדיש", "Идиш", "yid"),
    _lang("yo", "Yoruba", "Yorùbá", "Йоруба", "yor", "YORUBA"),
    _lang("yua", "Yucatec Maya", "Maaya tʼaan", "Юкатекский майя"),
    _lang("za", "Zhuang", "Vahcuengh", "Чжуанский"),
    _lang("zu", "Zulu", "isiZulu", "Зулу", "", "ZULU"),
)

# The 10 most spoken languages of the world (native and second-language speakers,
# Ethnologue 2025), most spoken first: a group at the top of every language list.
TOP_CODES: tuple[str, ...] = ("en", "zh", "hi", "es", "ar", "fr", "bn", "pt", "ru", "id")

_BY_CODE: dict[str, Language] = {lang.code: lang for lang in LANGUAGES}

# Codes a model may answer with for a listed language.
_ALIASES: dict[str, str] = {
    "iw": "he", "in": "id", "ji": "yi", "jw": "jv", "fil": "tl", "tgl": "tl",
    "nb": "no", "nn": "no", "nob": "no", "nno": "no", "zh-cn": "zh", "zh-hans": "zh",
    "zh-sg": "zh", "cmn": "zh", "zh-hant": "zh-tw", "zh-hk": "zh-tw", "zh-mo": "zh-tw",
    "kmr": "ku", "prs": "fa", "pes": "fa", "arb": "ar", "swh": "sw", "tw": "ak", "twi": "ak",
    "gom": "kok", "mni-mtei": "mni", "ber": "zgh", "tzm": "zgh", "khk": "mn", "ekk": "et",
    "lvs": "lv", "zsm": "ms", "uzn": "uz", "azj": "az", "npi": "ne", "ory": "or", "pbt": "ps",
    "quy": "qu", "plt": "mg", "gaz": "om", "nya": "ny", "sot": "st", "nep": "ne",
}

# Tesseract and lingua mix up look-alike languages when given too many at once,
# and every lingua model costs about 20 MB, so the offline path (Tesseract)
# considers only the languages its bundled traineddata can read.
DEFAULT_OCR_CODES: tuple[str, ...] = ("pl", "ru", "en", "fr", "es", "de")


def get_language(code: str) -> Language:
    """Return the language for a code from :data:`LANGUAGES`.

    Raises:
        KeyError: If the code is not one of the supported languages.
    """
    return _BY_CODE[code.lower()]


def is_supported(code: str) -> bool:
    """Return True if ``code`` is one of the supported language codes."""
    return code.lower() in _BY_CODE


def find_language(code: str) -> Language | None:
    """Match a code written by a model (``"pt-BR"``, ``"iw"``, ``"zh_Hant"``) to a language."""
    code = code.strip().lower().replace("_", "-")
    if not code:
        return None
    for candidate in (code, code.split("-")[0]):
        candidate = _ALIASES.get(candidate, candidate)
        if candidate in _BY_CODE:
            return _BY_CODE[candidate]
    return None


def sorted_languages(ui_language: str) -> list[Language]:
    """All languages in alphabetical order of their names in ``ui_language``."""
    return sorted(LANGUAGES, key=lambda lang: lang.name(ui_language).casefold())
