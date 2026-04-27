from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app import texts
from app.keyboards import (
    kb_balance,
    kb_change_role_confirm,
    kb_main_menu,
    kb_nav_menu_help,
    kb_profile,
)
from app.menu_utils import get_menu_markup_for_user
from app.models import get_user_by_id, get_user_by_telegram_id, upsert_user
from app.order_repo import create_withdrawal_request, get_user_balance, list_withdrawal_requests
from app.profile_repo import (
    get_client_profile,
    get_client_profile_card,
    get_editor_profile,
    get_editor_profile_card,
)

router = Router()


def money_from_minor(minor: int, currency: str) -> str:
    return f"{minor / 100:.2f} {currency}"


def _format_rating(lang: str | None, avg_rating, review_count: int) -> str:
    if not review_count or avg_rating is None:
        return texts.tr(lang, "No reviews yet", "Ще немає відгуків")
    return texts.tr(lang, f"{float(avg_rating):.1f}/5 ({review_count} reviews)", f"{float(avg_rating):.1f}/5 ({review_count} відгуків)")


def _format_joined_since(lang: str | None, joined_at) -> str:
    if not joined_at:
        return "-"
    now = datetime.now(timezone.utc)
    delta_days = max((now - joined_at).days, 0)
    if delta_days < 30:
        return texts.tr(lang, f"{delta_days} days", f"{delta_days} днів")
    if delta_days < 365:
        months = max(delta_days // 30, 1)
        return texts.tr(lang, f"{months} months", f"{months} міс.")
    years = max(delta_days // 365, 1)
    return texts.tr(lang, f"{years} years", f"{years} р.")


def _build_editor_profile_text(lang: str | None, profile: dict, include_balance: bool = False, balance: dict | None = None) -> str:
    status = profile.get("verification_status") or "not_submitted"
    status_label = {
        "not_submitted": texts.tr(lang, "Not submitted", "Не подано"),
        "pending": texts.tr(lang, "Pending", "На перевірці"),
        "verified": texts.tr(lang, "Verified", "Верифіковано"),
        "rejected": texts.tr(lang, "Rejected", "Відхилено"),
    }.get(status, status)
    label_name = texts.tr(lang, "Name", "Ім'я")
    label_skills = texts.tr(lang, "Skills", "Навички")
    label_price_from = texts.tr(lang, "Price from", "Ціна від")
    label_avg_price = texts.tr(lang, "Average price per video", "Середня ціна за ролик")
    label_rating = texts.tr(lang, "Rating", "Рейтинг")
    label_completed = texts.tr(lang, "Completed orders", "Успішно виконано замовлень")
    label_since = texts.tr(lang, "With us", "З нами")
    label_portfolio = texts.tr(lang, "Portfolio", "Портфоліо")
    label_verification = texts.tr(lang, "Verification", "Верифікація")
    text = (
        f"{texts.tr(lang, '👤 Editor profile', '👤 Профіль монтажера')}\n\n"
        f"{label_name}: {profile.get('name') or profile.get('display_name') or '—'}\n"
        f"{label_skills}: {profile.get('skills') or '—'}\n"
        f"{label_price_from}: {money_from_minor(int(profile.get('price_from_minor') or 0), 'USD')}\n"
        f"{label_avg_price}: {money_from_minor(int(profile.get('avg_price_minor') or 0), 'USD')}\n"
        f"{label_rating}: {_format_rating(lang, profile.get('avg_rating'), int(profile.get('review_count') or 0))}\n"
        f"{label_completed}: {int(profile.get('completed_orders') or 0)}\n"
        f"{label_since}: {_format_joined_since(lang, profile.get('joined_at'))}\n"
        f"{label_portfolio}: {profile.get('portfolio_url') or '—'}\n"
        f"{label_verification}: {status_label}"
    )
    if include_balance and balance:
        text += (
            f"\n{texts.tr(lang, 'Balance', 'Баланс')}: {money_from_minor(balance.get('virtual_balance_minor', 0), 'USD')}"
            f"\n{texts.tr(lang, 'Total earned', 'Загалом зароблено')}: {money_from_minor(balance.get('total_earned_minor', 0), 'USD')}"
        )
    if status == "rejected" and profile.get("verification_note"):
        text += f"\n{texts.tr(lang, 'Reason', 'Причина')}: {profile.get('verification_note')}"
    return text


def _build_client_profile_text(lang: str | None, profile: dict) -> str:
    label_name = texts.tr(lang, "Name", "Ім'я")
    label_rating = texts.tr(lang, "Rating", "Рейтинг")
    label_completed = texts.tr(lang, "Completed orders", "Завершено замовлень")
    label_since = texts.tr(lang, "With us", "З нами")
    return (
        f"{texts.tr(lang, '👤 Client profile', '👤 Профіль замовника')}\n\n"
        f"{label_name}: {profile.get('name') or profile.get('display_name') or '—'}\n"
        f"{label_rating}: {_format_rating(lang, profile.get('avg_rating'), int(profile.get('review_count') or 0))}\n"
        f"{label_completed}: {int(profile.get('completed_orders') or 0)}\n"
        f"{label_since}: {_format_joined_since(lang, profile.get('joined_at'))}"
    )


@router.callback_query(F.data.in_({"editor:profile", "client:profile"}))
async def show_profile(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Натисніть /start", show_alert=True)
        return

    if user.role == "editor":
        profile = await get_editor_profile_card(user.id)
        if not profile:
            text = texts.tr(
                user.language,
                "👤 Editor profile\n\nProfile is not filled yet. Tap Edit profile.",
                "👤 Профіль монтажера\n\nПрофіль ще не заповнений. Натисніть Редагувати профіль.",
            )
            status = "not_submitted"
        else:
            text = _build_editor_profile_text(
                user.language,
                profile,
                include_balance=True,
                balance=await get_user_balance(user.id),
            )
            status = profile.get("verification_status") or "not_submitted"
        markup = kb_profile("editor", status, user.language)
    elif user.role == "client":
        profile = await get_client_profile_card(user.id) or await get_client_profile(user.id) or {"display_name": user.display_name}
        text = _build_client_profile_text(user.language, profile)
        markup = kb_profile("client", None, user.language)
    else:
        text = texts.tr(user.language, "👤 Moderator profile", "👤 Профіль модератора")
        markup = kb_profile("moderator", None, user.language)

    try:
        await call.message.edit_text(text, reply_markup=markup)
    except Exception:
        await call.message.answer(text, reply_markup=markup)
    await call.answer()


@router.callback_query(F.data.startswith("profile:view:"))
async def view_public_profile(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) < 5:
        await call.answer(texts.tr(user.language, "Invalid profile link.", "Некоректне посилання на профіль."), show_alert=True)
        return

    try:
        target_user_id = int(parts[2])
        order_id = int(parts[4])
    except ValueError:
        await call.answer(texts.tr(user.language, "Invalid profile link.", "Некоректне посилання на профіль."), show_alert=True)
        return

    source = parts[3]
    target_user = await get_user_by_id(target_user_id)
    if not target_user:
        await call.answer(texts.tr(user.language, "User not found.", "Користувача не знайдено."), show_alert=True)
        return

    if target_user.role == "editor":
        profile = await get_editor_profile_card(target_user_id) or {"display_name": target_user.display_name}
        text = _build_editor_profile_text(user.language, profile)
    elif target_user.role == "client":
        profile = await get_client_profile_card(target_user_id) or {"display_name": target_user.display_name}
        text = _build_client_profile_text(user.language, profile)
    else:
        text = texts.tr(user.language, "👤 Moderator profile", "👤 Профіль модератора")

    back_callback = "common:menu"
    if source == "open":
        back_callback = f"editor:order_view:{order_id}"
    elif source == "deal":
        back_callback = f"deal:menu:{order_id}"
    elif source == "proposal":
        back_callback = f"order:view:{order_id}"

    try:
        await call.message.edit_text(text, reply_markup=kb_nav_menu_help(back=back_callback, lang=user.language))
    except Exception:
        await call.message.answer(text, reply_markup=kb_nav_menu_help(back=back_callback, lang=user.language))
    await call.answer()


@router.callback_query(F.data == "profile:change_role")
async def change_role_menu(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Натисніть /start", show_alert=True)
        return

    text = (
        f"{texts.tr(user.language, '🔁 Change role', '🔁 Зміна ролі')}\n\n"
        f"{texts.tr(user.language, 'Choose a role. Profiles will be kept.', 'Оберіть роль. Профілі збережуться.')}"
    )

    try:
        await call.message.edit_text(text, reply_markup=kb_change_role_confirm(user.language))
    except Exception:
        await call.message.answer(text, reply_markup=kb_change_role_confirm(user.language))

    await call.answer()


@router.callback_query(F.data == "profile:back")
async def profile_back(call: CallbackQuery):
    await show_profile(call)


@router.callback_query(F.data.startswith("profile:set_role:"))
async def profile_set_role(call: CallbackQuery):
    new_role = call.data.split(":")[-1]

    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Натисніть /start", show_alert=True)
        return

    tg = call.from_user
    display_name = (tg.full_name or "").strip() or tg.username or "User"

    await upsert_user(
        telegram_id=tg.id,
        username=tg.username,
        display_name=display_name,
        role=new_role,
        language=user.language,
    )

    user = await get_user_by_telegram_id(tg.id)
    markup = await get_menu_markup_for_user(user) if user else kb_main_menu(new_role, user.language if user else None)

    try:
        await call.message.edit_text(texts.tr(user.language, "✅ Role updated.", "✅ Роль змінено."), reply_markup=markup)
    except Exception:
        await call.message.answer(texts.tr(user.language, "✅ Role updated.", "✅ Роль змінено."), reply_markup=markup)

    await call.answer()


@router.callback_query(F.data == "common:balance")
async def show_balance(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Натисніть /start", show_alert=True)
        return

    balance = await get_user_balance(user.id)
    balance_text = money_from_minor(balance.get("virtual_balance_minor", 0), "USD")
    total_earned = money_from_minor(balance.get("total_earned_minor", 0), "USD")

    text = texts.tr(
        user.language,
        f"💰 Your balance\n\nVirtual balance: {balance_text}\nTotal earned: {total_earned}",
        f"💰 Ваш баланс\n\nВіртуальний баланс: {balance_text}\nЗагалом зароблено: {total_earned}",
    )

    markup = kb_balance(user.role, user.language)
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


# ---------- Balance and withdrawal handlers ----------

@router.callback_query(F.data == "balance:withdraw")
async def withdraw_menu(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user or user.role != "editor":
        await call.answer(texts.tr(user.language if user else None, "Access denied", "Доступ заборонено"), show_alert=True)
        return

    balance = await get_user_balance(user.id)
    balance_minor = balance.get("virtual_balance_minor", 0)
    balance_text = money_from_minor(balance_minor, "USD")

    if balance_minor < 1000:
        text = texts.tr(user.language, f"💰 Your balance: {balance_text}\n\nMinimum withdrawal: 10 USD", f"💰 Ваш баланс: {balance_text}\n\nМінімальна сума виведення: 10 USD")
        await call.answer(text, show_alert=True)
        return

    text = texts.tr(
        user.language,
        f"💰 Withdraw funds\n\nYour balance: {balance_text}\n\nSend message in format:\nwithdraw <amount> <payment details>\n\nExample: withdraw 50 PayPal email@example.com",
        f"💰 Вивести кошти\n\nВаш баланс: {balance_text}\n\nНадішліть повідомлення у форматі:\nwithdraw <сума> <дані платежу>\n\nПриклад: withdraw 50 PayPal email@example.com",
    )
    await call.message.edit_text(text)
    await call.answer()


@router.message(F.text.regexp(r"^withdraw (\d+(?:\.\d{1,2})?) (.+)$"))
async def handle_withdraw(message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user.role != "editor":
        return

    parts = message.text.split(" ", 2)
    if len(parts) < 3:
        await message.answer(texts.tr(user.language, "Format: withdraw <amount> <payment details>", "Формат: withdraw <сума> <дані платежу>"))
        return

    try:
        amount = float(parts[1])
        amount_minor = int(amount * 100)
    except ValueError:
        await message.answer(texts.tr(user.language, "Invalid amount", "Некоректна сума"))
        return

    payment_details = parts[2]
    balance = await get_user_balance(user.id)
    if balance.get("virtual_balance_minor", 0) < amount_minor:
        await message.answer(texts.tr(user.language, "Insufficient balance", "Недостатньо коштів"))
        return

    fee_minor = amount_minor // 10
    net_minor = amount_minor - fee_minor
    request_id = await create_withdrawal_request(user.id, amount_minor, payment_details)
    if not request_id:
        await message.answer(texts.tr(user.language, "Failed to create withdrawal request", "Не вдалося створити запит на виведення"))
        return

    text = texts.tr(
        user.language,
        f"✅ Withdrawal request created!\nAmount: {amount:.2f} USD\nFee: {fee_minor / 100:.2f} USD\nYou will receive: {net_minor / 100:.2f} USD\n\nRequest ID: {request_id}\nStatus: Pending",
        f"✅ Запит на виведення створено!\nСума: {amount:.2f} USD\nКомісія: {fee_minor / 100:.2f} USD\nОтримаєте: {net_minor / 100:.2f} USD\n\nID запиту: {request_id}\nСтатус: Очікує",
    )
    await message.answer(text)
