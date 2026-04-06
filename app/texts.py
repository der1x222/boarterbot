def normalize_lang(lang: str | None) -> str:
    if not lang:
        return "en"
    lang = lang.strip().lower()
    if lang in {"ua", "uk", "uk-ua", "ukr"}:
        return "ua"
    if lang in {"en", "en-us", "en-gb"}:
        return "en"
    return "en"

def tr(lang: str | None, en: str, ua: str) -> str:
    return ua if normalize_lang(lang) == "ua" else en


TEXTS = {
    "choose_language": {
        "en": "Choose language / Оберіть мову",
        "ua": "Оберіть мову / Choose language",
    },
    "welcome": {
        "en": (
            "🎬 Welcome to the marketplace where video turns into money.\n\n"
            "Here clients find editors who understand style, rhythm, and trends — "
            "and editors find projects that pay fairly.\n\n"
            "Marketplace rules & safety:\n"
            "1) Make all deals only inside the marketplace chat and tools.\n"
            "2) Off‑platform deals are risky. We can’t protect you there.\n"
            "3) The marketplace is responsible only for deals completed inside the platform.\n\n"
            "By continuing, you agree to these rules.\n\n"
            "Choose your role to start:"
        ),
        "ua": (
            "🎬 Ласкаво просимо на біржу, де відео перетворюються на гроші.\n\n"
            "Тут замовники знаходять монтажерів, які розуміють стиль, ритм і тренди — "
            "а монтажери знаходять проєкти з чесною оплатою.\n\n"
            "Правила та безпека біржі:\n"
            "1) Проводьте всі угоди лише всередині біржі.\n"
            "2) Позабіржові угоди ризиковані. Ми не можемо вас там захистити.\n"
            "3) Біржа несе відповідальність лише за угоди, проведені всередині платформи.\n\n"
            "Продовжуючи, ви погоджуєтесь із цими правилами.\n\n"
            "Оберіть свою роль, щоб почати:"
        ),
    },
    "already_registered": {
        "en": "You are already registered ✅",
        "ua": "Ви вже зареєстровані ✅",
    },
    "settings_title": {
        "en": "Settings",
        "ua": "Налаштування",
    },
    "settings_text": {
        "en": "Choose language or edit your profile.",
        "ua": "Оберіть мову або відредагуйте профіль.",
    },
    "language_set": {
        "en": "Language updated.",
        "ua": "Мову змінено.",
    },
    "btn_settings": {
        "en": "⚙️ Settings",
        "ua": "⚙️ Налаштування",
    },
    "btn_edit_profile": {
        "en": "✏️ Edit profile",
        "ua": "✏️ Редагувати профіль",
    },
    "btn_role_client": {
        "en": "I am a client",
        "ua": "Я замовник",
    },
    "btn_role_editor": {
        "en": "I am an editor",
        "ua": "Я монтажер",
    },
    "btn_menu": {
        "en": "🏠 Menu",
        "ua": "🏠 Меню",
    },
    "btn_back": {
        "en": "⬅️ Back",
        "ua": "⬅️ Назад",
    },
    "btn_lang_en": {
        "en": "English",
        "ua": "English",
    },
    "btn_lang_uk": {
        "en": "Українська",
        "ua": "Українська",
    },
}


def t(key: str, lang: str | None = None) -> str:
    lang = normalize_lang(lang)
    bucket = TEXTS.get(key, {})
    if lang in bucket:
        return bucket[lang]
    if "en" in bucket:
        return bucket["en"]
    return ""
