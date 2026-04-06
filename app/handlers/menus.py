from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import os

from app.models import get_user_by_telegram_id
from app.menu_utils import get_menu_markup_for_user
from app.keyboards import (
    kb_support,
    kb_editor_orders_list,
    kb_editor_my_orders_list,
)
from app.profile_repo import get_editor_profile
from app.order_repo import list_open_orders, list_orders_for_editor
from app import texts

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

@router.callback_query(
    F.data.startswith(("client:", "editor:", "common:")) &
    ~F.data.in_(["client:profile", "editor:profile", "client:create_order", "client:my_orders", "common:settings"])
)
async def cb_menu(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Натисніть /start"), show_alert=True)
        return

    # ✅ "В меню"
    if call.data == "common:menu":
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Menu:", "Меню:"),
            reply_markup=await get_menu_markup_for_user(user),
        )
        await call.answer()
        return

    # Заглушки / проверки:
    if call.data == "common:balance":
            await send_clean_from_call(
                call,
                state,
                texts.tr(user.language, "💳 Balance: coming soon.", "💳 Баланс: скоро буде."),
                reply_markup=await get_menu_markup_for_user(user),
            )
    elif call.data == "common:vip":
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "💎 VIP: coming soon.", "💎 VIP: скоро буде."),
            reply_markup=await get_menu_markup_for_user(user),
        )
    elif call.data == "common:support":
        admin_username = os.getenv("ADMIN_USERNAME", "").strip()
        if admin_username:
            await send_clean_from_call(
                call,
                state,
                texts.tr(user.language, "🆘 Support: message the admin.", "🆘 Підтримка: напишіть адміну."),
                reply_markup=kb_support(admin_username, user.language),
            )
        else:
            await send_clean_from_call(
                call,
                state,
                texts.tr(user.language, "🆘 Support: admin is not configured.", "🆘 Підтримка: адмін не налаштований."),
                reply_markup=await get_menu_markup_for_user(user),
            )
    elif call.data == "editor:find_orders":
        p = await get_editor_profile(user.id)
        if not p or p.get("verification_status") != "verified":
            await call.answer(texts.tr(user.language, "⛔ Please verify first.", "⛔ Спочатку пройдіть верифікацію."), show_alert=True)
            return
        orders = await list_open_orders(limit=10)
        if not orders:
            await send_clean_from_call(
                call,
                state,
                texts.tr(user.language, "🔎 No available orders yet.", "🔎 Доступних замовлень поки немає."),
                reply_markup=await get_menu_markup_for_user(user),
            )
        else:
            await send_clean_from_call(
                call,
                state,
                texts.tr(user.language, "🔎 Available orders:", "🔎 Доступні замовлення:"),
                reply_markup=kb_editor_orders_list(orders, user.language),
            )
    elif call.data == "editor:my_proposals":
        orders = await list_orders_for_editor(user.id, limit=10)
        if not orders:
            await send_clean_from_call(
                call,
                state,
                texts.tr(user.language, "📬 No proposals yet.", "📬 Відгуків поки немає."),
                reply_markup=await get_menu_markup_for_user(user),
            )
        else:
            await send_clean_from_call(
                call,
                state,
                texts.tr(user.language, "📬 My proposals:", "📬 Мої відгуки:"),
                reply_markup=kb_editor_my_orders_list(orders, user.language),
            )
    elif call.data == "editor:my_deals":
        orders = await list_orders_for_editor(user.id, limit=10)
        if not orders:
            await send_clean_from_call(
                call,
                state,
                texts.tr(user.language, "💼 No active deals yet.", "💼 Активних угод поки немає."),
                reply_markup=await get_menu_markup_for_user(user),
            )
        else:
            await send_clean_from_call(
                call,
                state,
                texts.tr(user.language, "💼 My deals:", "💼 Мої угоди:"),
                reply_markup=kb_editor_my_orders_list(orders, user.language),
            )
    else:
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, f"⏳ In development: {call.data}", f"⏳ Розділ у розробці: {call.data}"),
            reply_markup=await get_menu_markup_for_user(user),
        )

    await call.answer()
