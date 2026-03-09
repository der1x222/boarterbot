from aiogram import Router, F
from aiogram.types import Message

from app.keyboards import kb_choose_role, kb_main_menu, kb_editor_menu
from app import texts
from app.models import get_user_by_telegram_id
from app.profile_repo import get_editor_profile

router = Router()

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)

    if not user:
        await message.answer(texts.WELCOME, reply_markup=kb_choose_role())
        return

    if user.role == "editor":
        p = await get_editor_profile(user.id)
        is_verified = bool(p and p.get("verification_status") == "verified")
        await message.answer(
            "Вы уже зарегистрированы ✅",
            reply_markup=kb_editor_menu(is_verified)
        )
        return

    await message.answer(
        "Вы уже зарегистрированы ✅",
        reply_markup=kb_main_menu(user.role)
    )