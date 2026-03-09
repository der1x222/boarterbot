from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from app.models import get_user_by_telegram_id
from app.keyboards import kb_nav, kb_main_menu
from app.states import RegClient, RegEditor
from app.profile_repo import upsert_client_profile, upsert_editor_profile

router = Router()

@router.callback_query(F.data == "reg:edit_client")
async def edit_client(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(RegClient.waiting_name)
    await call.message.answer("Введите имя (как показывать исполнителям):", reply_markup=kb_nav())
    await call.answer()

@router.message(RegClient.waiting_name)
async def save_client_name(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return

    name = (message.text or "").strip()
    await upsert_client_profile(user_id=user.id, name=name)
    await state.clear()
    await message.answer("✅ Профиль заказчика обновлён!", reply_markup=kb_main_menu("client"))

@router.callback_query(F.data == "reg:edit_editor")
async def edit_editor(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(RegEditor.waiting_name)
    await call.message.answer("Введите имя (как показывать заказчикам):", reply_markup=kb_nav())
    await call.answer()

@router.message(RegEditor.waiting_name)
async def editor_step_name(message: Message, state: FSMContext):
    await state.update_data(name=(message.text or "").strip())
    await state.set_state(RegEditor.waiting_skills)
    await message.answer("Специализации через запятую (Shorts, YouTube, Reels):", reply_markup=kb_nav())

@router.message(RegEditor.waiting_skills)
async def editor_step_skills(message: Message, state: FSMContext):
    await state.update_data(skills=(message.text or "").strip())
    await state.set_state(RegEditor.waiting_price)
    await message.answer("Минимальная цена (число). Например: 20", reply_markup=kb_nav())

@router.message(RegEditor.waiting_price)
async def editor_step_price(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Цена должна быть числом. Например: 20", reply_markup=kb_nav())
        return
    await state.update_data(price_from_minor=int(raw) * 100)
    await state.set_state(RegEditor.waiting_portfolio)
    await message.answer("Ссылка на портфолио:", reply_markup=kb_nav())

@router.message(RegEditor.waiting_portfolio)
async def editor_step_portfolio(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return

    data = await state.get_data()
    await upsert_editor_profile(
        user_id=user.id,
        name=data.get("name", ""),
        skills=data.get("skills", ""),
        price_from_minor=int(data.get("price_from_minor") or 0),
        portfolio_url=(message.text or "").strip(),
    )
    await state.clear()
    await message.answer("✅ Профиль монтажёра обновлён!", reply_markup=kb_main_menu("editor"))

@router.callback_query(F.data == "reg:cancel")
async def reg_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user_by_telegram_id(call.from_user.id)
    if user:
        await call.message.answer("Ок, отменено.", reply_markup=kb_main_menu(user.role))
    else:
        await call.message.answer("Ок, отменено. Нажмите /start")
    await call.answer()