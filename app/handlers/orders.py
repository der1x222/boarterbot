from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from datetime import datetime

from app.models import get_user_by_telegram_id, get_user_by_id, list_moderators
from app.keyboards import kb_nav_menu_help, kb_orders_list, kb_order_detail, kb_deal_menu, kb_editor_order_detail, kb_deal_chat_controls, kb_dispute_join, kb_dispute_controls, kb_deal_chat_menu, kb_proposal_actions
from app.menu_utils import get_menu_markup_for_user
from app.states import CreateOrder, DealChange, EditOrder, EditorProposal, DealChat, DisputeChat, DisputeOpenReason, ChatRequest
from app.order_repo import create_order, list_orders_for_client, get_order_for_client, accept_order, get_order_by_id, update_order_if_open, open_dispute, set_dispute_agree, close_dispute
from app.profile_repo import get_editor_profile

router = Router()

# ---------- helpers for clean chat ----------

async def safe_delete_message(message: Message | None):
    if not message:
        return
    try:
        await message.delete()
    except:
        pass

async def safe_delete_by_id(bot, chat_id: int, message_id: int | None):
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass

async def set_last_bot_message(state: FSMContext, message_id: int):
    await state.update_data(last_bot_message_id=message_id)

async def clear_last_bot_message(state: FSMContext, bot, chat_id: int):
    data = await state.get_data()
    await safe_delete_by_id(bot, chat_id, data.get("last_bot_message_id"))
    await state.update_data(last_bot_message_id=None)

async def send_clean(message: Message, state: FSMContext, text: str, reply_markup=None):
    await clear_last_bot_message(state, message.bot, message.chat.id)
    msg = await message.answer(text, reply_markup=reply_markup)
    await set_last_bot_message(state, msg.message_id)
    return msg

async def send_clean_from_call(call: CallbackQuery, state: FSMContext, text: str, reply_markup=None):
    chat_id = call.message.chat.id
    await clear_last_bot_message(state, call.bot, chat_id)
    try:
        await safe_delete_message(call.message)
    except:
        pass
    msg = await call.message.answer(text, reply_markup=reply_markup)
    await set_last_bot_message(state, msg.message_id)
    return msg

# ---------- create order flow ----------

@router.callback_query(F.data == "client:create_order")
async def create_order_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "client":
        await call.answer("Создание заказа доступно только заказчику.", show_alert=True)
        return

    await state.clear()
    await state.set_state(CreateOrder.waiting_title)
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        "Введите название заказа:",
        reply_markup=kb_nav_menu_help(back="order:back:menu"),
    )

