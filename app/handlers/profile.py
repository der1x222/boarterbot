from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.models import get_user_by_telegram_id, upsert_user
from app.profile_repo import get_editor_profile, get_client_profile
from app.order_repo import get_user_balance, create_withdrawal_request, list_withdrawal_requests
from app.keyboards import (
    kb_profile,
    kb_change_role_confirm,
    kb_main_menu,
    kb_balance,
)
from app.menu_utils import get_menu_markup_for_user
from app import texts

router = Router()


def money_from_minor(minor: int, currency: str) -> str:
    return f"{minor / 100:.2f} {currency}"


@router.callback_query(F.data.in_({"editor:profile", "client:profile"}))
async def show_profile(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    if user.role == "editor":
        p = await get_editor_profile(user.id)

        if not p:
            text = texts.tr(
                user.language,
                "👤 Editor profile\n\nProfile is not filled yet.\nTap “Edit profile”.",
                "👤 Профіль монтажера\n\nАнкета ще не заповнена.\nНатисніть «Редагувати профіль».",
            )
            status = "not_submitted"
        else:
            status = p.get("verification_status") or "not_submitted"
            status_label = {
                "not_submitted": texts.tr(user.language, "❌ Not submitted", "❌ Не подано"),
                "pending": texts.tr(user.language, "🕒 Pending", "🕒 На перевірці"),
                "verified": texts.tr(user.language, "✅ Verified", "✅ Верифіковано"),
                "rejected": texts.tr(user.language, "⛔ Rejected", "⛔ Відхилено"),
            }.get(status, status)

            price = money_from_minor(int(p.get("price_from_minor") or 0), "USD")
            portfolio = p.get("portfolio_url") or "—"

            label_name = texts.tr(user.language, "Name", "Ім'я")
            label_skills = texts.tr(user.language, "Skills", "Спеціалізації")
            label_price = texts.tr(user.language, "Price from", "Ціна від")
            label_portfolio = texts.tr(user.language, "Portfolio", "Портфоліо")
            label_verification = texts.tr(user.language, "Verification", "Верифікація")
            label_role = texts.tr(user.language, "Role", "Роль")
            role_label = texts.tr(user.language, "editor", "монтажер")

            # Get balance
            balance = await get_user_balance(user.id)
            balance_text = money_from_minor(balance.get("virtual_balance_minor", 0), "USD")
            total_earned = money_from_minor(balance.get("total_earned_minor", 0), "USD")

            text = (
                f"{texts.tr(user.language, '👤 Editor profile', '👤 Профіль монтажера')}\n\n"
                f"{label_name}: {p.get('name') or '—'}\n"
                f"{label_skills}: {p.get('skills') or '—'}\n"
                f"{label_price}: {price}\n"
                f"{label_portfolio}: {portfolio}\n\n"
                f"{label_verification}: {status_label}\n"
                f"{texts.tr(user.language, '💰 Balance', '💰 Баланс')}: {balance_text}\n"
                f"{texts.tr(user.language, '💵 Total earned', '💵 Загалом зароблено')}: {total_earned}\n"
                f"\n{label_role}: {role_label}"
            )

            if status == "rejected" and p.get("verification_note"):
                text += f"\n{texts.tr(user.language, 'Reason', 'Причина')}: {p['verification_note']}"

        markup = kb_profile("editor", status, user.language)

    elif user.role == "client":
        p = await get_client_profile(user.id)
        name = (p.get("name") if p else None) or "—"

        label_name = texts.tr(user.language, "Name", "Ім'я")
        label_role = texts.tr(user.language, "Role", "Роль")
        role_label = texts.tr(user.language, "client", "замовник")
        text = (
            f"{texts.tr(user.language, '👤 Client profile', '👤 Профіль замовника')}\n\n"
            f"{label_name}: {name}\n\n"
            f"{label_role}: {role_label}"
        )
        markup = kb_profile("client", None, user.language)

    else:
        text = texts.tr(user.language, "👤 Moderator profile", "👤 Профіль модератора")
        markup = kb_profile("moderator", None, user.language)

    try:
        await call.message.edit_text(text, reply_markup=markup)
    except:
        await call.message.answer(text, reply_markup=markup)

    await call.answer()


@router.callback_query(F.data == "profile:change_role")
async def change_role_menu(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    text = (
        f"{texts.tr(user.language, '🔁 Change role', '🔁 Зміна ролі')}\n\n"
        f"{texts.tr(user.language, 'Choose a role. Profiles will be kept.', 'Оберіть роль. Профілі збережуться.')}"
    )

    try:
        await call.message.edit_text(text, reply_markup=kb_change_role_confirm(user.language))
    except:
        await call.message.answer(text, reply_markup=kb_change_role_confirm(user.language))

    await call.answer()


@router.callback_query(F.data == "profile:back")
async def profile_back(call: CallbackQuery):
    await show_profile(call)


@router.callback_query(F.data.startswith("profile:set_role:"))
async def profile_set_role(call: CallbackQuery):
    new_role = call.data.split(":")[-1]  # client/editor

    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
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
    except:
        await call.message.answer(texts.tr(user.language, "✅ Role updated.", "✅ Роль змінено."), reply_markup=markup)

    await call.answer()

@router.callback_query(F.data == "common:balance")
async def show_balance(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Нажмите /start", show_alert=True)
        return

    balance = await get_user_balance(user.id)
    balance_text = money_from_minor(balance.get("virtual_balance_minor", 0), "USD")
    total_earned = money_from_minor(balance.get("total_earned_minor", 0), "USD")

    text = texts.tr(user.language, f"💰 Your balance\n\nVirtual balance: {balance_text}\nTotal earned: {total_earned}", f"💰 Ваш баланс\n\nВіртуальний баланс: {balance_text}\nЗагалом зароблено: {total_earned}")

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

    if balance_minor < 1000:  # minimum 10 USD
        text = texts.tr(user.language, f"💰 Your balance: {balance_text}\n\nMinimum withdrawal: 10 USD", f"💰 Ваш баланс: {balance_text}\n\nМінімальна сума виведення: 10 USD")
        await call.answer(text, show_alert=True)
        return

    text = texts.tr(user.language, f"💰 Withdraw funds\n\nYour balance: {balance_text}\n\nSend message in format:\nwithdraw <amount> <payment details>\n\nExample: withdraw 50 PayPal email@example.com", f"💰 Вивести кошти\n\nВаш баланс: {balance_text}\n\nНадішліть повідомлення у форматі:\nwithdraw <сума> <дані платежу>\n\nПриклад: withdraw 50 PayPal email@example.com")
    await call.message.edit_text(text)
    await call.answer()

@router.message(F.text.regexp(r'^withdraw (\d+(?:\.\d{1,2})?) (.+)$'))
async def handle_withdraw(message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user.role != "editor":
        return

    parts = message.text.split(' ', 2)
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

    # Create request
    request_id = await create_withdrawal_request(user.id, amount_minor, payment_details)
    if not request_id:
        await message.answer(texts.tr(user.language, "Failed to create withdrawal request", "Не вдалося створити запит на виведення"))
        return

    text = texts.tr(user.language, f"✅ Withdrawal request created!\nAmount: {amount:.2f} USD\nFee: {fee_minor / 100:.2f} USD\nYou will receive: {net_minor / 100:.2f} USD\n\nRequest ID: {request_id}\nStatus: Pending", f"✅ Запит на виведення створено!\nСума: {amount:.2f} USD\nКомісія: {fee_minor / 100:.2f} USD\nОтримаєте: {net_minor / 100:.2f} USD\n\nID запиту: {request_id}\nСтатус: Очікує")
    await message.answer(text)
