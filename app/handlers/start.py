from aiogram import Router, F
from aiogram.types import Message

from app.keyboards import kb_choose_role, kb_language_start
from app.menu_utils import get_menu_markup_for_user
from app import texts
from app.models import get_user_by_telegram_id

router = Router()

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)

    if not user:
        await message.answer(texts.t("choose_language", "en"), reply_markup=kb_language_start())
        return

    if user.role == "editor":
        await message.answer(
            texts.t("already_registered", user.language),
            reply_markup=await get_menu_markup_for_user(user)
        )
        return

    await message.answer(
        texts.t("already_registered", user.language),
        reply_markup=await get_menu_markup_for_user(user)
    )
