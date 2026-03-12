from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from app.models import get_user_by_telegram_id
from app.keyboards import kb_nav_menu_help, kb_main_menu, kb_orders_list, kb_order_detail
from app.states import CreateOrder
from app.order_repo import create_order, list_orders_for_client, get_order_for_client

router = Router()

# ---------- formatting ----------

def money_from_minor(minor: int, currency: str) -> str:
    return f"{minor / 100:.2f} {currency}"

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
        await call.answer("ÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ /start", show_alert=True)
        return
    if user.role != "client":
        await call.answer("Ð¡Ð¾Ð·Ð´Ð°Ð½Ð¸Ðµ Ð·Ð°ÐºÐ°Ð·Ð° Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ð¾ Ñ‚Ð¾Ð»ÑŒÐºÐ¾ Ð·Ð°ÐºÐ°Ð·Ñ‡Ð¸ÐºÑƒ.", show_alert=True)
        return

    await state.clear()
    await state.set_state(CreateOrder.waiting_title)
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        "Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð·Ð°ÐºÐ°Ð·Ð°:",
        reply_markup=kb_nav_menu_help(back="order:back:menu"),
    )

@router.callback_query(F.data.startswith("order:back:"))
async def create_order_back(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("ÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ /start", show_alert=True)
        return
    if user.role != "client":
        await state.clear()
        await call.message.answer("Ð¡Ð¾Ð·Ð´Ð°Ð½Ð¸Ðµ Ð·Ð°ÐºÐ°Ð·Ð° Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ð¾ Ñ‚Ð¾Ð»ÑŒÐºÐ¾ Ð·Ð°ÐºÐ°Ð·Ñ‡Ð¸ÐºÑƒ.")
        await call.answer()
        return

    action = call.data.split(":")[-1]
    await call.answer()

    if action == "menu":
        await state.clear()
        await send_clean_from_call(
            call,
            state,
            "ÐœÐµÐ½ÑŽ:",
            reply_markup=kb_main_menu(user.role),
        )
        return

    if action == "title":
        await state.set_state(CreateOrder.waiting_title)
        await send_clean_from_call(
            call,
            state,
            "Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð·Ð°ÐºÐ°Ð·Ð°:",
            reply_markup=kb_nav_menu_help(back="order:back:menu"),
        )
        return

    if action == "description":
        await state.set_state(CreateOrder.waiting_description)
        await send_clean_from_call(
            call,
            state,
            "ÐžÐ¿Ð¸ÑˆÐ¸Ñ‚Ðµ Ð·Ð°Ð´Ð°Ñ‡Ñƒ Ð¸ Ñ‚Ñ€ÐµÐ±Ð¾Ð²Ð°Ð½Ð¸Ñ (Ð¼Ð¾Ð¶Ð½Ð¾ ÑÑÑ‹Ð»ÐºÐ¾Ð¹):",
            reply_markup=kb_nav_menu_help(back="order:back:title"),
        )
        return

@router.callback_query(F.data == "order:cancel")
async def create_order_cancel(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("ÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ /start", show_alert=True)
        return

    await state.clear()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        "ÐžÐº, Ð¾Ñ‚Ð¼ÐµÐ½ÐµÐ½Ð¾.",
        reply_markup=kb_main_menu(user.role),
    )

@router.message(CreateOrder.waiting_title)
async def create_order_title(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Ð¡Ð¾Ð·Ð´Ð°Ð½Ð¸Ðµ Ð·Ð°ÐºÐ°Ð·Ð° Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ð¾ Ñ‚Ð¾Ð»ÑŒÐºÐ¾ Ð·Ð°ÐºÐ°Ð·Ñ‡Ð¸ÐºÑƒ.")
        return

    title = (message.text or "").strip()
    await safe_delete_message(message)

    if not title:
        await send_clean(
            message,
            state,
            "ÐÐ°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð½Ðµ Ð´Ð¾Ð»Ð¶Ð½Ð¾ Ð±Ñ‹Ñ‚ÑŒ Ð¿ÑƒÑÑ‚Ñ‹Ð¼. Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð·Ð°ÐºÐ°Ð·Ð°:",
            reply_markup=kb_nav_menu_help(back="order:back:menu"),
        )
        return

    await state.update_data(title=title)
    await state.set_state(CreateOrder.waiting_description)
    await send_clean(
        message,
        state,
        "ÐžÐ¿Ð¸ÑˆÐ¸Ñ‚Ðµ Ð·Ð°Ð´Ð°Ñ‡Ñƒ Ð¸ Ñ‚Ñ€ÐµÐ±Ð¾Ð²Ð°Ð½Ð¸Ñ (Ð¼Ð¾Ð¶Ð½Ð¾ ÑÑÑ‹Ð»ÐºÐ¾Ð¹):",
        reply_markup=kb_nav_menu_help(back="order:back:title"),
    )

@router.message(CreateOrder.waiting_description)
async def create_order_description(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Ð¡Ð¾Ð·Ð´Ð°Ð½Ð¸Ðµ Ð·Ð°ÐºÐ°Ð·Ð° Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ð¾ Ñ‚Ð¾Ð»ÑŒÐºÐ¾ Ð·Ð°ÐºÐ°Ð·Ñ‡Ð¸ÐºÑƒ.")
        return

    description = (message.text or "").strip()
    await safe_delete_message(message)

    if not description:
        await send_clean(
            message,
            state,
            "ÐžÐ¿Ð¸ÑÐ°Ð½Ð¸Ðµ Ð½Ðµ Ð´Ð¾Ð»Ð¶Ð½Ð¾ Ð±Ñ‹Ñ‚ÑŒ Ð¿ÑƒÑÑ‚Ñ‹Ð¼. ÐžÐ¿Ð¸ÑˆÐ¸Ñ‚Ðµ Ð·Ð°Ð´Ð°Ñ‡Ñƒ:",
            reply_markup=kb_nav_menu_help(back="order:back:title"),
        )
        return

    await state.update_data(description=description)
    await state.set_state(CreateOrder.waiting_budget)
    await send_clean(
        message,
        state,
        "Ð£ÐºÐ°Ð¶Ð¸Ñ‚Ðµ Ð±ÑŽÐ´Ð¶ÐµÑ‚ Ð² Ð´Ð¾Ð»Ð»Ð°Ñ€Ð°Ñ… (Ñ‡Ð¸ÑÐ»Ð¾). ÐÐ°Ð¿Ñ€Ð¸Ð¼ÐµÑ€: 50",
        reply_markup=kb_nav_menu_help(back="order:back:description"),
    )

@router.message(CreateOrder.waiting_budget)
async def create_order_budget(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer("Ð¡Ð¾Ð·Ð´Ð°Ð½Ð¸Ðµ Ð·Ð°ÐºÐ°Ð·Ð° Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ð¾ Ñ‚Ð¾Ð»ÑŒÐºÐ¾ Ð·Ð°ÐºÐ°Ð·Ñ‡Ð¸ÐºÑƒ.")
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    if not raw.isdigit():
        await send_clean(
            message,
            state,
            "Ð‘ÑŽÐ´Ð¶ÐµÑ‚ Ð´Ð¾Ð»Ð¶ÐµÐ½ Ð±Ñ‹Ñ‚ÑŒ Ñ‡Ð¸ÑÐ»Ð¾Ð¼. ÐÐ°Ð¿Ñ€Ð¸Ð¼ÐµÑ€: 50",
            reply_markup=kb_nav_menu_help(back="order:back:description"),
        )
        return

    data = await state.get_data()
    order_id = await create_order(
        client_id=user.id,
        title=data.get("title", ""),
        description=data.get("description", ""),
        budget_minor=int(raw) * 100,
        currency="USD",
    )

    await state.clear()
    await clear_last_bot_message(state, message.bot, message.chat.id)

    await message.answer(
        f"✅ Заказ создан. Номер: #{order_id}",
        reply_markup=kb_main_menu(user.role),
    )

@router.callback_query(F.data == "client:my_orders")
async def my_orders(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("ÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ /start", show_alert=True)
        return
    if user.role != "client":
        await call.answer("Ð Ð°Ð·Ð´ÐµÐ» Ð´Ð¾ÑÑ‚ÑƒÐ¿ÐµÐ½ Ñ‚Ð¾Ð»ÑŒÐºÐ¾ Ð·Ð°ÐºÐ°Ð·Ñ‡Ð¸ÐºÑƒ.", show_alert=True)
        return

    orders = await list_orders_for_client(user.id, limit=10)
    if not orders:
        await call.message.answer("Ð£ Ð²Ð°Ñ Ð¿Ð¾ÐºÐ° Ð½ÐµÑ‚ Ð·Ð°ÐºÐ°Ð·Ð¾Ð².", reply_markup=kb_main_menu(user.role))
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

    price = money_from_minor(int(order.get("budget_minor") or 0), order.get("currency") or "USD")
    created_at = order.get("created_at")
    created_label = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "-"

    title = order.get("title") or "-"
    description = order.get("description") or "-"
    if len(description) > 1500:
        description = description[:1497] + "..."

    text = (
        f"Заказ #{order['id']}\n\n"
        f"Название: {title}\n"
        f"Описание: {description}\n"
        f"Бюджет: {price}\n"
        f"Статус: {order.get('status')}\n"
        f"Создан: {created_label}"
    )

    await call.message.answer(text, reply_markup=kb_order_detail(order_id))
    await call.answer()
