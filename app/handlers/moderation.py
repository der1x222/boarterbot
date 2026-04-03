from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from app.models import get_user_by_telegram_id, get_user_by_id
from app.profile_repo import set_editor_verification
from app.menu_utils import get_menu_markup_for_user
from app.moderation_utils import is_moderator_telegram_id
from app.moderation_repo import (
    list_pending_verifications,
    list_held_messages,
    list_dispute_deals,
    get_deal_by_id,
    get_held_message_by_id,
    update_held_message_status,
    count_stats,
    create_user_sanction,
    log_moderation_action,
)
from app.keyboards import (
    kb_mod_verification_controls,
    kb_mod_held_controls,
    kb_mod_dispute_controls,
    kb_mod_user_controls,
    kb_moderation_menu,
    kb_nav_menu_help,
    kb_verify_chat_reply,
    kb_verify_chat_controls,
)
from app.states import ModerationSearch, ModerationUserLookup, ModerationMessage, VerifyChat

router = Router()

# ---------- helpers ----------

def _truncate(text: str | None, limit: int = 600) -> str:
    if not text:
        return "—"
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."

def _money_from_minor(minor: int, currency: str = "USD") -> str:
    return f"{minor / 100:.2f} {currency}"

async def _ensure_moderator(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return None
    if not is_moderator_telegram_id(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return None
    return user

async def _ensure_moderator_message(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or not is_moderator_telegram_id(message.from_user.id):
        return None
    return user

async def _safe_edit_or_send(call: CallbackQuery, text: str, reply_markup=None):
    try:
        await call.message.edit_text(text, reply_markup=reply_markup)
    except:
        await call.message.answer(text, reply_markup=reply_markup)

async def _show_pending_verifications(call: CallbackQuery, offset: int):
    items = await list_pending_verifications(offset=offset, limit=1)
    if not items:
        await _safe_edit_or_send(
            call,
            "🆕 Новые верификации\n\nОчередь пустая.",
            reply_markup=kb_nav_menu_help(back="common:menu"),
        )
        return

    p = items[0]
    price = _money_from_minor(int(p.get("price_from_minor") or 0))
    text = (
        "🆕 Новые верификации\n\n"
        f"user_id: {p.get('user_id')}\n"
        f"имя: {p.get('name') or '—'}\n"
        f"специализации: {p.get('skills') or '—'}\n"
        f"цена: {price}\n"
        f"портфолио: {p.get('portfolio_url') or '—'}\n"
        f"test_submission: {_truncate(p.get('test_submission'))}\n"
        f"verification_status: {p.get('verification_status')}"
    )
    await _safe_edit_or_send(
        call,
        text,
        reply_markup=kb_mod_verification_controls(int(p["user_id"]), offset),
    )

async def _show_held_messages(call: CallbackQuery, offset: int):
    items = await list_held_messages(offset=offset, limit=1)
    if not items:
        await _safe_edit_or_send(
            call,
            "💬 Сообщения на проверке\n\nОчередь пустая.",
            reply_markup=kb_nav_menu_help(back="common:menu"),
        )
        return

    m = items[0]
    text = (
        "💬 Сообщения на проверке\n\n"
        f"deal_id: {m.get('deal_id')}\n"
        f"sender_user_id: {m.get('sender_user_id')}\n"
        f"original_text: {_truncate(m.get('original_text'))}\n"
        f"normalized_text: {_truncate(m.get('normalized_text'))}\n"
        f"flag_reason: {m.get('flag_reason')}"
    )
    await _safe_edit_or_send(
        call,
        text,
        reply_markup=kb_mod_held_controls(int(m["id"]), offset),
    )

async def _show_disputes(call: CallbackQuery, offset: int):
    items = await list_dispute_deals(offset=offset, limit=1)
    if not items:
        await _safe_edit_or_send(
            call,
            "⚠️ Споры\n\nАктивных споров нет.",
            reply_markup=kb_nav_menu_help(back="common:menu"),
        )
        return

    d = items[0]
    text = (
        "⚠️ Споры\n\n"
        f"deal_id: {d.get('id')}\n"
        f"client_id: {d.get('client_id')}\n"
        f"editor_id: {d.get('editor_id')}\n"
        f"status: {d.get('status')}\n"
        f"price_minor: {d.get('price_minor')}"
    )
    await _safe_edit_or_send(
        call,
        text,
        reply_markup=kb_mod_dispute_controls(int(d["id"]), offset),
    )

# ---------- menu entries ----------

@router.callback_query(F.data == "mod:menu")
async def mod_menu(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    await _safe_edit_or_send(
        call,
        "Инструменты модератора:",
        reply_markup=kb_moderation_menu(),
    )
    await call.answer()

@router.callback_query(F.data == "mod:verifications")
async def mod_verifications(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    await _show_pending_verifications(call, 0)
    await call.answer()

@router.callback_query(F.data.startswith("mod:verifications:page:"))
async def mod_verifications_page(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    try:
        offset = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Неверный offset.", show_alert=True)
        return
    await _show_pending_verifications(call, offset)
    await call.answer()

@router.callback_query(F.data.startswith("mod:verifications:approve:"))
async def mod_verifications_approve(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    parts = call.data.split(":")
    if len(parts) < 5:
        await call.answer("Неверные данные.", show_alert=True)
        return
    try:
        editor_user_id = int(parts[3])
        offset = int(parts[4])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    await set_editor_verification(editor_user_id, "verified", note="approved by moderator")
    await log_moderation_action(
        moderator_user_id=user.id,
        action_type="verify_approve",
        target_user_id=editor_user_id,
        object_type="editor_profile",
        object_id=editor_user_id,
        payload={},
    )
    await _show_pending_verifications(call, offset)
    await call.answer("✅ Одобрено.")

@router.callback_query(F.data.startswith("mod:verifications:reject:"))
async def mod_verifications_reject(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    parts = call.data.split(":")
    if len(parts) < 5:
        await call.answer("Неверные данные.", show_alert=True)
        return
    try:
        editor_user_id = int(parts[3])
        offset = int(parts[4])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    await set_editor_verification(editor_user_id, "rejected", note="rejected by moderator")
    await log_moderation_action(
        moderator_user_id=user.id,
        action_type="verify_reject",
        target_user_id=editor_user_id,
        object_type="editor_profile",
        object_id=editor_user_id,
        payload={},
    )
    await _show_pending_verifications(call, offset)
    await call.answer("❌ Отклонено.")

@router.callback_query(F.data.startswith("mod:verifications:chat:"))
async def mod_verifications_chat(call: CallbackQuery, state: FSMContext):
    user = await _ensure_moderator(call)
    if not user:
        return
    try:
        editor_user_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("???????????????? user_id.", show_alert=True)
        return

    await state.clear()
    await state.set_state(VerifyChat.chatting)
    await state.update_data(peer_user_id=editor_user_id)

    await _safe_edit_or_send(
        call,
        "?????? ?? ????????????????????. ???????????? ??????????????????.",
        reply_markup=kb_verify_chat_controls(),
    )
    await call.answer()

    editor = await get_user_by_id(editor_user_id)
    if editor:
        await call.bot.send_message(
            editor.telegram_id,
            "?????????????????? ?????????? ?????? ???? ??????????????????????. ?????????????? ??????????????????, ?????????? ????????????????.",
            reply_markup=kb_verify_chat_reply(user.id),
        )

@router.callback_query(F.data.startswith("mod:verifications:msg:"))
async def mod_verifications_message(call: CallbackQuery, state: FSMContext):
    user = await _ensure_moderator(call)
    if not user:
        return
    try:
        target_user_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Неверный user_id.", show_alert=True)
        return

    await state.clear()
    await state.set_state(ModerationMessage.waiting_text)
    await state.update_data(
        target_user_ids=[target_user_id],
        object_type="editor_profile",
        object_id=target_user_id,
        action_type="verification_message",
    )
    await _safe_edit_or_send(
        call,
        "✉️ Напишите сообщение пользователю одним сообщением:",
        reply_markup=kb_nav_menu_help(back="common:menu"),
    )
    await call.answer()

@router.callback_query(F.data == "mod:held_messages")
async def mod_held_messages(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    await _show_held_messages(call, 0)
    await call.answer()

@router.callback_query(F.data.startswith("mod:held_messages:page:"))
async def mod_held_messages_page(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    try:
        offset = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Неверный offset.", show_alert=True)
        return
    await _show_held_messages(call, offset)
    await call.answer()

@router.callback_query(F.data.startswith("mod:held_messages:approve:"))
async def mod_held_messages_approve(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    parts = call.data.split(":")
    if len(parts) < 5:
        await call.answer("Неверные данные.", show_alert=True)
        return
    try:
        message_id = int(parts[3])
        offset = int(parts[4])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    held = await get_held_message_by_id(message_id)
    await update_held_message_status(message_id, "approved")
    await log_moderation_action(
        moderator_user_id=user.id,
        action_type="held_approve",
        target_user_id=int(held["sender_user_id"]) if held else None,
        object_type="held_message",
        object_id=message_id,
        payload={},
    )
    await _show_held_messages(call, offset)
    await call.answer("✅ Одобрено.")

@router.callback_query(F.data.startswith("mod:held_messages:reject:"))
async def mod_held_messages_reject(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    parts = call.data.split(":")
    if len(parts) < 5:
        await call.answer("Неверные данные.", show_alert=True)
        return
    try:
        message_id = int(parts[3])
        offset = int(parts[4])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    held = await get_held_message_by_id(message_id)
    await update_held_message_status(message_id, "rejected")
    await log_moderation_action(
        moderator_user_id=user.id,
        action_type="held_reject",
        target_user_id=int(held["sender_user_id"]) if held else None,
        object_type="held_message",
        object_id=message_id,
        payload={},
    )
    await _show_held_messages(call, offset)
    await call.answer("❌ Отклонено.")

@router.callback_query(F.data.startswith("mod:held_messages:ban:"))
async def mod_held_messages_ban(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    parts = call.data.split(":")
    if len(parts) < 5:
        await call.answer("Неверные данные.", show_alert=True)
        return
    try:
        message_id = int(parts[3])
        offset = int(parts[4])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    held = await get_held_message_by_id(message_id)
    if not held:
        await call.answer("Сообщение не найдено.", show_alert=True)
        return

    target_user_id = int(held["sender_user_id"])
    await create_user_sanction(
        target_user_id=target_user_id,
        moderator_user_id=user.id,
        sanction_type="ban",
        reason="held_message",
    )
    await update_held_message_status(message_id, "rejected")
    await log_moderation_action(
        moderator_user_id=user.id,
        action_type="user_ban",
        target_user_id=target_user_id,
        object_type="held_message",
        object_id=message_id,
        payload={"reason": "held_message"},
    )
    await _show_held_messages(call, offset)
    await call.answer("🚫 Пользователь забанен.")

@router.callback_query(F.data.startswith("mod:held_messages:msg:"))
async def mod_held_messages_message(call: CallbackQuery, state: FSMContext):
    user = await _ensure_moderator(call)
    if not user:
        return
    try:
        message_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    held = await get_held_message_by_id(message_id)
    if not held:
        await call.answer("Сообщение не найдено.", show_alert=True)
        return

    await state.clear()
    await state.set_state(ModerationMessage.waiting_text)
    await state.update_data(
        target_user_ids=[int(held["sender_user_id"])],
        object_type="held_message",
        object_id=message_id,
        action_type="held_message_reply",
    )
    await _safe_edit_or_send(
        call,
        "✉️ Напишите сообщение пользователю одним сообщением:",
        reply_markup=kb_nav_menu_help(back="common:menu"),
    )
    await call.answer()

@router.callback_query(F.data == "mod:disputes")
async def mod_disputes(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    await _show_disputes(call, 0)
    await call.answer()

@router.callback_query(F.data.startswith("mod:disputes:page:"))
async def mod_disputes_page(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    try:
        offset = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Неверный offset.", show_alert=True)
        return
    await _show_disputes(call, offset)
    await call.answer()

@router.callback_query(F.data.startswith("mod:disputes:pay:"))
async def mod_disputes_pay(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    parts = call.data.split(":")
    if len(parts) < 5:
        await call.answer("Неверные данные.", show_alert=True)
        return
    try:
        deal_id = int(parts[3])
        offset = int(parts[4])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    await log_moderation_action(
        moderator_user_id=user.id,
        action_type="dispute_pay_editor",
        target_user_id=None,
        object_type="deal",
        object_id=deal_id,
        payload={},
    )
    await _show_disputes(call, offset)
    await call.answer("✅ Решение записано.")

@router.callback_query(F.data.startswith("mod:disputes:refund:"))
async def mod_disputes_refund(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    parts = call.data.split(":")
    if len(parts) < 5:
        await call.answer("Неверные данные.", show_alert=True)
        return
    try:
        deal_id = int(parts[3])
        offset = int(parts[4])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    await log_moderation_action(
        moderator_user_id=user.id,
        action_type="dispute_refund_client",
        target_user_id=None,
        object_type="deal",
        object_id=deal_id,
        payload={},
    )
    await _show_disputes(call, offset)
    await call.answer("↩️ Решение записано.")

@router.callback_query(F.data.startswith("mod:disputes:msg:"))
async def mod_disputes_message(call: CallbackQuery, state: FSMContext):
    user = await _ensure_moderator(call)
    if not user:
        return
    try:
        deal_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    deal = await get_deal_by_id(deal_id)
    if not deal:
        await call.answer("Сделка не найдена.", show_alert=True)
        return

    targets = []
    if deal.get("client_id"):
        targets.append(int(deal["client_id"]))
    if deal.get("editor_id"):
        targets.append(int(deal["editor_id"]))

    await state.clear()
    await state.set_state(ModerationMessage.waiting_text)
    await state.update_data(
        target_user_ids=targets,
        object_type="deal",
        object_id=deal_id,
        action_type="dispute_message",
    )
    await _safe_edit_or_send(
        call,
        "✉️ Напишите сообщение для сторон спора одним сообщением:",
        reply_markup=kb_nav_menu_help(back="common:menu"),
    )
    await call.answer()

@router.callback_query(F.data == "mod:search")
async def mod_search_start(call: CallbackQuery, state: FSMContext):
    user = await _ensure_moderator(call)
    if not user:
        return
    await state.clear()
    await state.set_state(ModerationSearch.waiting_query)
    await _safe_edit_or_send(
        call,
        "🔎 Поиск\n\nВведите user_id или deal_id:",
        reply_markup=kb_nav_menu_help(back="common:menu"),
    )
    await call.answer()

@router.message(ModerationSearch.waiting_query)
async def mod_search_result(message: Message, state: FSMContext):
    user = await _ensure_moderator_message(message)
    if not user:
        await state.clear()
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Введите число (user_id или deal_id).")
        return

    query_id = int(raw)
    found_user = await get_user_by_id(query_id)
    found_deal = await get_deal_by_id(query_id)

    lines = ["🔎 Поиск"]
    if found_user:
        username = f"@{found_user.username}" if found_user.username else "—"
        lines.append(
            "\nПользователь:"
            f"\n  user_id: {found_user.id}"
            f"\n  telegram_id: {found_user.telegram_id}"
            f"\n  username: {username}"
            f"\n  display_name: {found_user.display_name or '—'}"
            f"\n  role: {found_user.role}"
        )
    if found_deal:
        lines.append(
            "\nСделка:"
            f"\n  deal_id: {found_deal.get('id')}"
            f"\n  client_id: {found_deal.get('client_id')}"
            f"\n  editor_id: {found_deal.get('editor_id')}"
            f"\n  status: {found_deal.get('status')}"
            f"\n  price_minor: {found_deal.get('price_minor')}"
        )

    if not found_user and not found_deal:
        lines.append("\nНичего не найдено.")

    await state.clear()
    await message.answer("\n".join(lines), reply_markup=await get_menu_markup_for_user(user))

@router.callback_query(F.data == "mod:stats")
async def mod_stats(call: CallbackQuery):
    user = await _ensure_moderator(call)
    if not user:
        return
    stats = await count_stats()
    text = (
        "📊 Статистика\n\n"
        f"pending верификаций: {stats.get('pending_verifications', 0)}\n"
        f"held messages: {stats.get('held_messages', 0)}\n"
        f"disputes: {stats.get('disputes', 0)}\n"
        f"users: {stats.get('users', 0)}\n"
        f"editor_profiles: {stats.get('editor_profiles', 0)}\n"
        f"client_profiles: {stats.get('client_profiles', 0)}"
    )
    await _safe_edit_or_send(call, text, reply_markup=kb_nav_menu_help(back="common:menu"))
    await call.answer()

@router.callback_query(F.data == "mod:users")
async def mod_users_start(call: CallbackQuery, state: FSMContext):
    user = await _ensure_moderator(call)
    if not user:
        return
    await state.clear()
    await state.set_state(ModerationUserLookup.waiting_user_id)
    await _safe_edit_or_send(
        call,
        "🚫 Пользователи / санкции\n\nВведите user_id:",
        reply_markup=kb_nav_menu_help(back="common:menu"),
    )
    await call.answer()

@router.message(ModerationUserLookup.waiting_user_id)
async def mod_users_show(message: Message, state: FSMContext):
    moderator = await _ensure_moderator_message(message)
    if not moderator:
        await state.clear()
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Введите число (user_id).")
        return

    user_id = int(raw)
    user = await get_user_by_id(user_id)
    if not user:
        await message.answer("Пользователь не найден.")
        return

    text = (
        "🚫 Пользователь\n\n"
        f"user_id: {user.id}\n"
        f"telegram_id: {user.telegram_id}\n"
        f"username: {('@' + user.username) if user.username else '—'}\n"
        f"display_name: {user.display_name or '—'}\n"
        f"role: {user.role}"
    )
    await state.clear()
    await message.answer(text, reply_markup=kb_mod_user_controls(user.id))

@router.callback_query(F.data.startswith("mod:user:warn:"))
async def mod_user_warn(call: CallbackQuery):
    moderator = await _ensure_moderator(call)
    if not moderator:
        return
    try:
        target_user_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    await create_user_sanction(
        target_user_id=target_user_id,
        moderator_user_id=moderator.id,
        sanction_type="warning",
        reason="manual_warning",
    )
    await log_moderation_action(
        moderator_user_id=moderator.id,
        action_type="user_warning",
        target_user_id=target_user_id,
        object_type="user",
        object_id=target_user_id,
        payload={"reason": "manual_warning"},
    )
    await _safe_edit_or_send(
        call,
        f"⚠️ Warning выдан пользователю {target_user_id}.",
        reply_markup=kb_mod_user_controls(target_user_id),
    )
    await call.answer()

@router.callback_query(F.data.startswith("mod:user:ban:"))
async def mod_user_ban(call: CallbackQuery):
    moderator = await _ensure_moderator(call)
    if not moderator:
        return
    try:
        target_user_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    await create_user_sanction(
        target_user_id=target_user_id,
        moderator_user_id=moderator.id,
        sanction_type="ban",
        reason="manual_ban",
    )
    await log_moderation_action(
        moderator_user_id=moderator.id,
        action_type="user_ban",
        target_user_id=target_user_id,
        object_type="user",
        object_id=target_user_id,
        payload={"reason": "manual_ban"},
    )
    await _safe_edit_or_send(
        call,
        f"🚫 Пользователь {target_user_id} забанен.",
        reply_markup=kb_mod_user_controls(target_user_id),
    )
    await call.answer()

@router.callback_query(F.data.startswith("mod:user:msg:"))
async def mod_user_message(call: CallbackQuery, state: FSMContext):
    moderator = await _ensure_moderator(call)
    if not moderator:
        return
    try:
        target_user_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Неверные данные.", show_alert=True)
        return

    await state.clear()
    await state.set_state(ModerationMessage.waiting_text)
    await state.update_data(
        target_user_ids=[target_user_id],
        object_type="user",
        object_id=target_user_id,
        action_type="user_message",
    )
    await _safe_edit_or_send(
        call,
        "✉️ Напишите сообщение пользователю одним сообщением:",
        reply_markup=kb_nav_menu_help(back="common:menu"),
    )
    await call.answer()

@router.message(ModerationMessage.waiting_text)
async def mod_send_message(message: Message, state: FSMContext):
    moderator = await _ensure_moderator_message(message)
    if not moderator:
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите текст сообщения.")
        return

    data = await state.get_data()
    target_ids = list({int(x) for x in (data.get("target_user_ids") or [])})
    object_type = data.get("object_type") or "user"
    object_id = data.get("object_id")
    action_type = data.get("action_type") or "message"

    for target_id in target_ids:
        target_user = await get_user_by_id(target_id)
        if target_user:
            await message.bot.send_message(
                target_user.telegram_id,
                f"Сообщение от модератора:\n{text}",
            )

    await log_moderation_action(
        moderator_user_id=moderator.id,
        action_type=action_type,
        target_user_id=target_ids[0] if target_ids else None,
        object_type=object_type,
        object_id=int(object_id) if object_id else None,
        payload={"text": text, "targets": target_ids},
    )

    await state.clear()
    await message.answer("✅ Сообщение отправлено.", reply_markup=await get_menu_markup_for_user(moderator))
