from aiogram import Router, F
from aiogram.types import CallbackQuery

from app import texts
from app.models import get_user_by_telegram_id, upsert_user
from app.keyboards import kb_settings_menu, kb_choose_role

router = Router()


@router.callback_query(F.data == "common:settings")
async def open_settings(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    lang = texts.normalize_lang(user.language)
    text = f"{texts.t('settings_title', lang)}\n\n{texts.t('settings_text', lang)}"
    try:
        await call.message.edit_text(text, reply_markup=kb_settings_menu(user.role, lang))
    except:
        await call.message.answer(text, reply_markup=kb_settings_menu(user.role, lang))
    await call.answer()


@router.callback_query(F.data.startswith("lang:set:"))
async def set_language(call: CallbackQuery):
    lang = texts.normalize_lang(call.data.split(":")[-1])
    user = await get_user_by_telegram_id(call.from_user.id)

    if not user:
        text = texts.t("welcome", lang)
        try:
            await call.message.edit_text(text, reply_markup=kb_choose_role(lang))
        except:
            await call.message.answer(text, reply_markup=kb_choose_role(lang))
        await call.answer()
        return

    await upsert_user(
        telegram_id=user.telegram_id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        language=lang,
    )

    text = (
        f"{texts.t('settings_title', lang)}\n\n"
        f"{texts.t('language_set', lang)}\n"
        f"{texts.t('settings_text', lang)}"
    )
    try:
        await call.message.edit_text(text, reply_markup=kb_settings_menu(user.role, lang))
    except:
        await call.message.answer(text, reply_markup=kb_settings_menu(user.role, lang))
    await call.answer()
