from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from datetime import datetime
import re
from urllib.parse import urlparse

from app.models import get_user_by_telegram_id, get_user_by_id, list_moderators
from app.keyboards import kb_nav_menu_help, kb_orders_list, kb_order_detail, kb_deal_menu, kb_editor_order_detail, kb_deal_chat_controls, kb_dispute_join, kb_dispute_controls, kb_deal_chat_menu, kb_proposal_actions, kb_deal_chat_link_controls
from app.menu_utils import get_menu_markup_for_user
from app.states import CreateOrder, DealChange, EditOrder, EditorProposal, DealChat, DisputeChat, DisputeOpenReason, ChatRequest
from app.order_repo import create_order, list_orders_for_client, get_order_for_client, accept_order, get_order_by_id, update_order_if_open, open_dispute, set_dispute_agree, close_dispute
from app.profile_repo import get_editor_profile
from app import texts

router = Router()

def _t(user, en: str, ua: str) -> str:
    return texts.tr(getattr(user, "language", None), en, ua)

def _tl(lang: str | None, en: str, ua: str) -> str:
    return texts.tr(lang, en, ua)

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
        await call.answer(texts.tr(None, "Type /start", "Натисніть /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(texts.tr(user.language, "Only clients can create orders.", "Створення замовлення доступне лише замовнику."), show_alert=True)
        return

    await state.clear()
    await state.set_state(CreateOrder.waiting_title)
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        texts.tr(user.language, "Enter order title:", "Введіть назву замовлення:"),
        reply_markup=kb_nav_menu_help(back="order:back:menu", lang=user.language),
    )

@router.callback_query(F.data.startswith("order:back:"))
async def create_order_back(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Натисніть /start"), show_alert=True)
        return
    if user.role != "client":
        await state.clear()
        await call.message.answer(texts.tr(user.language, "Only clients can create orders.", "Створення замовлення доступне лише замовнику."))
        await call.answer()
        return

    action = call.data.split(":")[-1]
    await call.answer()

    if action == "menu":
        await state.clear()
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Menu:", "Меню:"),
            reply_markup=await get_menu_markup_for_user(user),
        )
        return

    if action == "title":
        await state.set_state(CreateOrder.waiting_title)
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Enter order title:", "Введіть назву замовлення:"),
            reply_markup=kb_nav_menu_help(back="order:back:menu", lang=user.language),
        )
        return

    if action == "description":
        await state.set_state(CreateOrder.waiting_description)
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Describe the task and requirements (you can include a link):", "Опишіть задачу і вимоги (можна з посиланням):"),
            reply_markup=kb_nav_menu_help(back="order:back:title", lang=user.language),
        )
        return

    if action == "budget":
        await state.set_state(CreateOrder.waiting_budget)
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Enter budget in USD (number). Example: 50", "Вкажіть бюджет у доларах (число). Наприклад: 50"),
            reply_markup=kb_nav_menu_help(back="order:back:description", lang=user.language),
        )
        return

    if action == "revision_price":
        await state.set_state(CreateOrder.waiting_revision_price)
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Enter revision price in USD (number). Example: 10", "Вкажіть ціну за правки (у доларах, число). Наприклад: 10"),
            reply_markup=kb_nav_menu_help(back="order:back:budget", lang=user.language),
        )
        return

@router.callback_query(F.data == "order:cancel")
async def create_order_cancel(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Натисніть /start"), show_alert=True)
        return

    await state.clear()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        texts.tr(user.language, "OK, canceled.", "Добре, скасовано."),
        reply_markup=await get_menu_markup_for_user(user),
    )

