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

def kb_nav_portfolio_none(cancel: str = "reg:cancel") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="\u041d\u0435\u0442\u0443", callback_data="reg:portfolio:none")
    b.button(text="\u274c \u041e\u0442\u043c\u0435\u043d\u0430", callback_data=cancel)
    b.adjust(2)
    return b.as_markup()


def kb_nav_menu_help(
    back: str | None = None,
    menu: str = "common:menu",
    help_: str = "common:support",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if back:
        b.button(text="⬅️ Назад", callback_data=back)
    b.button(text="🏠 Меню", callback_data=menu)
    b.button(text="🆘 Помощь", callback_data=help_)
    b.adjust(3)
    return b.as_markup()

def kb_main_menu(role: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()

    if role == "client":
        b.button(text="➕ Создать заказ", callback_data="client:create_order")
        b.button(text="⬅️ К списку", callback_data="client:my_orders")
        b.button(text="💼 Мои сделки", callback_data="client:my_deals")
        b.button(text="VIP", callback_data="common:vip")
        b.button(text="👤 Профиль", callback_data="client:profile")
        b.button(text="💳 Баланс", callback_data="common:balance")
        b.button(text="🆘 Поддержка", callback_data="common:support")
        b.adjust(2, 2, 2, 1)

    elif role == "editor":
        b.button(text="👤 Профиль", callback_data="editor:profile")
        b.button(text="✅ Пройти верификацию", callback_data="verify:start")
        b.button(text="📬 Мои отклики", callback_data="editor:my_proposals")
        b.button(text="💼 Мои сделки", callback_data="editor:my_deals")
        b.button(text="VIP", callback_data="common:vip")
        b.button(text="💳 Баланс", callback_data="common:balance")
        b.button(text="🆘 Поддержка", callback_data="common:support")
        b.adjust(2, 2, 2, 1)

    else:
        b.button(text="🆕 Новые верификации", callback_data="mod:verifications")
        b.button(text="⚠️ Споры", callback_data="mod:disputes")
        b.button(text="💬 Сообщения на проверке", callback_data="mod:held_messages")
        b.button(text="🔎 Поиск", callback_data="mod:search")
        b.button(text="📊 Статистика", callback_data="mod:stats")
        b.button(text="🚫 Пользователи / санкции", callback_data="mod:users")
        b.adjust(2, 2, 2)

    return b.as_markup()

def kb_editor_menu(is_verified: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👤 Профиль", callback_data="editor:profile")
    if is_verified:
        b.button(text="⬅️ К списку", callback_data="editor:find_orders")
    else:
        b.button(text="✅ Пройти верификацию", callback_data="verify:start")
        b.button(text="🧪 Авто-верификация (тест)", callback_data="verify:auto")
    b.button(text="📬 Мои отклики", callback_data="editor:my_proposals")
    b.button(text="💼 Мои сделки", callback_data="editor:my_deals")
    b.button(text="VIP", callback_data="common:vip")
    b.button(text="💳 Баланс", callback_data="common:balance")
    b.button(text="🆘 Поддержка", callback_data="common:support")
    b.adjust(2, 2, 2, 1)
    return b.as_markup()

def kb_profile(role: str, verification_status: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()

    if role == "editor":
        b.button(text="✏️ Изменить информацию", callback_data="edit:editor_menu")
        if verification_status != "verified":
            b.button(text="✅ Пройти верификацию", callback_data="verify:start")
    elif role == "client":
        b.button(text="✏️ Изменить информацию", callback_data="edit:client_menu")

    b.button(text="🔁 Сменить роль", callback_data="profile:change_role")
    b.button(text="🏠 Меню", callback_data="common:menu")
    b.adjust(1)
    return b.as_markup()

def kb_change_role_confirm() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Я заказчик", callback_data="profile:set_role:client")
    b.button(text="Я монтажёр", callback_data="profile:set_role:editor")
    b.button(text="⬅️ Назад", callback_data="profile:back")
    b.adjust(2, 1)
    return b.as_markup()

def kb_verify_admin(editor_user_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Approve", callback_data=f"verify:approve:{editor_user_id}")
    b.button(text="❌ Reject", callback_data=f"verify:reject:{editor_user_id}")
    b.button(text="✉️ Написать", callback_data=f"verify:msg:{editor_user_id}")
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

def kb_edit_editor_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👤 Изменить имя", callback_data="edit:editor:name")
    b.button(text="🎬 Изменить специализации", callback_data="edit:editor:skills")
    b.button(text="💰 Изменить цену", callback_data="edit:editor:price")
    b.button(text="📁 Изменить портфолио", callback_data="edit:editor:portfolio")
    b.button(text="⬅️ В профиль", callback_data="editor:profile")
    b.button(text="🏠 Меню", callback_data="common:menu")
    b.adjust(1)
    return b.as_markup()

def kb_edit_client_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👤 Изменить имя", callback_data="edit:client:name")
    b.button(text="⬅️ В профиль", callback_data="client:profile")
    b.button(text="🏠 Меню", callback_data="common:menu")
    b.adjust(1)
    return b.as_markup()

def kb_orders_list(orders: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for o in orders:
        title = (o.get("title") or "-").strip()
        if len(title) > 24:
            title = title[:21] + "..."
        b.button(text=f"#{o['id']} {title}", callback_data=f"order:view:{o['id']}")
    b.button(text="🏠 Меню", callback_data="common:menu")
    b.button(text="🆘 Поддержка", callback_data="common:support")
    sizes = [1] * len(orders)
    sizes.append(2)
    b.adjust(*sizes)
    return b.as_markup()

def kb_order_detail(order_id: int, allow_edit: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if allow_edit:
        b.button(text="✏️ Редактировать", callback_data=f"order:edit:{order_id}")
    b.button(text="⬅️ К списку", callback_data="client:my_orders")
    b.button(text="🏠 Меню", callback_data="common:menu")
    b.button(text="🆘 Поддержка", callback_data="common:support")
    if allow_edit:
        b.adjust(1, 1, 2)
    else:
        b.adjust(1, 2)
    return b.as_markup()

def kb_support(admin_username: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    username = admin_username.lstrip("@")
    b.button(text="✉️ Написать админу", url=f"https://t.me/{username}")
    b.button(text="🏠 Меню", callback_data="common:menu")
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

def kb_deal_menu(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="\U0001F4AC \u0427\u0430\u0442", callback_data=f"deal:chat:{order_id}")
    b.button(text="\u270F\ufe0f \u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c", callback_data=f"deal:change:{order_id}")
    b.button(text="\U0001F198 \u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430", callback_data="common:support")
    b.adjust(2, 1)
    return b.as_markup()

def kb_deal_chat_menu(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="\u25b6\ufe0f \u041d\u0430\u0447\u0430\u0442\u044c \u0447\u0430\u0442", callback_data=f"deal:chat:start:{order_id}")
    b.button(text="\u26a0\ufe0f \u0421\u043f\u043e\u0440", callback_data=f"deal:dispute:{order_id}")
    b.button(text="\u2b05\ufe0f \u041a \u043c\u0435\u043d\u044e \u0437\u0430\u043a\u0430\u0437\u0430", callback_data=f"deal:menu:{order_id}")
    b.adjust(1, 1, 1)
    return b.as_markup()

def kb_deal_chat_controls(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔗 Отправить ссылку", callback_data=f"deal:chat:link:{order_id}")
    b.button(text="\U0001F6AA \u0412\u044b\u0439\u0442\u0438 \u0438\u0437 \u0447\u0430\u0442\u0430", callback_data=f"deal:chat:exit:{order_id}")
    b.button(text="\u26a0\ufe0f \u0421\u043f\u043e\u0440", callback_data=f"deal:dispute:{order_id}")
    b.button(text="\u2b05\ufe0f \u041a \u043c\u0435\u043d\u044e \u0437\u0430\u043a\u0430\u0437\u0430", callback_data=f"deal:menu:{order_id}")
    b.adjust(1, 1, 1, 1)
    return b.as_markup()

def kb_deal_chat_link_controls(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад к чату", callback_data=f"deal:chat:start:{order_id}")
    b.button(text="\u2b05\ufe0f \u041a \u043c\u0435\u043d\u044e \u0437\u0430\u043a\u0430\u0437\u0430", callback_data=f"deal:menu:{order_id}")
    b.adjust(1, 1)
    return b.as_markup()

def kb_dispute_join(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="\u2696\ufe0f \u0412\u043e\u0439\u0442\u0438 \u0432 \u0441\u043f\u043e\u0440", callback_data=f"deal:dispute:join:{order_id}")
    b.adjust(1)
    return b.as_markup()

def kb_dispute_controls(order_id: int, is_moderator: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if is_moderator:
        b.button(text="\u2705 \u0417\u0430\u043a\u0440\u044b\u0442\u044c \u0441\u043f\u043e\u0440", callback_data=f"deal:dispute:close:{order_id}")
    else:
        b.button(text="\u2705 \u0421\u043e\u0433\u043b\u0430\u0441\u0435\u043d \u0437\u0430\u043a\u0440\u044b\u0442\u044c \u0441\u043f\u043e\u0440", callback_data=f"deal:dispute:agree:{order_id}")
    b.button(text="\U0001F6AA \u0412\u044b\u0439\u0442\u0438", callback_data=f"deal:dispute:exit:{order_id}")
    b.button(text="\u2b05\ufe0f \u041a \u043c\u0435\u043d\u044e \u0437\u0430\u043a\u0430\u0437\u0430", callback_data=f"deal:menu:{order_id}")
    b.adjust(1, 1, 1)
    return b.as_markup()

def kb_proposal_actions(order_id: int, editor_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💬 Начать чат", callback_data=f"proposal:chat:{order_id}:{editor_id}")
    b.button(text="✅ Принять", callback_data=f"proposal:accept:{order_id}:{editor_id}")
    b.button(text="❌ Отклонить", callback_data=f"proposal:reject:{order_id}:{editor_id}")
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
