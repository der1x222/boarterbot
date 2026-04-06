from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app import texts

def _lang_label(label_key: str, lang: str | None) -> str:
    return texts.t(label_key, lang)

def _tr(lang: str | None, en: str, ua: str) -> str:
    return texts.tr(lang, en, ua)

def kb_choose_role(lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    lng = texts.normalize_lang(lang)
    b.button(text=_lang_label("btn_role_client", lng), callback_data=f"role:client:{lng}")
    b.button(text=_lang_label("btn_role_editor", lng), callback_data=f"role:editor:{lng}")
    b.adjust(2)
    return b.as_markup()

def kb_nav(back: str | None = None, cancel: str = "reg:cancel", lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if back:
        b.button(text=_tr(lang, "⬅️ Back", "⬅️ Назад"), callback_data=back)
    b.button(text=_tr(lang, "❌ Cancel", "❌ Скасувати"), callback_data=cancel)
    b.adjust(2)
    return b.as_markup()

def kb_nav_portfolio_none(cancel: str = "reg:cancel", lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=_tr(lang, "No portfolio", "Без портфоліо"), callback_data="reg:portfolio:none")
    b.button(text=_tr(lang, "Cancel", "Скасувати"), callback_data=cancel)
    b.adjust(2)
    return b.as_markup()


def kb_nav_menu_help(
    back: str | None = None,
    menu: str = "common:menu",
    help_: str = "common:support",
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if back:
        b.button(text=_tr(lang, "Back", "Назад"), callback_data=back)
    b.button(text=_tr(lang, "Menu", "Меню"), callback_data=menu)
    b.button(text=_tr(lang, "Support", "Підтримка"), callback_data=help_)
    b.adjust(3)
    return b.as_markup()

def kb_main_menu(role: str, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    lng = texts.normalize_lang(lang)

    if role == "client":
        b.button(text=_tr(lng, "➕ Create order", "➕ Створити замовлення"), callback_data="client:create_order")
        b.button(text=_tr(lng, "⬅️ Orders list", "⬅️ До списку"), callback_data="client:my_orders")
        b.button(text=_tr(lng, "💼 My deals", "💼 Мої угоди"), callback_data="client:my_deals")
        b.button(text="VIP", callback_data="common:vip")
        b.button(text=_tr(lng, "👤 Profile", "👤 Профіль"), callback_data="client:profile")
        b.button(text=_lang_label("btn_settings", lng), callback_data="common:settings")
        b.button(text=_tr(lng, "💳 Balance", "💳 Баланс"), callback_data="common:balance")
        b.button(text=_tr(lng, "🆘 Support", "🆘 Підтримка"), callback_data="common:support")
        b.adjust(2, 2, 2, 2)

    elif role == "editor":
        b.button(text=_tr(lng, "👤 Profile", "👤 Профіль"), callback_data="editor:profile")
        b.button(text=_tr(lng, "✅ Verify", "✅ Верифікація"), callback_data="verify:start")
        b.button(text=_tr(lng, "📬 My proposals", "📬 Мої відгуки"), callback_data="editor:my_proposals")
        b.button(text=_tr(lng, "💼 My deals", "💼 Мої угоди"), callback_data="editor:my_deals")
        b.button(text="VIP", callback_data="common:vip")
        b.button(text=_lang_label("btn_settings", lng), callback_data="common:settings")
        b.button(text=_tr(lng, "💳 Balance", "💳 Баланс"), callback_data="common:balance")
        b.button(text=_tr(lng, "🆘 Support", "🆘 Підтримка"), callback_data="common:support")
        b.adjust(2, 2, 2, 2)

    else:
        return kb_moderation_menu(lng)

    return b.as_markup()

def kb_moderation_menu(lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    lng = texts.normalize_lang(lang)
    b.button(text=_tr(lng, "🆕 New verifications", "🆕 Нові верифікації"), callback_data="mod:verifications")
    b.button(text=_tr(lng, "⚠️ Disputes", "⚠️ Спори"), callback_data="mod:disputes")
    b.button(text=_tr(lng, "💬 Messages on review", "💬 Повідомлення на перевірці"), callback_data="mod:held_messages")
    b.button(text=_tr(lng, "🔎 Search", "🔎 Пошук"), callback_data="mod:search")
    b.button(text=_tr(lng, "📊 Stats", "📊 Статистика"), callback_data="mod:stats")
    b.button(text=_tr(lng, "🚫 Users / sanctions", "🚫 Користувачі / санкції"), callback_data="mod:users")
    b.button(text=_lang_label("btn_settings", lng), callback_data="common:settings")
    b.button(text=_tr(lng, "🏠 Menu", "🏠 Меню"), callback_data="common:menu")
    b.adjust(2, 2, 2, 2)
    return b.as_markup()

def kb_with_moderation_button(markup: InlineKeyboardMarkup, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for row in markup.inline_keyboard:
        b.row(*row)
    b.row(InlineKeyboardButton(text=_tr(lang, "🛠️ Moderator tools", "🛠️ Інструменти модератора"), callback_data="mod:menu"))
    return b.as_markup()

def kb_editor_menu(is_verified: bool, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    lng = texts.normalize_lang(lang)
    b.button(text=_tr(lng, "👤 Profile", "👤 Профіль"), callback_data="editor:profile")
    if is_verified:
        b.button(text=_tr(lng, "⬅️ Orders list", "⬅️ До списку"), callback_data="editor:find_orders")
    else:
        b.button(text=_tr(lng, "✅ Verify", "✅ Верифікація"), callback_data="verify:start")
    b.button(text=_tr(lng, "📬 My proposals", "📬 Мої відгуки"), callback_data="editor:my_proposals")
    b.button(text=_tr(lng, "💼 My deals", "💼 Мої угоди"), callback_data="editor:my_deals")
    b.button(text="VIP", callback_data="common:vip")
    b.button(text=_lang_label("btn_settings", lng), callback_data="common:settings")
    b.button(text=_tr(lng, "💳 Balance", "💳 Баланс"), callback_data="common:balance")
    b.button(text=_tr(lng, "🆘 Support", "🆘 Підтримка"), callback_data="common:support")
    b.adjust(2, 2, 2, 2)
    return b.as_markup()

def kb_profile(role: str, verification_status: str | None = None, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    lng = texts.normalize_lang(lang)

    if role == "editor" and verification_status != "verified":
        b.button(text=_tr(lng, "✅ Verify", "✅ Верифікація"), callback_data="verify:start")

    b.button(text=_tr(lng, "🔁 Change role", "🔁 Змінити роль"), callback_data="profile:change_role")
    b.button(text=_lang_label("btn_settings", lng), callback_data="common:settings")
    b.button(text=_tr(lng, "🏠 Menu", "🏠 Меню"), callback_data="common:menu")
    b.adjust(1, 1, 1)
    return b.as_markup()

def kb_change_role_confirm(lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=_tr(lang, "I am a client", "Я замовник"), callback_data="profile:set_role:client")
    b.button(text=_tr(lang, "I am an editor", "Я монтажер"), callback_data="profile:set_role:editor")
    b.button(text=_tr(lang, "⬅️ Back", "⬅️ Назад"), callback_data="profile:back")
    b.adjust(2, 1)
    return b.as_markup()

def kb_verify_admin(editor_user_id: int, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=_tr(lang, "✅ Approve", "✅ Підтвердити"), callback_data=f"verify:approve:{editor_user_id}")
    b.button(text=_tr(lang, "❌ Reject", "❌ Відхилити"), callback_data=f"verify:reject:{editor_user_id}")
    b.button(text=_tr(lang, "✉️ Message", "✉️ Написати"), callback_data=f"verify:msg:{editor_user_id}")
    b.adjust(2, 1)
    return b.as_markup()

def kb_mod_verification_controls(user_id: int, offset: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Approve", callback_data=f"mod:verifications:approve:{user_id}:{offset}")
    b.button(text="❌ Reject", callback_data=f"mod:verifications:reject:{user_id}:{offset}")
    b.button(text="\U0001F4AC \u0427\u0430\u0442", callback_data=f"mod:verifications:chat:{user_id}")
    b.button(text="⬅️ Назад", callback_data="common:menu")
    b.button(text="▶️ Следующий", callback_data=f"mod:verifications:page:{offset + 1}")
    b.adjust(2, 1, 2)
    return b.as_markup()

def kb_mod_held_controls(message_id: int, offset: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Approve", callback_data=f"mod:held_messages:approve:{message_id}:{offset}")
    b.button(text="❌ Reject", callback_data=f"mod:held_messages:reject:{message_id}:{offset}")
    b.button(text="🚫 Ban user", callback_data=f"mod:held_messages:ban:{message_id}:{offset}")
    b.button(text="✉️ Написать", callback_data=f"mod:held_messages:msg:{message_id}")
    b.button(text="⬅️ Назад", callback_data="common:menu")
    b.button(text="▶️ Следующий", callback_data=f"mod:held_messages:page:{offset + 1}")
    b.adjust(2, 2, 2)
    return b.as_markup()

def kb_mod_dispute_controls(deal_id: int, offset: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Выплатить исполнителю", callback_data=f"mod:disputes:pay:{deal_id}:{offset}")
    b.button(text="↩️ Вернуть заказчику", callback_data=f"mod:disputes:refund:{deal_id}:{offset}")
    b.button(text="✉️ Написать", callback_data=f"mod:disputes:msg:{deal_id}")
    b.button(text="⬅️ Назад", callback_data="common:menu")
    b.button(text="▶️ Следующий", callback_data=f"mod:disputes:page:{offset + 1}")
    b.adjust(1, 1, 1, 2)
    return b.as_markup()

def kb_mod_user_controls(user_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⚠️ Warning", callback_data=f"mod:user:warn:{user_id}")
    b.button(text="🚫 Ban", callback_data=f"mod:user:ban:{user_id}")
    b.button(text="✉️ Написать", callback_data=f"mod:user:msg:{user_id}")
    b.button(text="⬅️ Назад", callback_data="common:menu")
    b.adjust(2, 1, 1)
    return b.as_markup()

def kb_edit_editor_menu(lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=_tr(lang, "Change name", "Змінити ім'я"), callback_data="edit:editor:name")
    b.button(text=_tr(lang, "Change skills", "Змінити навички"), callback_data="edit:editor:skills")
    b.button(text=_tr(lang, "Change price", "Змінити ціну"), callback_data="edit:editor:price")
    b.button(text=_tr(lang, "Change portfolio", "Змінити портфоліо"), callback_data="edit:editor:portfolio")
    b.button(text=_tr(lang, "Back to profile", "До профілю"), callback_data="editor:profile")
    b.button(text=_tr(lang, "Menu", "Меню"), callback_data="common:menu")
    b.adjust(1)
    return b.as_markup()

def kb_edit_client_menu(lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=_tr(lang, "Change name", "Змінити ім'я"), callback_data="edit:client:name")
    b.button(text=_tr(lang, "Back to profile", "До профілю"), callback_data="client:profile")
    b.button(text=_tr(lang, "Menu", "Меню"), callback_data="common:menu")
    b.adjust(1)
    return b.as_markup()

def kb_language_start() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=texts.t("btn_lang_en", "en"), callback_data="lang:set:en")
    b.button(text=texts.t("btn_lang_uk", "ua"), callback_data="lang:set:ua")
    b.adjust(2)
    return b.as_markup()

def kb_settings_menu(role: str, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    lng = texts.normalize_lang(lang)
    has_edit = role in {"editor", "client"}
    if has_edit:
        target = "edit:editor_menu" if role == "editor" else "edit:client_menu"
        b.button(text=_lang_label("btn_edit_profile", lng), callback_data=target)
    b.button(
        text=_lang_label("btn_lang_en", lng) + (" ✅" if lng == "en" else ""),
        callback_data="lang:set:en",
    )
    b.button(
        text=_lang_label("btn_lang_uk", lng) + (" ✅" if lng == "ua" else ""),
        callback_data="lang:set:ua",
    )
    b.button(text=_lang_label("btn_menu", lng), callback_data="common:menu")
    sizes = [1, 2, 1] if has_edit else [2, 1]
    b.adjust(*sizes)
    return b.as_markup()

def kb_orders_list(orders: list[dict], lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for o in orders:
        title = (o.get("title") or "-").strip()
        if len(title) > 24:
            title = title[:21] + "..."
        b.button(text=f"#{o['id']} {title}", callback_data=f"order:view:{o['id']}")
    b.button(text=_tr(lang, "Menu", "Меню"), callback_data="common:menu")
    b.button(text=_tr(lang, "Support", "Підтримка"), callback_data="common:support")
    sizes = [1] * len(orders)
    sizes.append(2)
    b.adjust(*sizes)
    return b.as_markup()

def kb_order_detail(order_id: int, allow_edit: bool = False, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if allow_edit:
        b.button(text=_tr(lang, "Edit", "Редагувати"), callback_data=f"order:edit:{order_id}")
    b.button(text=_tr(lang, "Back to list", "До списку"), callback_data="client:my_orders")
    b.button(text=_tr(lang, "Menu", "Меню"), callback_data="common:menu")
    b.button(text=_tr(lang, "Support", "Підтримка"), callback_data="common:support")
    if allow_edit:
        b.adjust(1, 1, 2)
    else:
        b.adjust(1, 2)
    return b.as_markup()

def kb_support(admin_username: str, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    username = admin_username.lstrip("@")
    b.button(text=_tr(lang, "Message admin", "Написати адміну"), url=f"https://t.me/{username}")
    b.button(text=_tr(lang, "Menu", "Меню"), callback_data="common:menu")
    b.adjust(1, 1)
    return b.as_markup()

def kb_editor_orders_list(orders: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for o in orders:
        title = (o.get('title') or '-').strip()
        if len(title) > 24:
            title = title[:21] + '...'
        b.button(text=f"📄 Детали #{o['id']} {title}", callback_data=f"order:details:{o['id']}")
    b.button(text="🏠 Меню", callback_data="common:menu")
    b.button(text="🆘 Поддержка", callback_data="common:support")
    sizes = [1] * len(orders)
    sizes.append(2)
    b.adjust(*sizes)
    return b.as_markup()

def kb_editor_my_orders_list(orders: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for o in orders:
        title = (o.get("title") or "-").strip()
        if len(title) > 24:
            title = title[:21] + "..."
        b.button(text=f"📌 #{o['id']} {title}", callback_data=f"order:menu:{o['id']}")
    b.button(text="🏠 Меню", callback_data="common:menu")
    b.button(text="🆘 Поддержка", callback_data="common:support")
    sizes = [1] * len(orders)
    sizes.append(2)
    b.adjust(*sizes)
    return b.as_markup()

def kb_editor_order_detail(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💬 Начать чат", callback_data=f"order:chat:{order_id}")
    b.button(text="💰 Предложить цену", callback_data=f"order:proposal:{order_id}")
    b.button(text="⬅️ К списку", callback_data="editor:find_orders")
    b.button(text="🏠 Меню", callback_data="common:menu")
    b.button(text="🆘 Поддержка", callback_data="common:support")
    b.adjust(2, 1, 2)
    return b.as_markup()

def kb_deal_menu(order_id: int, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=_tr(lang, "Chat", "Чат"), callback_data=f"deal:chat:{order_id}")
    b.button(text=_tr(lang, "Change", "Змінити"), callback_data=f"deal:change:{order_id}")
    b.button(text=_tr(lang, "Support", "Підтримка"), callback_data="common:support")
    b.adjust(2, 1)
    return b.as_markup()

def kb_deal_chat_menu(order_id: int, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=_tr(lang, "Start chat", "Почати чат"), callback_data=f"deal:chat:start:{order_id}")
    b.button(text=_tr(lang, "Dispute", "Спір"), callback_data=f"deal:dispute:{order_id}")
    b.button(text=_tr(lang, "To order menu", "До меню замовлення"), callback_data=f"deal:menu:{order_id}")
    b.adjust(1, 1, 1)
    return b.as_markup()

def kb_deal_chat_controls(order_id: int, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=_tr(lang, "Send link", "Надіслати посилання"), callback_data=f"deal:chat:link:{order_id}")
    b.button(text=_tr(lang, "Exit chat", "Вийти з чату"), callback_data=f"deal:chat:exit:{order_id}")
    b.button(text=_tr(lang, "Dispute", "Спір"), callback_data=f"deal:dispute:{order_id}")
    b.button(text=_tr(lang, "To order menu", "До меню замовлення"), callback_data=f"deal:menu:{order_id}")
    b.adjust(1, 1, 1, 1)
    return b.as_markup()

def kb_deal_chat_link_controls(order_id: int, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=_tr(lang, "Back to chat", "Назад до чату"), callback_data=f"deal:chat:start:{order_id}")
    b.button(text=_tr(lang, "To order menu", "До меню замовлення"), callback_data=f"deal:menu:{order_id}")
    b.adjust(1, 1)
    return b.as_markup()

def kb_dispute_join(order_id: int, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=_tr(lang, "Join dispute", "Увійти в спір"), callback_data=f"deal:dispute:join:{order_id}")
    b.adjust(1)
    return b.as_markup()

def kb_dispute_controls(order_id: int, is_moderator: bool = False, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if is_moderator:
        b.button(text=_tr(lang, "Close dispute", "Закрити спір"), callback_data=f"deal:dispute:close:{order_id}")
    else:
        b.button(text=_tr(lang, "Agree to close dispute", "Згоден закрити спір"), callback_data=f"deal:dispute:agree:{order_id}")
    b.button(text=_tr(lang, "Exit", "Вийти"), callback_data=f"deal:dispute:exit:{order_id}")
    b.button(text=_tr(lang, "To order menu", "До меню замовлення"), callback_data=f"deal:menu:{order_id}")
    b.adjust(1, 1, 1)
    return b.as_markup()

def kb_proposal_actions(order_id: int, editor_id: int, lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=_tr(lang, "Start chat", "Почати чат"), callback_data=f"proposal:chat:{order_id}:{editor_id}")
    b.button(text=_tr(lang, "Accept", "Прийняти"), callback_data=f"proposal:accept:{order_id}:{editor_id}")
    b.button(text=_tr(lang, "Reject", "Відхилити"), callback_data=f"proposal:reject:{order_id}:{editor_id}")
    b.adjust(1, 1, 1)
    return b.as_markup()

def kb_verify_chat_reply(moderator_user_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💬 Ответить", callback_data=f"verify:chat:reply:{moderator_user_id}")
    b.adjust(1)
    return b.as_markup()

def kb_verify_chat_controls() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚪 Выйти", callback_data="verify:chat:exit")
    b.adjust(1)
    return b.as_markup()