@router.callback_query(F.data.startswith("order:back:"))
async def create_order_back(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "client":
        await state.clear()
        await call.message.answer("Создание заказа доступно только заказчику.")
        await call.answer()
        return

    action = call.data.split(":")[-1]
    await call.answer()

    if action == "menu":
        await state.clear()
        await send_clean_from_call(
            call,
            state,
            "Меню:",
            reply_markup=await get_menu_markup_for_user(user),
        )
        return

    if action == "title":
        await state.set_state(CreateOrder.waiting_title)
        await send_clean_from_call(
            call,
            state,
            "Введите название заказа:",
            reply_markup=kb_nav_menu_help(back="order:back:menu"),
        )
        return

    if action == "description":
        await state.set_state(CreateOrder.waiting_description)
        await send_clean_from_call(
            call,
            state,
            "Опишите задачу и требования (можно ссылкой):",
            reply_markup=kb_nav_menu_help(back="order:back:title"),
        )
        return

    if action == "budget":
        await state.set_state(CreateOrder.waiting_budget)
        await send_clean_from_call(
            call,
            state,
            "Укажите бюджет в долларах (число). Например: 50",
            reply_markup=kb_nav_menu_help(back="order:back:description"),
        )
        return

    if action == "revision_price":
        await state.set_state(CreateOrder.waiting_revision_price)
        await send_clean_from_call(
            call,
            state,
            "Укажите цену за правки (в долларах, число). Например: 10",
            reply_markup=kb_nav_menu_help(back="order:back:budget"),
        )
        return

@router.callback_query(F.data == "order:cancel")
async def create_order_cancel(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    await state.clear()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        "Ок, отменено.",
        reply_markup=await get_menu_markup_for_user(user),
    )

@router.message(CreateOrder.waiting_title)
async def create_order_title(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Создание заказа доступно только заказчику.")
        return

    title = (message.text or "").strip()
    await safe_delete_message(message)

    if not title:
        await send_clean(
            message,
            state,
            "Название не должно быть пустым. Введите название заказа:",
            reply_markup=kb_nav_menu_help(back="order:back:menu"),
        )
        return

    await state.update_data(title=title)
    await state.set_state(CreateOrder.waiting_description)
    await send_clean(
        message,
        state,
        "Опишите задачу и требования (можно ссылкой):",
        reply_markup=kb_nav_menu_help(back="order:back:title"),
    )

@router.message(CreateOrder.waiting_description)
async def create_order_description(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Создание заказа доступно только заказчику.")
        return

    description = (message.text or "").strip()
    await safe_delete_message(message)

    if not description:
        await send_clean(
            message,
            state,
            "Описание не должно быть пустым. Опишите задачу:",
            reply_markup=kb_nav_menu_help(back="order:back:title"),
        )
        return

    await state.update_data(description=description)
    await state.set_state(CreateOrder.waiting_budget)
    await send_clean(
        message,
        state,
        "Укажите бюджет в долларах (число). Например: 50",
        reply_markup=kb_nav_menu_help(back="order:back:description"),
    )

@router.message(CreateOrder.waiting_budget)
async def create_order_budget(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Создание заказа доступно только заказчику.")
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    if not raw.isdigit():
        await send_clean(
            message,
            state,
            "Бюджет должен быть числом. Например: 50",
            reply_markup=kb_nav_menu_help(back="order:back:description"),
        )
        return

    await state.update_data(budget_minor=int(raw) * 100)
    await state.set_state(CreateOrder.waiting_revision_price)
    await send_clean(
        message,
        state,
        "Укажите цену за правки (в долларах, число). Например: 10",
        reply_markup=kb_nav_menu_help(back="order:back:budget"),
    )

@router.message(CreateOrder.waiting_revision_price)
async def create_order_revision_price(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Создание заказа доступно только заказчику.")
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    if not raw.isdigit():
        await send_clean(
            message,
            state,
            "Цена за правки должна быть числом. Например: 10",
            reply_markup=kb_nav_menu_help(back="order:back:budget"),
        )
        return

    await state.update_data(revision_price_minor=int(raw) * 100)
    await state.set_state(CreateOrder.waiting_deadline)
    await send_clean(
        message,
        state,
        "Укажите дедлайн (гггг-мм-дд чч:мм). Например: 2026-03-15 18:30",
        reply_markup=kb_nav_menu_help(back="order:back:revision_price"),
    )

@router.message(CreateOrder.waiting_deadline)
async def create_order_deadline(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Создание заказа доступно только заказчику.")
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    try:
        deadline_at = datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except ValueError:
        await send_clean(
            message,
            state,
            "Дедлайн должен быть в формате гггг-мм-дд чч:мм. Например: 2026-03-15 18:30",
            reply_markup=kb_nav_menu_help(back="order:back:revision_price"),
        )
        return

    data = await state.get_data()
    order_id = await create_order(
        client_id=user.id,
        title=data.get("title", ""),
        description=data.get("description", ""),
        budget_minor=int(data.get("budget_minor") or 0),
        revision_price_minor=int(data.get("revision_price_minor") or 0),
        deadline_at=deadline_at,
        currency="USD",
    )

    await state.clear()
    await clear_last_bot_message(state, message.bot, message.chat.id)

    await message.answer(
        f"✅ Заказ создан. Номер: #{order_id}",
            reply_markup=await get_menu_markup_for_user(user),
    )

@router.callback_query(F.data == "client:my_orders")
async def my_orders(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "client":
        await call.answer("Раздел доступен только заказчику.", show_alert=True)
        return

    orders = await list_orders_for_client(user.id, limit=10)
    if not orders:
        await call.message.answer("У вас пока нет заказов.", reply_markup=await get_menu_markup_for_user(user))
        await call.answer()
        return

    text = "Ваши заказы:\n\nВыберите заказ для просмотра."
    await call.message.answer(text, reply_markup=kb_orders_list(orders))
    await call.answer()

@router.callback_query(F.data.startswith("order:view:"))
async def order_view(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "client":
        await call.answer("Раздел доступен только заказчику.", show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_for_client(order_id, user.id)
    if not order:
        await call.answer("Заказ не найден.", show_alert=True)
        return

    price = f"{int(order.get('budget_minor') or 0) / 100:.2f} {order.get('currency') or 'USD'}"
    revision_price = f"{int(order.get('revision_price_minor') or 0) / 100:.2f} {order.get('currency') or 'USD'}"
    created_at = order.get("created_at")
    created_label = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "-"
    deadline_at = order.get("deadline_at")
    deadline_label = deadline_at.strftime("%Y-%m-%d %H:%M") if deadline_at else "-"

    title = order.get("title") or "-"
    description = order.get("description") or "-"
    if len(description) > 1500:
        description = description[:1497] + "..."

    allow_edit = order.get("status") == "open" and not order.get("editor_id")
    text = (
        f"Заказ #{order['id']}\n\n"
        f"Название: {title}\n"
        f"Описание: {description}\n"
        f"Бюджет: {price}\n"
        f"Цена за правки: {revision_price}\n"
        f"Статус: {order.get('status')}\n"
        f"Создан: {created_label}\n"
        f"Дедлайн: {deadline_label}"
    )

    await call.message.answer(text, reply_markup=kb_order_detail(order_id, allow_edit=allow_edit))
    await call.answer()

@router.callback_query(F.data == "order_edit:cancel")
async def order_edit_cancel(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    await state.clear()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        "Меню:",
        reply_markup=await get_menu_markup_for_user(user),
    )

@router.callback_query(F.data.startswith("order:edit:"))
async def order_edit_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "client":
        await call.answer("Раздел доступен только заказчику.", show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_for_client(order_id, user.id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await call.answer("Заказ нельзя редактировать.", show_alert=True)
        return

    await state.clear()
    await state.set_state(EditOrder.waiting_title)
    await state.update_data(order_id=order_id)
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        f"Введите новое название заказа (текущее: {order.get('title') or '-'}):",
        reply_markup=kb_nav_menu_help(back="order_edit:cancel"),
    )

@router.message(EditOrder.waiting_title)
async def order_edit_title(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Создание заказа доступно только заказчику.")
        return

    title = (message.text or "").strip()
    await safe_delete_message(message)
    if not title:
        await send_clean(
            message,
            state,
            "Название не должно быть пустым.",
            reply_markup=kb_nav_menu_help(back="order_edit:cancel"),
        )
        return

    await state.update_data(title=title)
    await state.set_state(EditOrder.waiting_description)
    await send_clean(
        message,
        state,
        "Опишите задачу и требования (можно ссылкой):",
        reply_markup=kb_nav_menu_help(back="order_edit:cancel"),
    )

@router.message(EditOrder.waiting_description)
async def order_edit_description(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Создание заказа доступно только заказчику.")
        return

    description = (message.text or "").strip()
    await safe_delete_message(message)
    if not description:
        await send_clean(
            message,
            state,
            "Описание не должно быть пустым.",
            reply_markup=kb_nav_menu_help(back="order_edit:cancel"),
        )
        return

    await state.update_data(description=description)
    await state.set_state(EditOrder.waiting_budget)
    await send_clean(
        message,
        state,
        "Укажите бюджет в долларах (число). Например: 50",
        reply_markup=kb_nav_menu_help(back="order_edit:cancel"),
    )

@router.message(EditOrder.waiting_budget)
async def order_edit_budget(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Создание заказа доступно только заказчику.")
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)
    if not raw.isdigit():
        await send_clean(
            message,
            state,
            "Бюджет должен быть числом. Например: 50",
            reply_markup=kb_nav_menu_help(back="order_edit:cancel"),
        )
        return

    await state.update_data(budget_minor=int(raw) * 100)
    await state.set_state(EditOrder.waiting_revision_price)
    await send_clean(
        message,
        state,
        "Укажите цену за правки (в долларах, число). Например: 10",
        reply_markup=kb_nav_menu_help(back="order_edit:cancel"),
    )

@router.message(EditOrder.waiting_revision_price)
async def order_edit_revision_price(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Создание заказа доступно только заказчику.")
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)
    if not raw.isdigit():
        await send_clean(
            message,
            state,
            "Цена за правки должна быть числом. Например: 10",
            reply_markup=kb_nav_menu_help(back="order_edit:cancel"),
        )
        return

    await state.update_data(revision_price_minor=int(raw) * 100)
    await state.set_state(EditOrder.waiting_deadline)
    await send_clean(
        message,
        state,
        "Укажите дедлайн (гггг-мм-дд чч:мм). Например: 2026-03-15 18:30",
        reply_markup=kb_nav_menu_help(back="order_edit:cancel"),
    )

@router.message(EditOrder.waiting_deadline)
async def order_edit_deadline(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Создание заказа доступно только заказчику.")
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    try:
        deadline_at = datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except ValueError:
        await send_clean(
            message,
            state,
            "Дедлайн должен быть в формате гггг-мм-дд чч:мм. Например: 2026-03-15 18:30",
            reply_markup=kb_nav_menu_help(back="order_edit:cancel"),
        )
        return

    data = await state.get_data()
    order_id = int(data.get('order_id') or 0)
    ok = await update_order_if_open(
        order_id=order_id,
        client_id=user.id,
        title=data.get('title', ''),
        description=data.get('description', ''),
        budget_minor=int(data.get('budget_minor') or 0),
        revision_price_minor=int(data.get('revision_price_minor') or 0),
        deadline_at=deadline_at,
    )

    await state.clear()

    if not ok:
        await message.answer("Заказ нельзя редактировать. Возможно, на него уже откликнулись.")
        return

    await message.answer("✅ Заказ обновлен.", reply_markup=await get_menu_markup_for_user(user))

@router.callback_query(F.data.startswith("order:details:"))
async def order_details_for_editor(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "editor":
        await call.answer("Доступно только монтажёрам.", show_alert=True)
        return

    p = await get_editor_profile(user.id)
    if not p or p.get("verification_status") != "verified":
        await call.answer("⛔ Сначала пройдите верификацию.", show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await call.answer("Заказ недоступен.", show_alert=True)
        return

    price = f"{int(order.get('budget_minor') or 0) / 100:.2f} {order.get('currency') or 'USD'}"
    revision_price = f"{int(order.get('revision_price_minor') or 0) / 100:.2f} {order.get('currency') or 'USD'}"
    created_at = order.get('created_at')
    created_label = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "-"
    deadline_at = order.get('deadline_at')
    deadline_label = deadline_at.strftime("%Y-%m-%d %H:%M") if deadline_at else "-"

    title = order.get('title') or '-'
    description = order.get('description') or '-'
    if len(description) > 1500:
        description = description[:1497] + '...'

    text = (
        f"Заказ #{order['id']}\n\n"
        f"Название: {title}\n"
        f"Описание: {description}\n"
        f"Бюджет: {price}\n"
        f"Цена за правки: {revision_price}\n"
        f"Создан: {created_label}\n"
        f"Дедлайн: {deadline_label}"
    )

    await call.message.answer(text, reply_markup=kb_editor_order_detail(order_id))
    await call.answer()


@router.callback_query(F.data.startswith("order:chat:"))
async def order_chat_request(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "editor":
        await call.answer("Доступно только монтажерам.", show_alert=True)
        return

    p = await get_editor_profile(user.id)
    if not p or p.get("verification_status") != "verified":
        await call.answer("⛔ Сначала пройдите верификацию.", show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await call.answer("Заказ недоступен.", show_alert=True)
        return

    await state.clear()
    await state.set_state(ChatRequest.waiting_text)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer("Напишите текст запроса на чат для заказчика:")

@router.message(ChatRequest.waiting_text)
async def order_chat_request_text(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer("Доступно только монтажерам.")
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не должен быть пустым.")
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await state.clear()
        await message.answer("Заказ недоступен.")
        return

    client = await get_user_by_id(int(order['client_id']))
    if client:
        editor_name = user.display_name or user.username or f"id:{user.telegram_id}"
        editor_username = f"@{user.username}" if user.username else ""
        await message.bot.send_message(
            client.telegram_id,
            f"Запрос на чат по заказу #{order_id} от {editor_name} {editor_username}:\n{text}",
        )

    await state.clear()
    await message.answer("Запрос отправлен заказчику.")

@router.callback_query(F.data.startswith("order:proposal:"))
async def order_proposal_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "editor":
        await call.answer("Доступно только монтажерам.", show_alert=True)
        return

    p = await get_editor_profile(user.id)
    if not p or p.get("verification_status") != "verified":
        await call.answer("⛔ Сначала пройдите верификацию.", show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await call.answer("Заказ недоступен.", show_alert=True)
        return

    await state.clear()
    await state.set_state(EditorProposal.waiting_price)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer("Укажите вашу цену в долларах (число). Например: 80")

@router.message(EditorProposal.waiting_price)
async def order_proposal_price(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer("Доступно только монтажерам.")
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Цена должна быть числом. Например: 80")
        return

    await state.update_data(proposal_price=int(raw) * 100)
    await state.set_state(EditorProposal.waiting_comment)
    await message.answer("Короткий комментарий к предложению (можно одним сообщением).")

@router.message(EditorProposal.waiting_comment)
async def order_proposal_comment(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer("Доступно только монтажерам.")
        return

    comment = (message.text or "").strip()
    if not comment:
        await message.answer("Напишите короткий комментарий.")
        return

    data = await state.get_data()
    order_id = int(data.get('order_id') or 0)
    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await state.clear()
        await message.answer("Заказ недоступен.")
        return

    client = await get_user_by_id(int(order['client_id']))
    if client:
        price = f"{int(data.get('proposal_price') or 0) / 100:.2f} {order.get('currency') or 'USD'}"
        editor_name = user.display_name or user.username or f"id:{user.telegram_id}"
        editor_username = f"@{user.username}" if user.username else ""
        await message.bot.send_message(
            client.telegram_id,
            f"Предложение по заказу #{order_id} от {editor_name} {editor_username}:\n"
            f"Цена: {price}\n"
            f"Комментарий: {comment}",
            reply_markup=kb_proposal_actions(order_id, user.id),
        )

    await state.clear()
    await message.answer("Предложение отправлено заказчику.")

@router.callback_query(F.data.startswith("proposal:accept:"))
async def proposal_accept(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "client":
        await call.answer("Доступно только заказчику.", show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer("Неверные данные.", show_alert=True)
        return

    try:
        order_id = int(parts[2])
        editor_id = int(parts[3])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("client_id") != user.id:
        await call.answer("Заказ не найден.", show_alert=True)
        return
    if order.get("status") != "open" or order.get("editor_id"):
        await call.answer("Заказ недоступен.", show_alert=True)
        return

    ok = await accept_order(order_id, editor_id)
    if not ok:
        await call.answer("Не удалось принять заказ.", show_alert=True)
        return

    editor = await get_user_by_id(editor_id)
    if editor:
        await call.bot.send_message(
            editor.telegram_id,
            f"Заказ #{order_id} принят заказчиком.",
            reply_markup=kb_deal_menu(order_id),
        )

    await call.answer("Заказ принят.", show_alert=True)

@router.callback_query(F.data.startswith("proposal:reject:"))
async def proposal_reject(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "client":
        await call.answer("Доступно только заказчику.", show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer("Неверные данные.", show_alert=True)
        return

    try:
        order_id = int(parts[2])
        editor_id = int(parts[3])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("client_id") != user.id:
        await call.answer("Заказ не найден.", show_alert=True)
        return

    editor = await get_user_by_id(editor_id)
    if editor:
        await call.bot.send_message(editor.telegram_id, f"Заказчик отклонил предложение по заказу #{order_id}.")

    await call.answer("Отклонено.", show_alert=True)

@router.callback_query(F.data.startswith("proposal:chat:"))
async def proposal_chat(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "client":
        await call.answer("Доступно только заказчику.", show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer("Неверные данные.", show_alert=True)
        return

    try:
        order_id = int(parts[2])
        editor_id = int(parts[3])
    except ValueError:
        await call.answer("Неверные даннеые.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("client_id") != user.id:
        await call.answer("Заказ не найден.", show_alert=True)
        return

    editor = await get_user_by_id(editor_id)
    if editor:
        client_name = user.display_name or user.username or f"id:{user.telegram_id}"
        client_username = f"@{user.username}" if user.username else ""
        await call.bot.send_message(
            editor.telegram_id,
            f"Заказчик {client_name} {client_username} хочет начать чат по заказу #{order_id}.",
        )

    await call.answer("Запрос отправлен эдитору.", show_alert=True)

@router.callback_query(F.data.startswith("deal:change:"))
async def deal_change_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "editor":
        await call.answer("Доступно только монтажёрам.", show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id:
        await call.answer("Заказ не найден.", show_alert=True)
        return

    await state.clear()
    await state.set_state(DealChange.waiting_text)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer("Опишите что нужно изменить:")

@router.message(DealChange.waiting_text)
async def deal_change_submit(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer("Доступно только монтажёрам.")
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Опишите что нужно изменить.")
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id:
        await state.clear()
        await message.answer("Заказ не найден.")
        return

    client = await get_user_by_id(int(order["client_id"]))
    if client:
        await message.bot.send_message(
            client.telegram_id,
            f"Запрос на изменение по заказу #{order_id}:\n{text}",
        )

    await state.clear()
    await message.answer("Отправлено заказчику.")

@router.callback_query(F.data.startswith("order:menu:"))
async def order_menu_open(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "editor":
        await call.answer("Доступно только монтажёрам.", show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id:
        await call.answer("Заказ не найден.", show_alert=True)
        return

    await call.message.answer("Меню заказа:", reply_markup=kb_deal_menu(order_id))
    await call.answer()

# ---------- deal chat & dispute ----------

def _user_label(user) -> str:
    name = user.display_name or user.username or f"id:{user.telegram_id}"
    username = f"@{user.username}" if user.username else ""
    return f"{name} {username}".strip()

@router.callback_query(F.data.startswith("deal:menu:"))
async def deal_menu_open(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer("Нет доступа.", show_alert=True)
        return

    await call.answer()
    await call.message.answer("Меню заказа:", reply_markup=kb_deal_menu(order_id))

@router.callback_query(F.data.startswith("deal:chat:exit:"))
async def deal_chat_exit(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    await state.clear()
    await call.answer()
    await call.message.answer("Чат закрыт.", reply_markup=kb_deal_chat_menu(order_id))

@router.callback_query(F.data.startswith("deal:chat:start:"))
async def deal_chat_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await call.answer("Сделка не найдена.", show_alert=True)
        return

    if order.get("status") == "dispute":
        await call.answer("Спор активен. Перейдите в спор.", show_alert=True)
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer("Нет доступа.", show_alert=True)
        return

    await state.clear()
    await state.set_state(DealChat.chatting)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(
        f"Чат по заказу #{order_id}. Пишите сообщение.",
        reply_markup=kb_deal_chat_controls(order_id),
    )

@router.callback_query(F.data.startswith("deal:chat:"))
async def deal_chat_menu(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 3:
        return

    try:
        order_id = int(parts[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer("Нет доступа.", show_alert=True)
        return

    await call.answer()
    await call.message.answer("Меню чата:", reply_markup=kb_deal_chat_menu(order_id))

@router.message(DealChat.chatting)
async def deal_chat_message(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    if not order_id:
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await state.clear()
        await message.answer("Сделка не найдена.")
        return

    if order.get("status") == "dispute":
        await message.answer("Спор активен. Перейдите в спор.")
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")):
        await message.answer("Нет доступа.")
        return

    text = (message.text or "").strip()
    if not text:
        return

    recipient_id = order.get("editor_id") if user.id == order.get("client_id") else order.get("client_id")
    recipient = await get_user_by_id(int(recipient_id))
    if recipient:
        await message.bot.send_message(
            recipient.telegram_id,
            f"Чат по заказу #{order_id} от {_user_label(user)}\n{text}",
            reply_markup=kb_deal_chat_controls(order_id),
        )

@router.callback_query(F.data.startswith("deal:dispute:exit:"))
async def dispute_exit(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    await state.clear()
    await call.answer()
    await call.message.answer("Вы вышли из спора.", reply_markup=kb_deal_menu(order_id))

@router.callback_query(F.data.startswith("deal:dispute:join:"))
async def dispute_join(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("status") != "dispute":
        await call.answer("Спор не активен.", show_alert=True)
        return

    if user.role != "moderator" and user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer("Нет доступа.", show_alert=True)
        return

    await state.clear()
    await state.set_state(DisputeChat.chatting)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(
        "Спор открыт. Окончательное решение выносит модератор.\n"
        "Спор может закрыть модератор или если обе стороны согласятся.",
        reply_markup=kb_dispute_controls(order_id, is_moderator=(user.role == "moderator")),
    )

@router.callback_query(F.data.startswith("deal:dispute:agree:"))
async def dispute_agree(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role not in ("client", "editor"):
        await call.answer("Нет доступа.", show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("status") != "dispute":
        await call.answer("Спор не активен.", show_alert=True)
        return

    client_agree, editor_agree = await set_dispute_agree(order_id, user.role)
    await call.answer("Отмечено.", show_alert=True)

    if client_agree and editor_agree:
        await close_dispute(order_id)
        client = await get_user_by_id(int(order["client_id"]))
        editor = await get_user_by_id(int(order["editor_id"]))
        moderators = await list_moderators()
        msg = f"Спор по заказу #{order_id} закрыт по согласию сторон.",
        if client:
            await call.bot.send_message(client.telegram_id, msg)
        if editor:
            await call.bot.send_message(editor.telegram_id, msg)
        for m in moderators:
            await call.bot.send_message(m.telegram_id, msg)

@router.callback_query(F.data.startswith("deal:dispute:close:"))
async def dispute_close(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "moderator":
        await call.answer("Нет доступа.", show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    ok = await close_dispute(order_id)
    if not ok:
        await call.answer("Спор не активен.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    client = await get_user_by_id(int(order["client_id"])) if order else None
    editor = await get_user_by_id(int(order["editor_id"])) if order else None
    moderators = await list_moderators()
    msg = f"Спор по заказу #{order_id} закрыт модератором.",
    if client:
        await call.bot.send_message(client.telegram_id, msg)
    if editor:
        await call.bot.send_message(editor.telegram_id, msg)
    for m in moderators:
        await call.bot.send_message(m.telegram_id, msg)

@router.callback_query(F.data.startswith("deal:dispute:"))
async def dispute_open(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 3:
        return

    try:
        order_id = int(parts[-1])
    except ValueError:
        await call.answer("Некорректный номер.", show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await call.answer("Сделка не найдена.", show_alert=True)
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer("Нет доступа.", show_alert=True)
        return

    if order.get("status") == "dispute":
        await call.answer("Спор уже активен.", show_alert=True)
        return

    await state.clear()
    await state.set_state(DisputeOpenReason.waiting_text)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer("Опишите причину спора одним сообщением.")

@router.message(DisputeOpenReason.waiting_text)
async def dispute_open_reason(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    if not order_id:
        await state.clear()
        return

    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Причина не должна быть пустой.")
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await state.clear()
        await message.answer("Сделка не найдена.")
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")):
        await state.clear()
        await message.answer("Нет доступа.")
        return

    ok = await open_dispute(order_id, user.id)
    if not ok:
        await state.clear()
        await message.answer("Не удалось открыть спор.")
        return

    await state.clear()
    await state.set_state(DisputeChat.chatting)
    await state.update_data(order_id=order_id)

    warning = (
        "Внимание! Сделка заморожена до конца спора.\n"
        "Окончательное решение выносит модератор.\n"
        "Спор может закрыть модератор или если обе стороны согласятся.",
    )

    client = await get_user_by_id(int(order["client_id"]))
    editor = await get_user_by_id(int(order["editor_id"]))
    moderators = await list_moderators()

    mod_msg = f"Спор по заказу #{order_id} открыт. Причина: {reason}",

    if client and client.telegram_id != message.from_user.id:
        await message.bot.send_message(client.telegram_id, warning, reply_markup=kb_dispute_join(order_id))
    if editor and editor.telegram_id != message.from_user.id:
        await message.bot.send_message(editor.telegram_id, warning, reply_markup=kb_dispute_join(order_id))
    for m in moderators:
        await message.bot.send_message(m.telegram_id, mod_msg, reply_markup=kb_dispute_join(order_id))

    await message.answer(warning, reply_markup=kb_dispute_controls(order_id, is_moderator=False))

@router.message(DisputeChat.chatting)
async def dispute_chat_message(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    if not order_id:
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("status") != "dispute":
        await state.clear()
        await message.answer("Спор не активен.")
        return

    if user.role != "moderator" and user.id not in (order.get("client_id"), order.get("editor_id")):
        await message.answer("Нет доступа.")
        return

    text = (message.text or "").strip()
    if not text:
        return

    prefix = f"СПОР #{order_id} от {_user_label(user)}\n"

    moderators = await list_moderators()
    recipients = []
    if order.get("client_id"):
        recipients.append(int(order.get("client_id")))
    if order.get("editor_id"):
        recipients.append(int(order.get("editor_id")))

    for uid in recipients:
        if uid == user.id:
            continue
        u = await get_user_by_id(uid)
        if u:
            await message.bot.send_message(
                u.telegram_id,
                prefix + text,
                reply_markup=kb_dispute_controls(order_id, is_moderator=False),
            )

    for m in moderators:
        if m.id == user.id:
            continue
        await message.bot.send_message(
            m.telegram_id,
            prefix + text,
            reply_markup=kb_dispute_controls(order_id, is_moderator=True),
        )
