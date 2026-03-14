from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import os

from app.models import get_user_by_telegram_id
from app.keyboards import (
    kb_main_menu,
    kb_editor_menu,
    kb_support,
    kb_editor_orders_list,
    kb_editor_my_orders_list,
)
from app.profile_repo import get_editor_profile
from app.order_repo import list_open_orders, list_orders_for_editor

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

async def get_menu_markup(user):
    if user.role == "editor":
        p = await get_editor_profile(user.id)
        is_verified = bool(p and p.get("verification_status") == "verified")
        return kb_editor_menu(is_verified)
    return kb_main_menu(user.role)

@router.callback_query(
    F.data.startswith(("client:", "editor:", "mod:", "common:", "deal:")) &
    ~F.data.in_(["client:profile", "editor:profile", "client:create_order", "client:my_orders"])
)
async def cb_menu(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    # ✅ "В меню"
    if call.data == "common:menu":
        await send_clean_from_call(
            call,
            state,
            "Меню:",
            reply_markup=await get_menu_markup(user),
        )
        await call.answer()
        return

    # Заглушки / проверки:
    if call.data == "common:balance":
        await send_clean_from_call(
            call,
            state,
            "💳 Баланс: скоро будет.",
            reply_markup=await get_menu_markup(user),
        )
    elif call.data == "common:vip":
        await send_clean_from_call(
            call,
            state,
            "💎 VIP: скоро будет.",
            reply_markup=await get_menu_markup(user),
        )
    elif call.data == "common:support":
        admin_username = os.getenv("ADMIN_USERNAME", "").strip()
        if admin_username:
            await send_clean_from_call(
                call,
                state,
                "🆘 Поддержка: напишите админу.",
                reply_markup=kb_support(admin_username),
            )
        else:
            await send_clean_from_call(
                call,
                state,
                "🆘 Поддержка: админ не настроен.",
                reply_markup=await get_menu_markup(user),
            )
    elif call.data == "mod:held_messages":
        await send_clean_from_call(
            call,
            state,
            "🆕 Очередь модерации: скоро будет.",
            reply_markup=await get_menu_markup(user),
        )
    elif call.data == "editor:find_orders":
        p = await get_editor_profile(user.id)
        if not p or p.get("verification_status") != "verified":
            await call.answer("⛔ Сначала пройдите верификацию.", show_alert=True)
            return
        orders = await list_open_orders(limit=10)
        if not orders:
            await send_clean_from_call(
                call,
                state,
                "🔎 Доступных заказов пока нет.",
                reply_markup=await get_menu_markup(user),
            )
        else:
            await send_clean_from_call(
                call,
                state,
                "🔎 Доступные заказы:",
                reply_markup=kb_editor_orders_list(orders),
            )
    elif call.data == "editor:my_proposals":
        orders = await list_orders_for_editor(user.id, limit=10)
        if not orders:
            await send_clean_from_call(
                call,
                state,
                "📬 Откликов пока нет.",
                reply_markup=await get_menu_markup(user),
            )
        else:
            await send_clean_from_call(
                call,
                state,
                "📬 Мои отклики:",
                reply_markup=kb_editor_my_orders_list(orders),
            )
    elif call.data == "editor:my_deals":
        orders = await list_orders_for_editor(user.id, limit=10)
        if not orders:
            await send_clean_from_call(
                call,
                state,
                "💼 Активных сделок пока нет.",
                reply_markup=await get_menu_markup(user),
            )
        else:
            await send_clean_from_call(
                call,
                state,
                "💼 Мои сделки:",
                reply_markup=kb_editor_my_orders_list(orders),
            )
    elif call.data.startswith("deal:chat"):
        await send_clean_from_call(
            call,
            state,
            "💬 Чат: скоро будет.",
            reply_markup=await get_menu_markup(user),
        )
    elif call.data.startswith("deal:change"):
        await send_clean_from_call(
            call,
            state,
            "✏️ Изменить: скоро будет.",
            reply_markup=await get_menu_markup(user),
        )
    elif call.data.startswith("deal:dispute"):
        await send_clean_from_call(
            call,
            state,
            "⚠️ Спор: скоро будет.",
            reply_markup=await get_menu_markup(user),
        )
    else:
        await send_clean_from_call(
            call,
            state,
            f"⏳ Раздел в разработке: {call.data}",
            reply_markup=await get_menu_markup(user),
        )

    await call.answer()
