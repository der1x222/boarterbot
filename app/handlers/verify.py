from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from app.models import get_user_by_telegram_id, get_user_by_id
from app.moderation_utils import get_moderator_ids
from app.states import Verify, VerifyChat
from app.profile_repo import get_editor_profile, set_editor_test_submission, set_editor_verification
from app.keyboards import kb_nav_menu_help, kb_editor_menu, kb_verify_chat_reply, kb_verify_chat_controls

router = Router()

@router.callback_query(F.data == "verify:start")
async def verify_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "editor":
        await call.answer("Верификация доступна только монтажерам.", show_alert=True)
        return

    p = await get_editor_profile(user.id)
    status = (p.get("verification_status") if p else None) or "not_submitted"
    if status == "verified":
        await call.message.answer("Вы уже верифицированы.", reply_markup=kb_editor_menu(True))
        await call.answer()
        return
    if status == "pending":
        await call.message.answer("Заявка уже отправлена. Ожидайте ответа.")
        await call.answer()
        return

    await state.clear()
    await state.set_state(Verify.waiting_submission)
    await call.answer()
    await call.message.answer(
        "Опишите данные для верификации одним сообщением (можно ссылки, опыт, примеры работ).",
        reply_markup=kb_nav_menu_help(back="common:menu"),
    )

@router.message(Verify.waiting_submission)
async def verify_submit(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer("Верификация доступна только монтажерам.")
        return

    submission = (message.text or "").strip()
    if not submission:
        await message.answer("Введите данные для верификации одним сообщением.")
        return

    await set_editor_test_submission(user.id, submission)
    await state.clear()

    mods = list(get_moderator_ids())
    text = "Новая заявка на верификацию\n"
    if message.from_user.username:
        text += f"Юз: @{message.from_user.username}\n"
    else:
        text += f"User ID: {message.from_user.id}\n"
    text += f"Данные: {submission}"

    if mods:
        for mod_id in mods:
            try:
                await message.bot.send_message(mod_id, text)
            except:
                pass
        await message.answer("Заявка отправлена модераторам.", reply_markup=kb_editor_menu(False))
    else:
        await message.answer("Модераторы не настроены. Обратитесь в поддержку.", reply_markup=kb_editor_menu(False))

@router.callback_query(F.data.startswith("verify:chat:reply:"))
async def verify_chat_reply(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    try:
        moderator_user_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    await state.clear()
    await state.set_state(VerifyChat.chatting)
    await state.update_data(peer_user_id=moderator_user_id)
    await call.answer()
    await call.message.answer("Чат с модератором. Пишите сообщение.", reply_markup=kb_verify_chat_controls())

@router.callback_query(F.data == "verify:chat:exit")
async def verify_chat_exit(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    await state.clear()
    await call.answer()

    if user.role == "editor":
        p = await get_editor_profile(user.id)
        is_verified = bool(p and p.get("verification_status") == "verified")
        await call.message.answer("Чат закрыт.", reply_markup=kb_editor_menu(is_verified))
    else:
        await call.message.answer("Чат закрыт.")

@router.message(VerifyChat.chatting)
async def verify_chat_message(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return

    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    peer_user_id = int(data.get("peer_user_id") or 0)
    if not peer_user_id:
        await state.clear()
        return

    peer = await get_user_by_id(peer_user_id)
    if not peer:
        await state.clear()
        return

    await message.bot.send_message(
        peer.telegram_id,
        f"Сообщение по верификации от {user.display_name or user.username or f'id:{user.telegram_id}'}:\n{text}",
        reply_markup=kb_verify_chat_controls(),
    )

@router.callback_query(F.data == "verify:auto")
async def verify_auto(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return
    if user.role != "editor":
        await call.answer("Доступно только монтажерам.", show_alert=True)
        return

    await set_editor_verification(user.id, "verified", note="auto")
    await call.message.answer("✅ Верификация пройдена (тест).", reply_markup=kb_editor_menu(True))
    await call.answer()
