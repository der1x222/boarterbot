from aiogram import Router, F
from aiogram.types import Message

from app.keyboards import kb_choose_role
from app.menu_utils import get_menu_markup_for_user
from app import texts
from app.models import get_user_by_telegram_id

router = Router()

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)

    if not user:
        await message.answer(texts.WELCOME, reply_markup=kb_choose_role())
        return

    if user.role == "editor":
        await message.answer(
            "Вы уже зарегистрированы ✅",
            reply_markup=await get_menu_markup_for_user(user)
        )
        return

    await message.answer(
        "Вы уже зарегистрированы ✅",
        reply_markup=await get_menu_markup_for_user(user)
    )
