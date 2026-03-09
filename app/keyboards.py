from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def kb_choose_role() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Я заказчик", callback_data="role:client")
    b.button(text="Я монтажёр", callback_data="role:editor")
    b.adjust(2)
    return b.as_markup()

def kb_nav(back: str | None = None, cancel: str = "reg:cancel") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if back:
        b.button(text="⬅️ Назад", callback_data=back)
    b.button(text="❌ Отмена", callback_data=cancel)
    b.adjust(2)
    return b.as_markup()

def kb_profile_editor() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Сменить информацию", callback_data="reg:edit_editor")
    b.button(text="⬅️ В меню", callback_data="common:menu")
    b.adjust(1)
    return b.as_markup()

def kb_profile_client() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Сменить информацию", callback_data="reg:edit_client")
    b.button(text="⬅️ В меню", callback_data="common:menu")
    b.adjust(1)
    return b.as_markup()

def kb_main_menu(role: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()

    if role == "client":
        b.button(text="➕ Создать заказ", callback_data="client:create_order")
        b.button(text="📦 Мои заказы", callback_data="client:my_orders")
        b.button(text="💼 Мои сделки", callback_data="client:my_deals")
        b.button(text="👤 Профиль", callback_data="client:profile")
        b.button(text="💳 Баланс", callback_data="common:balance")
        b.button(text="🆘 Поддержка", callback_data="common:support")
        b.adjust(2, 2, 2)

    elif role == "editor":
        b.button(text="👤 Профиль", callback_data="editor:profile")
        b.button(text="🔎 Найти заказы", callback_data="editor:find_orders")
        b.button(text="📬 Мои отклики", callback_data="editor:my_proposals")
        b.button(text="💼 Мои сделки", callback_data="editor:my_deals")
        b.button(text="💳 Баланс", callback_data="common:balance")
        b.button(text="🆘 Поддержка", callback_data="common:support")
        b.adjust(2, 2, 2)

    else:
        b.button(text="🆕 Сообщения на проверке", callback_data="mod:held_messages")
        b.button(text="⚠️ Споры", callback_data="mod:disputes")
        b.button(text="📊 Статистика", callback_data="mod:stats")
        b.adjust(1)

    return b.as_markup()
def kb_profile(role: str, verification_status: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()

    if role == "editor":
        b.button(text="✏️ Изменить информацию", callback_data="reg:edit_editor")
        if verification_status != "verified":
            b.button(text="✅ Пройти верификацию", callback_data="verify:start")

    elif role == "client":
        b.button(text="✏️ Изменить информацию", callback_data="reg:edit_client")

    b.button(text="🔁 Сменить роль", callback_data="profile:change_role")
    b.button(text="⬅️ В меню", callback_data="common:menu")
    b.adjust(1)
    return b.as_markup()

def kb_change_role_confirm() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Я заказчик", callback_data="profile:set_role:client")
    b.button(text="Я монтажёр", callback_data="profile:set_role:editor")
    b.button(text="⬅️ Назад", callback_data="profile:back")
    b.adjust(2, 1)
    return b.as_markup()
def kb_editor_menu(is_verified: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👤 Профиль", callback_data="editor:profile")

    if is_verified:
        b.button(text="🔎 Найти заказы", callback_data="editor:find_orders")
    else:
        b.button(text="✅ Пройти верификацию", callback_data="verify:start")

    b.button(text="📬 Мои отклики", callback_data="editor:my_proposals")
    b.button(text="💼 Мои сделки", callback_data="editor:my_deals")
    b.button(text="💳 Баланс", callback_data="common:balance")
    b.button(text="🆘 Поддержка", callback_data="common:support")
    b.adjust(2, 2, 2)
    return b.as_markup()