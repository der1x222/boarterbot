from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.models import get_user_by_telegram_id
from app.keyboards import kb_main_menu, kb_editor_menu
from app.profile_repo import get_editor_profile

router = Router()

@router.callback_query(
    F.data.startswith(("client:", "editor:", "mod:", "common:")) &
    ~F.data.in_(["client:profile", "editor:profile", "client:create_order", "client:my_orders"])
)
async def cb_menu(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    # ✅ "В меню"
    if call.data == "common:menu":
        if user.role == "editor":
            p = await get_editor_profile(user.id)
            is_verified = bool(p and p.get("verification_status") == "verified")
            await call.message.answer("Меню:", reply_markup=kb_editor_menu(is_verified))
        else:
            await call.message.answer("Меню:", reply_markup=kb_main_menu(user.role))
        await call.answer()
        return

    # Заглушки / проверки:
    if call.data == "common:balance":
        await call.message.answer("💳 Баланс: скоро будет.")
    elif call.data == "common:support":
        await call.message.answer("🆘 Поддержка: скоро будет.")
    elif call.data == "mod:held_messages":
        await call.message.answer("🆕 Очередь модерации: скоро будет.")
    elif call.data == "editor:find_orders":
        p = await get_editor_profile(user.id)
        if not p or p.get("verification_status") != "verified":
            await call.answer("⛔ Сначала пройдите верификацию.", show_alert=True)
            return
        await call.message.answer("🔎 Поиск заказов: скоро будет.")
    else:
        await call.message.answer(f"⏳ Раздел в разработке: {call.data}")

    # Показать меню снова
    if user.role == "editor":
        p = await get_editor_profile(user.id)
        is_verified = bool(p and p.get("verification_status") == "verified")
        await call.message.answer("Меню:", reply_markup=kb_editor_menu(is_verified))
    else:
        await call.message.answer("Меню:", reply_markup=kb_main_menu(user.role))

    await call.answer()