@router.message(CreateOrder.waiting_title)
async def create_order_title(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(texts.tr(user.language, "Only clients can create orders.", "Створення замовлення доступне лише замовнику."))
        return

    title = (message.text or "").strip()
    await safe_delete_message(message)

    if not title:
        await send_clean(
            message,
            state,
            texts.tr(user.language, "Title cannot be empty. Enter order title:", "Назва не повинна бути порожньою. Введіть назву замовлення:"),
            reply_markup=kb_nav_menu_help(back="order:back:menu", lang=user.language),
        )
        return

    await state.update_data(title=title)
    await state.set_state(CreateOrder.waiting_description)
    await send_clean(
        message,
        state,
        texts.tr(user.language, "Describe the task and requirements (you can include a link):", "Опишіть задачу і вимоги (можна з посиланням):"),
        reply_markup=kb_nav_menu_help(back="order:back:title", lang=user.language),
    )

@router.message(CreateOrder.waiting_description)
async def create_order_description(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(texts.tr(user.language, "Only clients can create orders.", "Створення замовлення доступне лише замовнику."))
        return

    description = (message.text or "").strip()
    await safe_delete_message(message)

    if not description:
        await send_clean(
            message,
            state,
            texts.tr(user.language, "Description cannot be empty. Describe the task:", "Опис не повинен бути порожнім. Опишіть задачу:"),
            reply_markup=kb_nav_menu_help(back="order:back:title", lang=user.language),
        )
        return

    await state.update_data(description=description)
    await state.set_state(CreateOrder.waiting_budget)
    await send_clean(
        message,
        state,
        texts.tr(user.language, "Enter budget in USD (number). Example: 50", "Вкажіть бюджет у доларах (число). Наприклад: 50"),
        reply_markup=kb_nav_menu_help(back="order:back:description", lang=user.language),
    )

@router.message(CreateOrder.waiting_budget)
async def create_order_budget(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(texts.tr(user.language, "Only clients can create orders.", "Створення замовлення доступне лише замовнику."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    if not raw.isdigit():
        await send_clean(
            message,
            state,
            texts.tr(user.language, "Budget must be a number. Example: 50", "Бюджет має бути числом. Наприклад: 50"),
            reply_markup=kb_nav_menu_help(back="order:back:description", lang=user.language),
        )
        return

    await state.update_data(budget_minor=int(raw) * 100)
    await state.set_state(CreateOrder.waiting_revision_price)
    await send_clean(
        message,
        state,
        texts.tr(user.language, "Enter revision price in USD (number). Example: 10", "Вкажіть ціну за правки (у доларах, число). Наприклад: 10"),
        reply_markup=kb_nav_menu_help(back="order:back:budget", lang=user.language),
    )

@router.message(CreateOrder.waiting_revision_price)
async def create_order_revision_price(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(texts.tr(user.language, "Only clients can create orders.", "Створення замовлення доступне лише замовнику."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    if not raw.isdigit():
        await send_clean(
            message,
            state,
            texts.tr(user.language, "Revision price must be a number. Example: 10", "Ціна за правки має бути числом. Наприклад: 10"),
            reply_markup=kb_nav_menu_help(back="order:back:budget", lang=user.language),
        )
        return

    await state.update_data(revision_price_minor=int(raw) * 100)
    await state.set_state(CreateOrder.waiting_deadline)
    await send_clean(
        message,
        state,
        texts.tr(user.language, "Enter deadline (YYYY-MM-DD HH:MM). Example: 2026-03-15 18:30", "Вкажіть дедлайн (рррр-мм-дд гг:хх). Наприклад: 2026-03-15 18:30"),
        reply_markup=kb_nav_menu_help(back="order:back:revision_price", lang=user.language),
    )

@router.message(CreateOrder.waiting_deadline)
async def create_order_deadline(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(texts.tr(user.language, "Only clients can create orders.", "Створення замовлення доступне лише замовнику."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    try:
        deadline_at = datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except ValueError:
        await send_clean(
            message,
            state,
            texts.tr(user.language, "Deadline must be in YYYY-MM-DD HH:MM format. Example: 2026-03-15 18:30", "Дедлайн має бути у форматі рррр-мм-дд гг:хх. Наприклад: 2026-03-15 18:30"),
            reply_markup=kb_nav_menu_help(back="order:back:revision_price", lang=user.language),
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
        texts.tr(user.language, f"✅ Order created. ID: #{order_id}", f"✅ Замовлення створено. Номер: #{order_id}"),
            reply_markup=await get_menu_markup_for_user(user),
    )

@router.callback_query(F.data == "client:my_orders")
async def my_orders(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Натисніть /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(texts.tr(user.language, "This section is for clients only.", "Розділ доступний лише замовнику."), show_alert=True)
        return

    orders = await list_orders_for_client(user.id, limit=10)
    if not orders:
        await call.message.answer(texts.tr(user.language, "You have no orders yet.", "У вас поки немає замовлень."), reply_markup=await get_menu_markup_for_user(user))
        await call.answer()
        return

    text = texts.tr(user.language, "Your orders:\n\nChoose an order to view.", "Ваші замовлення:\n\nОберіть замовлення для перегляду.")
    await call.message.answer(text, reply_markup=kb_orders_list(orders, user.language))
    await call.answer()

@router.callback_query(F.data.startswith("order:view:"))
async def order_view(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Натисніть /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(texts.tr(user.language, "This section is for clients only.", "Розділ доступний лише замовнику."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(texts.tr(user.language, "Invalid number.", "Некоректний номер."), show_alert=True)
        return

    order = await get_order_for_client(order_id, user.id)
    if not order:
        await call.answer(texts.tr(user.language, "Order not found.", "Замовлення не знайдено."), show_alert=True)
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
        f"{texts.tr(user.language, 'Order', 'Замовлення')} #{order['id']}\n\n"
        f"{texts.tr(user.language, 'Title', 'Назва')}: {title}\n"
        f"{texts.tr(user.language, 'Description', 'Опис')}: {description}\n"
        f"{texts.tr(user.language, 'Budget', 'Бюджет')}: {price}\n"
        f"{texts.tr(user.language, 'Revision price', 'Ціна за правки')}: {revision_price}\n"
        f"{texts.tr(user.language, 'Status', 'Статус')}: {order.get('status')}\n"
        f"{texts.tr(user.language, 'Created', 'Створено')}: {created_label}\n"
        f"{texts.tr(user.language, 'Deadline', 'Дедлайн')}: {deadline_label}"
    )

    await call.message.answer(text, reply_markup=kb_order_detail(order_id, allow_edit=allow_edit, lang=user.language))
    await call.answer()

@router.callback_query(F.data == "order_edit:cancel")
async def order_edit_cancel(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Натисніть /start"), show_alert=True)
        return
    await state.clear()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        texts.tr(user.language, "Menu:", "Меню:"),
        reply_markup=await get_menu_markup_for_user(user),
    )

@router.callback_query(F.data.startswith("order:edit:"))
async def order_edit_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Натисніть /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(texts.tr(user.language, "This section is for clients only.", "Розділ доступний лише замовнику."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(texts.tr(user.language, "Invalid number.", "Некоректний номер."), show_alert=True)
        return

    order = await get_order_for_client(order_id, user.id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await call.answer(texts.tr(user.language, "Order cannot be edited.", "Замовлення не можна редагувати."), show_alert=True)
        return

    await state.clear()
    await state.set_state(EditOrder.waiting_title)
    await state.update_data(order_id=order_id)
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        texts.tr(user.language, f"Enter new order title (current: {order.get('title') or '-'})", f"Введіть нову назву замовлення (поточна: {order.get('title') or '-'})"),
        reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
    )

@router.message(EditOrder.waiting_title)
async def order_edit_title(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(_t(user, "Only clients can create orders.", "Створення замовлення доступне лише замовнику."))
        return

    title = (message.text or "").strip()
    await safe_delete_message(message)
    if not title:
        await send_clean(
            message,
            state,
            _t(user, "Title cannot be empty.", "Назва не повинна бути порожньою."),
            reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
        )
        return

    await state.update_data(title=title)
    await state.set_state(EditOrder.waiting_description)
    await send_clean(
        message,
        state,
        _t(user, "Describe the task and requirements (you can include a link):", "Опишіть задачу і вимоги (можна з посиланням):"),
        reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
    )

@router.message(EditOrder.waiting_description)
async def order_edit_description(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(_t(user, "Only clients can create orders.", "Створення замовлення доступне лише замовнику."))
        return

    description = (message.text or "").strip()
    await safe_delete_message(message)
    if not description:
        await send_clean(
            message,
            state,
            _t(user, "Description cannot be empty.", "Опис не повинен бути порожнім."),
            reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
        )
        return

    await state.update_data(description=description)
    await state.set_state(EditOrder.waiting_budget)
    await send_clean(
        message,
        state,
        _t(user, "Enter budget in USD (number). Example: 50", "Вкажіть бюджет у доларах (число). Наприклад: 50"),
        reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
    )

@router.message(EditOrder.waiting_budget)
async def order_edit_budget(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(_t(user, "Only clients can create orders.", "Створення замовлення доступне лише замовнику."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)
    if not raw.isdigit():
        await send_clean(
            message,
            state,
            _t(user, "Budget must be a number. Example: 50", "Бюджет має бути числом. Наприклад: 50"),
            reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
        )
        return

    await state.update_data(budget_minor=int(raw) * 100)
    await state.set_state(EditOrder.waiting_revision_price)
    await send_clean(
        message,
        state,
        _t(user, "Enter revision price in USD (number). Example: 10", "Вкажіть ціну за правки (у доларах, число). Наприклад: 10"),
        reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
    )

@router.message(EditOrder.waiting_revision_price)
async def order_edit_revision_price(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(_t(user, "Only clients can create orders.", "Створення замовлення доступне лише замовнику."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)
    if not raw.isdigit():
        await send_clean(
            message,
            state,
            _t(user, "Revision price must be a number. Example: 10", "Ціна за правки має бути числом. Наприклад: 10"),
            reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
        )
        return

    await state.update_data(revision_price_minor=int(raw) * 100)
    await state.set_state(EditOrder.waiting_deadline)
    await send_clean(
        message,
        state,
        _t(user, "Enter deadline (YYYY-MM-DD HH:MM). Example: 2026-03-15 18:30", "Вкажіть дедлайн (рррр-мм-дд гг:хх). Наприклад: 2026-03-15 18:30"),
        reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
    )

@router.message(EditOrder.waiting_deadline)
async def order_edit_deadline(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(_t(user, "Only clients can create orders.", "Створення замовлення доступне лише замовнику."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    try:
        deadline_at = datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except ValueError:
        await send_clean(
            message,
            state,
            _t(user, "Deadline must be in YYYY-MM-DD HH:MM format. Example: 2026-03-15 18:30", "Дедлайн має бути у форматі рррр-мм-дд гг:хх. Наприклад: 2026-03-15 18:30"),
            reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
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
        await message.answer(_t(user, "Order cannot be edited. It may already have proposals.", "Замовлення не можна редагувати. Можливо, на нього вже відгукнулись."))
        return

    await message.answer(_t(user, "✅ Order updated.", "✅ Замовлення оновлено."), reply_markup=await get_menu_markup_for_user(user))

@router.callback_query(F.data.startswith("order:details:"))
async def order_details_for_editor(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "Натисніть /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "Доступно лише монтажерам."), show_alert=True)
        return

    p = await get_editor_profile(user.id)
    if not p or p.get("verification_status") != "verified":
        await call.answer(_t(user, "⛔ Please verify first.", "⛔ Спочатку пройдіть верифікацію."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "Некоректний номер."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await call.answer(_t(user, "Order not available.", "Замовлення недоступне."), show_alert=True)
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
        f"{_t(user, 'Order', 'Замовлення')} #{order['id']}\n\n"
        f"{_t(user, 'Title', 'Назва')}: {title}\n"
        f"{_t(user, 'Description', 'Опис')}: {description}\n"
        f"{_t(user, 'Budget', 'Бюджет')}: {price}\n"
        f"{_t(user, 'Revision price', 'Ціна за правки')}: {revision_price}\n"
        f"{_t(user, 'Created', 'Створено')}: {created_label}\n"
        f"{_t(user, 'Deadline', 'Дедлайн')}: {deadline_label}"
    )

    await call.message.answer(text, reply_markup=kb_editor_order_detail(order_id, user.language))
    await call.answer()


@router.callback_query(F.data.startswith("order:chat:"))
async def order_chat_request(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "Натисніть /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "Доступно лише монтажерам."), show_alert=True)
        return

    p = await get_editor_profile(user.id)
    if not p or p.get("verification_status") != "verified":
        await call.answer(_t(user, "⛔ Please verify first.", "⛔ Спочатку пройдіть верифікацію."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "Некоректний номер."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await call.answer(_t(user, "Order not available.", "Замовлення недоступне."), show_alert=True)
        return

    await state.clear()
    await state.set_state(ChatRequest.waiting_text)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(_t(user, "Write a chat request to the client:", "Напишіть текст запиту на чат для замовника:"))

@router.message(ChatRequest.waiting_text)
async def order_chat_request_text(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer(_t(user, "Editors only.", "Доступно лише монтажерам."))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer(_t(user, "Text cannot be empty.", "Текст не повинен бути порожнім."))
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await state.clear()
        await message.answer(_t(user, "Order not available.", "Замовлення недоступне."))
        return

    client = await get_user_by_id(int(order['client_id']))
    if client:
        editor_name = user.display_name or user.username or f"id:{user.telegram_id}"
        editor_username = f"@{user.username}" if user.username else ""
        await message.bot.send_message(
            client.telegram_id,
            _t(client, f"Chat request for order #{order_id} from {editor_name} {editor_username}:\n{text}", f"Запит на чат по замовленню #{order_id} від {editor_name} {editor_username}:\n{text}"),
        )

    await state.clear()
    await message.answer(_t(user, "Request sent to the client.", "Запит надіслано замовнику."))

@router.callback_query(F.data.startswith("order:proposal:"))
async def order_proposal_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "Натисніть /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "Доступно лише монтажерам."), show_alert=True)
        return

    p = await get_editor_profile(user.id)
    if not p or p.get("verification_status") != "verified":
        await call.answer(_t(user, "⛔ Please verify first.", "⛔ Спочатку пройдіть верифікацію."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "Некоректний номер."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await call.answer(_t(user, "Order not available.", "Замовлення недоступне."), show_alert=True)
        return

    await state.clear()
    await state.set_state(EditorProposal.waiting_price)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(_t(user, "Enter your price in USD (number). Example: 80", "Вкажіть вашу ціну в доларах (число). Наприклад: 80"))

@router.message(EditorProposal.waiting_price)
async def order_proposal_price(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer(_t(user, "Editors only.", "Доступно лише монтажерам."))
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer(_t(user, "Price must be a number. Example: 80", "Ціна має бути числом. Наприклад: 80"))
        return

    await state.update_data(proposal_price=int(raw) * 100)
    await state.set_state(EditorProposal.waiting_comment)
    await message.answer(_t(user, "Short comment for the proposal (single message).", "Короткий коментар до пропозиції (можна одним повідомленням)."))

@router.message(EditorProposal.waiting_comment)
async def order_proposal_comment(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer(_t(user, "Editors only.", "Доступно лише монтажерам."))
        return

    comment = (message.text or "").strip()
    if not comment:
        await message.answer(_t(user, "Write a short comment.", "Напишіть короткий коментар."))
        return

    data = await state.get_data()
    order_id = int(data.get('order_id') or 0)
    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await state.clear()
        await message.answer(_t(user, "Order not available.", "Замовлення недоступне."))
        return

    client = await get_user_by_id(int(order['client_id']))
    if client:
        price = f"{int(data.get('proposal_price') or 0) / 100:.2f} {order.get('currency') or 'USD'}"
        editor_name = user.display_name or user.username or f"id:{user.telegram_id}"
        editor_username = f"@{user.username}" if user.username else ""
        await message.bot.send_message(
            client.telegram_id,
            _t(client, f"Proposal for order #{order_id} from {editor_name} {editor_username}:\n", f"Пропозиція по замовленню #{order_id} від {editor_name} {editor_username}:\n")
            + _t(client, f"Price: {price}\n", f"Ціна: {price}\n")
            + _t(client, f"Comment: {comment}", f"Коментар: {comment}"),
            reply_markup=kb_proposal_actions(order_id, user.id, client.language),
        )

    await state.clear()
    await message.answer(_t(user, "Proposal sent to the client.", "Пропозицію надіслано замовнику."))

@router.callback_query(F.data.startswith("proposal:accept:"))
async def proposal_accept(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "Натисніть /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(_t(user, "Clients only.", "Доступно лише замовнику."), show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer(_t(user, "Invalid data.", "Невірні дані."), show_alert=True)
        return

    try:
        order_id = int(parts[2])
        editor_id = int(parts[3])
    except ValueError:
        await call.answer(_t(user, "Invalid data.", "Невірні дані."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("client_id") != user.id:
        await call.answer(_t(user, "Order not found.", "Замовлення не знайдено."), show_alert=True)
        return
    if order.get("status") != "open" or order.get("editor_id"):
        await call.answer(_t(user, "Order not available.", "Замовлення недоступне."), show_alert=True)
        return

    ok = await accept_order(order_id, editor_id)
    if not ok:
        await call.answer(_t(user, "Failed to accept the order.", "Не вдалося прийняти замовлення."), show_alert=True)
        return

    editor = await get_user_by_id(editor_id)
    if editor:
        await call.bot.send_message(
            editor.telegram_id,
            _t(editor, f"Order #{order_id} accepted by the client.", f"Замовлення #{order_id} прийнято замовником."),
            reply_markup=kb_deal_menu(order_id, editor.language),
        )

    await call.answer(_t(user, "Order accepted.", "Замовлення прийнято."), show_alert=True)

@router.callback_query(F.data.startswith("proposal:reject:"))
async def proposal_reject(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "Натисніть /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(_t(user, "Clients only.", "Доступно лише замовнику."), show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer(_t(user, "Invalid data.", "Невірні дані."), show_alert=True)
        return

    try:
        order_id = int(parts[2])
        editor_id = int(parts[3])
    except ValueError:
        await call.answer(_t(user, "Invalid data.", "Невірні дані."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("client_id") != user.id:
        await call.answer(_t(user, "Order not found.", "Замовлення не знайдено."), show_alert=True)
        return

    editor = await get_user_by_id(editor_id)
    if editor:
        await call.bot.send_message(editor.telegram_id, _t(editor, f"Client rejected your proposal for order #{order_id}.", f"Замовник відхилив пропозицію по замовленню #{order_id}."))

    await call.answer(_t(user, "Rejected.", "Відхилено."), show_alert=True)

@router.callback_query(F.data.startswith("proposal:chat:"))
async def proposal_chat(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(_t(user, "Clients only.", "???????? ???? ?????????."), show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer(_t(user, "Invalid data.", "??????? ????."), show_alert=True)
        return

    try:
        order_id = int(parts[2])
        editor_id = int(parts[3])
    except ValueError:
        await call.answer(_t(user, "Invalid data.", "??????? ????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("client_id") != user.id:
        await call.answer(_t(user, "Order not found.", "?????????? ?? ????????."), show_alert=True)
        return

    editor = await get_user_by_id(editor_id)
    if editor:
        client_name = user.display_name or user.username or f"id:{user.telegram_id}"
        client_username = f"@{user.username}" if user.username else ""
        await call.bot.send_message(
            editor.telegram_id,
            _t(
                editor,
                f"Client {client_name} {client_username} wants to start a chat about order #{order_id}.",
                f"???????? {client_name} {client_username} ???? ?????? ??? ?? ?????????? #{order_id}.",
            ),
        )

    await call.answer(_t(user, "Request sent to the editor.", "????? ????????? ?????????."), show_alert=True)

@router.callback_query(F.data.startswith("deal:change:"))
async def deal_change_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "???????? ???? ??????????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id:
        await call.answer(_t(user, "Order not found.", "?????????? ?? ????????."), show_alert=True)
        return

    await state.clear()
    await state.set_state(DealChange.waiting_text)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(_t(user, "Describe what needs to be changed:", "??????? ?? ???????? ???????:"))

@router.message(DealChange.waiting_text)
async def deal_change_submit(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer(_t(user, "Editors only.", "???????? ???? ??????????."))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer(_t(user, "Describe what needs to be changed.", "??????? ?? ???????? ???????."))
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id:
        await state.clear()
        await message.answer(_t(user, "Order not found.", "?????????? ?? ????????."))
        return

    client = await get_user_by_id(int(order["client_id"]))
    if client:
        await message.bot.send_message(
            client.telegram_id,
            _t(
                    client,
                    f"Change request for order #{order_id}:\n{text}",
                    f"Запит на зміну по замовленню #{order_id}:\n{text}",
                ),
        )

    await state.clear()
    await message.answer(_t(user, "Sent to the client.", "????????? ?????????."))

@router.callback_query(F.data.startswith("order:menu:"))
async def order_menu_open(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "???????? ???? ??????????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id:
        await call.answer(_t(user, "Order not found.", "?????????? ?? ????????."), show_alert=True)
        return

    await call.message.answer(_t(user, "Order menu:", "???? ??????????:"), reply_markup=kb_deal_menu(order_id, user.language))
    await call.answer()

# ---------- deal chat & dispute ----------

_LINK_RE = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/|bit\.ly/|goo\.gl/|drive\.google\.com/|docs\.google\.com/|dropbox\.com/|mega\.nz/|onedrive\.live\.com/)",
    re.IGNORECASE,
)
_ALLOWED_LINK_HOSTS = {
    "drive.google.com",
    "docs.google.com",
    "dropbox.com",
    "www.dropbox.com",
    "mega.nz",
    "onedrive.live.com",
}

def _message_has_link(message: Message, text: str) -> bool:
    if message.entities:
        for ent in message.entities:
            if ent.type in ("url", "text_link"):
                return True
    return bool(_LINK_RE.search(text))

def _extract_urls(message: Message, text: str) -> list[str]:
    urls: list[str] = []
    if message.entities:
        for ent in message.entities:
            if ent.type == "text_link" and ent.url:
                urls.append(ent.url)
            elif ent.type == "url":
                urls.append(text[ent.offset : ent.offset + ent.length])
    if not urls:
        # Fallback for raw text without entities
        urls.extend(re.findall(r"(https?://\S+|www\.\S+)", text))
    return urls

def _is_allowed_link(url: str) -> bool:
    candidate = url.strip()
    if candidate.startswith("www."):
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    return host in _ALLOWED_LINK_HOSTS

def _user_label(user) -> str:
    name = user.display_name or user.username or f"id:{user.telegram_id}"
    username = f"@{user.username}" if user.username else ""
    return f"{name} {username}".strip()

async def _activate_deal_chat_for_user(
    state: FSMContext,
    bot,
    telegram_id: int,
    order_id: int,
) -> None:
    # Ensure recipient can reply without manually starting the chat
    key = StorageKey(
        bot_id=bot.id,
        chat_id=telegram_id,
        user_id=telegram_id,
    )
    ctx = FSMContext(storage=state.storage, key=key)
    await ctx.set_state(DealChat.chatting)
    await ctx.update_data(order_id=order_id)

@router.callback_query(F.data.startswith("deal:menu:"))
async def deal_menu_open(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    await call.answer()
    await call.message.answer(_t(user, "Order menu:", "???? ??????????:"), reply_markup=kb_deal_menu(order_id, user.language))

@router.callback_query(F.data.startswith("deal:chat:exit:"))
async def deal_chat_exit(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    await state.clear()
    await call.answer()
    await call.message.answer(_t(user, "Chat closed.", "??? ???????."), reply_markup=kb_deal_chat_menu(order_id, user.language))

@router.callback_query(F.data.startswith("deal:chat:start:"))
async def deal_chat_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await call.answer(_t(user, "Deal not found.", "????? ?? ????????."), show_alert=True)
        return

    if order.get("status") == "dispute":
        await call.answer(_t(user, "Dispute is active. Go to the dispute.", "???? ????????. ????????? ? ????."), show_alert=True)
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    await state.clear()
    await state.set_state(DealChat.chatting)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(
            _t(
                recipient,
                f"Chat for order #{order_id} from {_user_label(user)}\n{text}",
                f"Чат по замовленню #{order_id} від {_user_label(user)}\n{text}",
            ),
        reply_markup=kb_deal_chat_controls(order_id, user.language),
    )

@router.callback_query(F.data.startswith("deal:chat:link:"))
async def deal_chat_link_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await call.answer(_t(user, "Deal not found.", "????? ?? ????????."), show_alert=True)
        return

    if order.get("status") == "dispute":
        await call.answer(_t(user, "Dispute is active. Go to the dispute.", "???? ????????. ????????? ? ????."), show_alert=True)
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    await state.clear()
    await state.set_state(DealChat.waiting_link)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(
        _t(
            user,
            f"Send a link for order #{order_id} in one message.\n"
            "Hint: you can send links only to Google Drive, Dropbox, OneDrive, Mega.",
            f"\u041d\u0430\u0434\u0456\u0441\u043b\u0456\u0442\u044c \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043f\u043e \u0437\u0430\u043c\u043e\u0432\u043b\u0435\u043d\u043d\u044e #{order_id} \u043e\u0434\u043d\u0438\u043c \u043f\u043e\u0432\u0456\u0434\u043e\u043c\u043b\u0435\u043d\u043d\u044f\u043c.\n"
            "\u041f\u0456\u0434\u043a\u0430\u0437\u043a\u0430: \u043c\u043e\u0436\u043d\u0430 \u043d\u0430\u0434\u0441\u0438\u043b\u0430\u0442\u0438 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043b\u0438\u0448\u0435 \u043d\u0430 Google Drive, Dropbox, OneDrive, Mega.",
        ),
        reply_markup=kb_deal_chat_link_controls(order_id, user.language),
    )

@router.callback_query(F.data.startswith("deal:chat:"))
async def deal_chat_menu(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 3:
        return

    try:
        order_id = int(parts[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    await call.answer()
    await call.message.answer(_t(user, "Chat menu:", "???? ????:"), reply_markup=kb_deal_chat_menu(order_id, user.language))

@router.message(DealChat.waiting_link)
async def deal_chat_link_message(message: Message, state: FSMContext):
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
        await message.answer(_t(user, "Deal not found.", "????? ?? ????????."))
        return

    if order.get("status") == "dispute":
        await message.answer(_t(user, "Dispute is active. Go to the dispute.", "???? ????????. ????????? ? ????."))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer(_t(user, "Send the link as a single text message.", "????????? ????????? ????? ????????? ?????????????."))
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")):
        await message.answer(_t(user, "No access.", "????? ???????."))
        return

    if not _message_has_link(message, text):
        await message.answer(
            _t(
                user,
                "This doesn't look like a link. Send the full link.\n"
                "Hint: you can send links only to Google Drive, Dropbox, OneDrive, Mega.",
                "\u0426\u0435 \u043d\u0435 \u0441\u0445\u043e\u0436\u0435 \u043d\u0430 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f. \u041d\u0430\u0434\u0456\u0441\u043b\u0456\u0442\u044c \u043f\u043e\u0432\u043d\u0435 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f.\n"
                "\u041f\u0456\u0434\u043a\u0430\u0437\u043a\u0430: \u043c\u043e\u0436\u043d\u0430 \u043d\u0430\u0434\u0441\u0438\u043b\u0430\u0442\u0438 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043b\u0438\u0448\u0435 \u043d\u0430 Google Drive, Dropbox, OneDrive, Mega.",
            ),
            reply_markup=kb_deal_chat_link_controls(order_id, user.language),
        )
        return

    urls = _extract_urls(message, text)
    if not urls or any(not _is_allowed_link(u) for u in urls):
        await message.answer(
            _t(
                user,
                "Link must be from an allowed service.\n"
                "Allowed: Google Drive, Dropbox, OneDrive, Mega.",
                "\u041f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043c\u0430\u0454 \u0431\u0443\u0442\u0438 \u0437 \u0434\u043e\u0437\u0432\u043e\u043b\u0435\u043d\u043e\u0433\u043e \u0441\u0435\u0440\u0432\u0456\u0441\u0443.\n"
                "\u0414\u043e\u0437\u0432\u043e\u043b\u0435\u043d\u0456: Google Drive, Dropbox, OneDrive, Mega.",
            ),
            reply_markup=kb_deal_chat_link_controls(order_id, user.language),
        )
        return

    recipient_id = order.get("editor_id") if user.id == order.get("client_id") else order.get("client_id")
    recipient = await get_user_by_id(int(recipient_id))
    if recipient:
        await message.bot.send_message(
            recipient.telegram_id,
            _t(
                recipient,
                f"Link for order #{order_id} from {_user_label(user)}\n{text}",
                f"Посилання по замовленню #{order_id} від {_user_label(user)}\n{text}",
            ),
            reply_markup=kb_deal_chat_controls(order_id, recipient.language),
        )
        await _activate_deal_chat_for_user(state, message.bot, recipient.telegram_id, order_id)

    await state.set_state(DealChat.chatting)
    await message.answer(_t(user, "Link sent.", "????????? ?????????."), reply_markup=kb_deal_chat_controls(order_id, user.language))

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
        await message.answer(_t(user, "Deal not found.", "????? ?? ????????."))
        return

    if order.get("status") == "dispute":
        await message.answer(_t(user, "Dispute is active. Go to the dispute.", "???? ????????. ????????? ? ????."))
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")):
        await message.answer(_t(user, "No access.", "????? ???????."))
        return

    text = (message.text or "").strip()
    if not text:
        return

    if _message_has_link(message, text):
        await message.answer(
            _t(
                user,
                "Links are not allowed in chat. Use the Send link menu.\n"
                "Hint: you can send links only to Google Drive, Dropbox, OneDrive, Mega.",
                "\u041f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u0432 \u0447\u0430\u0442\u0456 \u0437\u0430\u0431\u043e\u0440\u043e\u043d\u0435\u043d\u0456. \u0412\u0438\u043a\u043e\u0440\u0438\u0441\u0442\u043e\u0432\u0443\u0439\u0442\u0435 \u043c\u0435\u043d\u044e \u041d\u0430\u0434\u0456\u0441\u043b\u0430\u0442\u0438 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f.\n"
                "\u041f\u0456\u0434\u043a\u0430\u0437\u043a\u0430: \u043c\u043e\u0436\u043d\u0430 \u043d\u0430\u0434\u0441\u0438\u043b\u0430\u0442\u0438 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043b\u0438\u0448\u0435 \u043d\u0430 Google Drive, Dropbox, OneDrive, Mega.",
            ),
            reply_markup=kb_deal_chat_controls(order_id, user.language),
        )
        return

    recipient_id = order.get("editor_id") if user.id == order.get("client_id") else order.get("client_id")
    recipient = await get_user_by_id(int(recipient_id))
    if recipient:
        await message.bot.send_message(
            recipient.telegram_id,
            _t(
                recipient,
                f"Chat for order #{order_id} from {_user_label(user)}\n{text}",
                f"Чат по замовленню #{order_id} від {_user_label(user)}\n{text}",
            ),
            reply_markup=kb_deal_chat_controls(order_id, recipient.language),
        )
        await _activate_deal_chat_for_user(state, message.bot, recipient.telegram_id, order_id)

@router.callback_query(F.data.startswith("deal:dispute:exit:"))
async def dispute_exit(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    await state.clear()
    await call.answer()
    await call.message.answer(_t(user, "You left the dispute.", "?? ?????? ?? ?????."), reply_markup=kb_deal_menu(order_id, user.language))

@router.callback_query(F.data.startswith("deal:dispute:join:"))
async def dispute_join(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("status") != "dispute":
        await call.answer(_t(user, "Dispute is not active.", "???? ?? ????????."), show_alert=True)
        return

    if user.role != "moderator" and user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    await state.clear()
    await state.set_state(DisputeChat.chatting)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(
        _t(
            user,
            "Dispute opened. Final decision is made by a moderator.\n"
            "The dispute can be closed by a moderator or if both parties agree.",
            "\u0421\u043f\u0456\u0440 \u0432\u0456\u0434\u043a\u0440\u0438\u0442\u043e. \u041e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u0435 \u0440\u0456\u0448\u0435\u043d\u043d\u044f \u043f\u0440\u0438\u0439\u043c\u0430\u0454 \u043c\u043e\u0434\u0435\u0440\u0430\u0442\u043e\u0440.\n"
            "\u0421\u043f\u0456\u0440 \u043c\u043e\u0436\u0435 \u0437\u0430\u043a\u0440\u0438\u0442\u0438 \u043c\u043e\u0434\u0435\u0440\u0430\u0442\u043e\u0440 \u0430\u0431\u043e \u044f\u043a\u0449\u043e \u043e\u0431\u0438\u0434\u0432\u0456 \u0441\u0442\u043e\u0440\u043e\u043d\u0438 \u043f\u043e\u0433\u043e\u0434\u044f\u0442\u044c\u0441\u044f.",
        ),
        reply_markup=kb_dispute_controls(order_id, is_moderator=(user.role == "moderator"), lang=user.language),
    )

@router.callback_query(F.data.startswith("deal:dispute:agree:"))
async def dispute_agree(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role not in ("client", "editor"):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("status") != "dispute":
        await call.answer(_t(user, "Dispute is not active.", "???? ?? ????????."), show_alert=True)
        return

    client_agree, editor_agree = await set_dispute_agree(order_id, user.role)
    await call.answer(_t(user, "Marked.", "?????????."), show_alert=True)

    if client_agree and editor_agree:
        await close_dispute(order_id)
        client = await get_user_by_id(int(order["client_id"]))
        editor = await get_user_by_id(int(order["editor_id"]))
        moderators = await list_moderators()
        if client:
            await call.bot.send_message(
                client.telegram_id,
                _t(client, f"Dispute for order #{order_id} closed by agreement.", f"???? ?? ?????????? #{order_id} ??????? ?? ?????? ??????."),
            )
        if editor:
            await call.bot.send_message(
                editor.telegram_id,
                _t(editor, f"Dispute for order #{order_id} closed by agreement.", f"???? ?? ?????????? #{order_id} ??????? ?? ?????? ??????."),
            )
        for m in moderators:
            await call.bot.send_message(
                m.telegram_id,
                _t(m, f"Dispute for order #{order_id} closed by agreement.", f"???? ?? ?????????? #{order_id} ??????? ?? ?????? ??????."),
            )

@router.callback_query(F.data.startswith("deal:dispute:close:"))
async def dispute_close(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "moderator":
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    ok = await close_dispute(order_id)
    if not ok:
        await call.answer(_t(user, "Dispute is not active.", "???? ?? ????????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    client = await get_user_by_id(int(order["client_id"])) if order else None
    editor = await get_user_by_id(int(order["editor_id"])) if order else None
    moderators = await list_moderators()
    if client:
        await call.bot.send_message(
            client.telegram_id,
            _t(client, f"Dispute for order #{order_id} closed by moderator.", f"???? ?? ?????????? #{order_id} ??????? ???????????."),
        )
    if editor:
        await call.bot.send_message(
            editor.telegram_id,
            _t(editor, f"Dispute for order #{order_id} closed by moderator.", f"???? ?? ?????????? #{order_id} ??????? ???????????."),
        )
    for m in moderators:
        await call.bot.send_message(
            m.telegram_id,
            _t(m, f"Dispute for order #{order_id} closed by moderator.", f"???? ?? ?????????? #{order_id} ??????? ???????????."),
        )

@router.callback_query(F.data.startswith("deal:dispute:"))
async def dispute_open(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 3:
        return

    try:
        order_id = int(parts[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await call.answer(_t(user, "Deal not found.", "????? ?? ????????."), show_alert=True)
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    if order.get("status") == "dispute":
        await call.answer(_t(user, "Dispute is already active.", "???? ??? ????????."), show_alert=True)
        return

    await state.clear()
    await state.set_state(DisputeOpenReason.waiting_text)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(_t(user, "Describe the dispute reason in one message.", "??????? ??????? ????? ????? ?????????????."))

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
        await message.answer(_t(user, "Reason cannot be empty.", "Причина не повинна бути порожньою."))
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await state.clear()
        await message.answer(_t(user, "Deal not found.", "Угоду не знайдено."))
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")):
        await state.clear()
        await message.answer(_t(user, "No access.", "Немає доступу."))
        return

    ok = await open_dispute(order_id, user.id)
    if not ok:
        await state.clear()
        await message.answer(_t(user, "Failed to open dispute.", "Не вдалося відкрити спір."))
        return

    await state.clear()
    await state.set_state(DisputeChat.chatting)
    await state.update_data(order_id=order_id)

    warning_en = (
        "Attention! The deal is frozen until the dispute is resolved.\n"
        "Final decision is made by a moderator.\n"
        "The dispute can be closed by a moderator or if both parties agree."
    )
    warning_ua = (
        "\u0423\u0432\u0430\u0433\u0430! \u0423\u0433\u043e\u0434\u0443 \u0437\u0430\u043c\u043e\u0440\u043e\u0436\u0435\u043d\u043e \u0434\u043e \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043d\u044f \u0441\u043f\u043e\u0440\u0443.\n"
        "\u041e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u0435 \u0440\u0456\u0448\u0435\u043d\u043d\u044f \u043f\u0440\u0438\u0439\u043c\u0430\u0454 \u043c\u043e\u0434\u0435\u0440\u0430\u0442\u043e\u0440.\n"
        "\u0421\u043f\u0456\u0440 \u043c\u043e\u0436\u0435 \u0437\u0430\u043a\u0440\u0438\u0442\u0438 \u043c\u043e\u0434\u0435\u0440\u0430\u0442\u043e\u0440 \u0430\u0431\u043e \u044f\u043a\u0449\u043e \u043e\u0431\u0438\u0434\u0432\u0456 \u0441\u0442\u043e\u0440\u043e\u043d\u0438 \u043f\u043e\u0433\u043e\u0434\u044f\u0442\u044c\u0441\u044f."
    )
    warning = _t(user, warning_en, warning_ua)

    client = await get_user_by_id(int(order["client_id"]))
    editor = await get_user_by_id(int(order["editor_id"]))
    moderators = await list_moderators()

    if client and client.telegram_id != message.from_user.id:
        await message.bot.send_message(
            client.telegram_id,
            _t(client, warning_en, warning_ua),
            reply_markup=kb_dispute_join(order_id, lang=client.language),
        )
    if editor and editor.telegram_id != message.from_user.id:
        await message.bot.send_message(
            editor.telegram_id,
            _t(editor, warning_en, warning_ua),
            reply_markup=kb_dispute_join(order_id, lang=editor.language),
        )
    for m in moderators:
        await message.bot.send_message(
            m.telegram_id,
            _t(m, f"Dispute for order #{order_id} opened. Reason: {reason}", f"Спір по замовленню #{order_id} відкрито. Причина: {reason}"),
            reply_markup=kb_dispute_join(order_id, lang=m.language),
        )

    await message.answer(warning, reply_markup=kb_dispute_controls(order_id, is_moderator=False, lang=user.language))

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
        await message.answer(_t(user, "Dispute is not active.", "Спір не активний."))
        return

    if user.role != "moderator" and user.id not in (order.get("client_id"), order.get("editor_id")):
        await message.answer(_t(user, "No access.", "Немає доступу."))
        return

    text = (message.text or "").strip()
    if not text:
        return

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
            prefix = _t(u, f"DISPUTE #{order_id} from {_user_label(user)}\n", f"СПІР #{order_id} від {_user_label(user)}\n")
            await message.bot.send_message(
                u.telegram_id,
                prefix + text,
                reply_markup=kb_dispute_controls(order_id, is_moderator=False, lang=u.language),
            )

    for m in moderators:
        if m.id == user.id:
            continue
        prefix = _t(m, f"DISPUTE #{order_id} from {_user_label(user)}\n", f"СПІР #{order_id} від {_user_label(user)}\n")
        await message.bot.send_message(
            m.telegram_id,
            prefix + text,
            reply_markup=kb_dispute_controls(order_id, is_moderator=True, lang=m.language),
        )
