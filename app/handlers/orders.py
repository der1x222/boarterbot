from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from datetime import datetime, timedelta
import re
from urllib.parse import urlparse

from app.models import get_user_by_telegram_id, get_user_by_id, list_moderators
from app.keyboards import kb_nav_menu_help, kb_orders_list, kb_order_detail, kb_deal_menu, kb_mod_deal_menu, kb_editor_order_detail, kb_deal_chat_controls, kb_dispute_join, kb_dispute_controls, kb_deal_chat_menu, kb_proposal_actions, kb_deal_chat_link_controls, kb_deadline_quick, kb_revision_request_menu, kb_revision_response_menu, kb_order_completion_menu, kb_client_completion_menu, kb_order_category, kb_order_platform, kb_order_reference_controls, kb_order_category_edit, kb_order_platform_edit, kb_order_reference_controls_edit, kb_order_create_form, kb_order_materials_controls, kb_order_materials_controls_edit
from app.menu_utils import get_menu_markup_for_user
from app.states import CreateOrder, DealChange, EditOrder, EditorProposal, DealChat, DisputeChat, DisputeOpenReason, ChatRequest, RevisionRequest, RevisionCounter
from app.order_repo import create_order, list_orders_for_client, get_order_for_client, accept_order, get_order_by_id, update_order_if_open, open_dispute, set_dispute_agree, close_dispute, set_payment_link, create_deal_message, get_deal_messages, request_revision, respond_to_revision, set_revision_payment_link, mark_revision_paid, mark_final_video_sent, confirm_order_completion, complete_order_and_credit_editor
from app.profile_repo import get_editor_profile
from app.payment_api import create_payment_link
from app.moderation_utils import is_moderator_telegram_id, contains_forbidden_words, normalize_text
from app.moderation_repo import create_held_message
from app import texts

router = Router()

def _t(user, en: str, ua: str) -> str:
    return texts.tr(getattr(user, "language", None), en, ua)

def _tl(lang: str | None, en: str, ua: str) -> str:
    return texts.tr(lang, en, ua)

# ---------- helpers for clean chat ----------

async def safe_delete_message(message: Message | None):
    if not message:
        return
    try:
        await message.delete()
    except:
        pass

async def safe_delete_by_id(bot, chat_id: int, message_id: int | None):
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass

async def set_last_bot_message(state: FSMContext, message_id: int):
    await state.update_data(last_bot_message_id=message_id)

async def clear_last_bot_message(state: FSMContext, bot, chat_id: int):
    data = await state.get_data()
    await safe_delete_by_id(bot, chat_id, data.get("last_bot_message_id"))
    await state.update_data(last_bot_message_id=None)

async def send_clean(message: Message, state: FSMContext, text: str, reply_markup=None):
    await clear_last_bot_message(state, message.bot, message.chat.id)
    msg = await message.answer(text, reply_markup=reply_markup)
    await set_last_bot_message(state, msg.message_id)
    return msg

async def send_clean_from_call(call: CallbackQuery, state: FSMContext, text: str, reply_markup=None):
    chat_id = call.message.chat.id
    await clear_last_bot_message(state, call.bot, chat_id)
    try:
        await safe_delete_message(call.message)
    except:
        pass
    msg = await call.message.answer(text, reply_markup=reply_markup)
    await set_last_bot_message(state, msg.message_id)
    return msg

def _order_category_label(category: str | None, lang: str | None) -> str:
    labels = {
        "ad": _tl(lang, "Ad / promo", "Реклама / промо"),
        "youtube": _tl(lang, "YouTube video", "YouTube-відео"),
        "podcast": _tl(lang, "Interview / podcast", "Інтерв'ю / подкаст"),
        "shorts": _tl(lang, "Shorts / Reels / TikTok", "Shorts / Reels / TikTok"),
        "other": _tl(lang, "Other", "Інше"),
    }
    return labels.get((category or "").strip(), _tl(lang, "Not selected", "Не вибрано"))

def _order_platform_label(platform: str | None, lang: str | None) -> str:
    labels = {
        "youtube": "YouTube",
        "instagram": "Instagram",
        "tiktok": "TikTok",
        "facebook": "Facebook",
        "other": _tl(lang, "Other", "Інше"),
    }
    return labels.get((platform or "").strip(), _tl(lang, "Not selected", "Не вибрано"))

def _is_valid_youtube_url(raw: str) -> bool:
    try:
        parsed = urlparse(raw.strip())
    except Exception:
        return False
    host = (parsed.netloc or "").lower()
    return host.endswith("youtube.com") or host == "youtu.be" or host.endswith(".youtu.be")

def _extract_urls(raw: str) -> list[str]:
    return re.findall(r"https?://[^\s]+", raw or "", flags=re.IGNORECASE)

def _is_allowed_material_host(host: str) -> bool:
    clean_host = (host or "").lower().lstrip("www.")
    allowed_hosts = (
        "drive.google.com",
        "docs.google.com",
        "dropbox.com",
        "onedrive.live.com",
        "1drv.ms",
        "mega.nz",
        "wetransfer.com",
        "we.tl",
        "mediafire.com",
        "pixeldrain.com",
    )
    return any(clean_host == h or clean_host.endswith(f".{h}") for h in allowed_hosts)

def _has_only_allowed_material_links(raw: str) -> bool:
    urls = _extract_urls(raw)
    if not urls:
        return True
    for url in urls:
        try:
            parsed = urlparse(url.strip())
        except Exception:
            return False
        if parsed.scheme not in {"http", "https"}:
            return False
        if not _is_allowed_material_host(parsed.netloc):
            return False
    return True

def _build_order_description(data: dict, lang: str | None) -> str:
    task_details = (data.get("task_details") or "").strip()
    materials = (data.get("materials") or "").strip()
    reference_url = (data.get("reference_url") or "").strip() or _tl(lang, "No reference", "Без референсу")
    category = _order_category_label(data.get("category"), lang)
    platform = _order_platform_label(data.get("platform"), lang)
    return (
        f"{_tl(lang, 'Category', 'Категорія')}: {category}\n"
        f"{_tl(lang, 'Platform', 'Платформа')}: {platform}\n\n"
        f"{_tl(lang, 'Task details', 'Деталі завдання')}:\n{task_details}\n\n"
        f"{_tl(lang, 'Source materials', 'Матеріали від замовника')}:\n{materials}\n\n"
        f"{_tl(lang, 'Reference (YouTube)', 'Референс (YouTube)')}: {reference_url}"
    )

def _build_order_preview(lang: str | None, data: dict) -> str:
    title = (data.get("title") or "").strip() or _tl(lang, "Not filled", "Не заповнено")
    budget_minor = int(data.get("budget_minor") or 0)
    revision_minor = int(data.get("revision_price_minor") or 0)
    category = _order_category_label(data.get("category"), lang)
    platform = _order_platform_label(data.get("platform"), lang)
    task_details = (data.get("task_details") or "").strip() or _tl(lang, "Not filled", "Не заповнено")
    raw_materials = (data.get("materials") or "").strip()
    if raw_materials == "__skipped__":
        materials = _tl(lang, "Skipped", "Пропущено")
    else:
        materials = raw_materials or _tl(lang, "Not filled", "Не заповнено")
    reference_url = (data.get("reference_url") or "").strip() or _tl(lang, "No reference", "Без референсу")
    return (
        f"{_tl(lang, 'Preview of your order', 'Попередній вигляд вашого оголошення')}\n\n"
        f"{_tl(lang, 'Title', 'Назва')}: {title}\n"
        f"{_tl(lang, 'Category', 'Категорія')}: {category}\n"
        f"{_tl(lang, 'Platform', 'Платформа')}: {platform}\n"
        f"{_tl(lang, 'Task details', 'Деталі завдання')}: {task_details}\n"
        f"{_tl(lang, 'Materials', 'Матеріали')}: {materials}\n"
        f"{_tl(lang, 'Reference', 'Референс')}: {reference_url}\n"
        f"{_tl(lang, 'Budget', 'Бюджет')}: {budget_minor / 100:.2f} USD\n"
        f"{_tl(lang, 'Revision price', 'Ціна правки')}: {revision_minor / 100:.2f} USD"
    )

def _parse_structured_description(description: str) -> dict:
    parsed = {
        "category": "",
        "platform": "",
        "task_details": "",
        "materials": "",
        "reference_url": "",
    }
    if not description:
        return parsed
    lines = description.splitlines()
    for line in lines:
        if line.startswith("Category: "):
            value = line.replace("Category: ", "", 1).strip().lower()
            if "ad" in value or "promo" in value:
                parsed["category"] = "ad"
            elif "youtube" in value:
                parsed["category"] = "youtube"
            elif "podcast" in value or "interview" in value:
                parsed["category"] = "podcast"
            elif "shorts" in value or "reels" in value or "tiktok" in value:
                parsed["category"] = "shorts"
            elif value:
                parsed["category"] = "other"
        elif line.startswith("Platform: "):
            value = line.replace("Platform: ", "", 1).strip().lower()
            if value in {"youtube", "instagram", "tiktok", "facebook"}:
                parsed["platform"] = value
            elif value:
                parsed["platform"] = "other"
        elif line.startswith("Task details:"):
            parsed["task_details"] = description.split("Task details:\n", 1)[-1].split("\n\n", 1)[0].strip()
        elif line.startswith("Source materials:"):
            parsed["materials"] = description.split("Source materials:\n", 1)[-1].split("\n\n", 1)[0].strip()
        elif line.startswith("Reference (YouTube): "):
            ref = line.replace("Reference (YouTube): ", "", 1).strip()
            parsed["reference_url"] = "" if ref.lower() == "no reference" else ref
    return parsed
async def _finalize_create_order(user, state: FSMContext, bot, chat_id: int, deadline_at: datetime):
    data = await state.get_data()
    description = _build_order_description(data, user.language)
    order_id = await create_order(
        client_id=user.id,
        title=data.get("title", ""),
        description=description,
        budget_minor=int(data.get("budget_minor") or 0),
        revision_price_minor=int(data.get("revision_price_minor") or 0),
        deadline_at=deadline_at,
        currency="USD",
    )

    await state.clear()
    await clear_last_bot_message(state, bot, chat_id)

    await bot.send_message(
        chat_id,
        texts.tr(user.language, f"? Order created. ID: #{order_id}", f"? Замовлення створено. ID: #{order_id}"),
        reply_markup=await get_menu_markup_for_user(user),
    )

async def _finalize_edit_order(user, state: FSMContext, bot, chat_id: int, deadline_at: datetime):
    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    description = _build_order_description(data, user.language)
    ok = await update_order_if_open(
        order_id=order_id,
        client_id=user.id,
        title=data.get("title", ""),
        description=description,
        budget_minor=int(data.get("budget_minor") or 0),
        revision_price_minor=int(data.get("revision_price_minor") or 0),
        deadline_at=deadline_at,
    )

    await state.clear()

    if not ok:
        await bot.send_message(
            chat_id,
            _t(user, "Order cannot be edited. It may already have proposals.", "Замовлення не можна редагувати. Можливо, воно вже має пропозиції."),
        )
        return

    await bot.send_message(
        chat_id,
        _t(user, "? Order updated.", "? Замовлення оновлено."),
        reply_markup=await get_menu_markup_for_user(user),
    )

# ---------- editor order viewing ----------

@router.callback_query(F.data.startswith("editor:order_view:"))
async def editor_order_view(call: CallbackQuery, state: FSMContext):
    try:
        user = await get_user_by_telegram_id(call.from_user.id)
        if not user:
            await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
            return
        
        # Parse order_id
        try:
            order_id = int(call.data.split(":")[-1])
        except (ValueError, IndexError):
            await call.answer(texts.t("order_invalid", user.language), show_alert=True)
            return
        
        # Get offset from state or default
        data = await state.get_data()
        offset = data.get("editor_orders_offset", 0)
        total = data.get("editor_orders_total", 0)
        
        # Get order details
        order = await get_order_by_id(order_id)
        if not order:
            await call.answer(texts.t("order_not_found", user.language), show_alert=True)
            return
        
        # Check if order is still open
        if order.get("status") != "open":
            await call.answer(texts.t("order_no_longer_available", user.language), show_alert=True)
            return
        
        # Format order details
        title = order.get("title", "?")
        description = order.get("description", "?")
        budget = order.get("budget_minor", 0) / 100
        currency = order.get("currency", "USD")
        deadline = order.get("deadline_at", "?")
        
        budget_label = texts.t("order_budget", user.language)
        deadline_label = texts.t("order_deadline", user.language)
        details_label = texts.t("order_details", user.language)
        
        text = (
            f"📋 <b>{title}</b>\n\n"
            f"💰 <b>{budget_label}</b> {budget} {currency}\n"
            f"📅 <b>{deadline_label}</b> {deadline}\n\n"
            f"📝 <b>{details_label}</b>\n{description}\n"
        )
        
        await state.update_data(editor_orders_offset=offset, editor_orders_total=total)
        await send_clean_from_call(
            call,
            state,
            text,
            reply_markup=kb_editor_order_detail(order_id, offset, total, user.language),
        )
        await call.answer()
    except Exception as e:
        print(f"Error in editor_order_view: {e}")
        await call.answer(texts.tr(user.language if 'user' in locals() else None, "Error", "Помилка"), show_alert=True)

@router.callback_query(F.data.startswith("editor:order_apply:"))
async def editor_order_apply(call: CallbackQuery, state: FSMContext):
    try:
        user = await get_user_by_telegram_id(call.from_user.id)
        if not user:
            await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
            return
        
        try:
            order_id = int(call.data.split(":")[-1])
        except (ValueError, IndexError):
            await call.answer(texts.t("order_invalid", user.language), show_alert=True)
            return
        
        # Check if editor already applied
        order = await get_order_by_id(order_id)
        if not order or order.get("status") != "open":
            await call.answer(texts.t("order_not_available", user.language), show_alert=True)
            return
        
        # Store order_id for proposal flow and enter state
        await state.set_state(EditorProposal.waiting_price)
        await state.update_data(order_id=order_id, editor_id=user.id)
        
        await call.answer()
        await send_clean_from_call(
            call,
            state,
            texts.t("order_propose_price", user.language),
            reply_markup=kb_nav_menu_help(back="common:menu", lang=user.language),
        )
    except Exception as e:
        print(f"Error in editor_order_apply: {e}")
        await call.answer(texts.tr(user.language if 'user' in locals() else None, "Error", "Помилка"), show_alert=True)

@router.callback_query(F.data.startswith("editor:order_chat:"))
async def editor_order_chat(call: CallbackQuery, state: FSMContext):
    try:
        user = await get_user_by_telegram_id(call.from_user.id)
        if not user:
            await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
            return
        
        try:
            order_id = int(call.data.split(":")[-1])
        except (ValueError, IndexError):
            await call.answer(texts.t("order_invalid", user.language), show_alert=True)
            return
        
        # Check if order exists and is open
        order = await get_order_by_id(order_id)
        if not order or order.get("status") != "open":
            await call.answer(texts.t("order_not_available", user.language), show_alert=True)
            return
        
        await call.answer(texts.t("order_chat_available_after_apply", user.language), show_alert=True)
    except Exception as e:
        print(f"Error in editor_order_chat: {e}")

@router.callback_query(F.data.startswith("editor:order_propose:"))
async def editor_order_propose(call: CallbackQuery, state: FSMContext):
    try:
        user = await get_user_by_telegram_id(call.from_user.id)
        if not user:
            await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
            return
        
        try:
            order_id = int(call.data.split(":")[-1])
        except (ValueError, IndexError):
            await call.answer(texts.tr(user.language, "Invalid order.", "Невірний заказ."), show_alert=True)
            return
        
        # Check if order exists and is open
        order = await get_order_by_id(order_id)
        if not order or order.get("status") != "open":
            await call.answer(texts.tr(user.language, "Order not available.", "Заказ недоступний."), show_alert=True)
            return
        
        # Store order_id for proposal flow and enter state
        await state.set_state(EditorProposal.waiting_price)
        await state.update_data(order_id=order_id, editor_id=user.id)
        
        await call.answer()
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Enter your proposed price (in numbers only, e.g., 50.5):", "Введіть вашу запропоновану ціну (тільки цифри, напр. 50.5):"),
            reply_markup=kb_nav_menu_help(back="common:menu", lang=user.language),
        )
    except Exception as e:
        print(f"Error in editor_order_propose: {e}")
        await call.answer(texts.tr(user.language if 'user' in locals() else None, "Error", "Помилка"), show_alert=True)

# ---------- create order flow ----------

@router.callback_query(F.data == "client:create_order")
async def create_order_start(call: CallbackQuery, state: FSMContext):
    try:
        user = await get_user_by_telegram_id(call.from_user.id)
        if not user:
            await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
            return
        if user.role != "client":
            await call.answer(texts.tr(user.language, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."), show_alert=True)
            return

        await state.clear()
        await state.set_state(CreateOrder.waiting_title)
        await state.update_data(
            title="",
            category="",
            platform="",
            task_details="",
            materials="",
            reference_url="",
            budget_minor=0,
            revision_price_minor=0,
        )
        data = await state.get_data()
        await call.answer()
        await send_clean_from_call(
            call,
            state,
            f"{_build_order_preview(user.language, data)}\n\n"
            + texts.tr(
                user.language,
                "Tap a button to fill a field. Start with title.",
                "Натисніть кнопку, щоб заповнити поле. Почніть з назви.",
            ),
            reply_markup=kb_order_create_form(user.language),
        )
    except Exception as e:
        print(f"Error in create_order_start: {e}")
        await call.answer(f"Error: {str(e)}", show_alert=True)

@router.callback_query(F.data.startswith("order:back:"))
async def create_order_back(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    if user.role != "client":
        await state.clear()
        await call.message.answer(texts.tr(user.language, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        await call.answer()
        return

    action = call.data.split(":")[-1]
    await call.answer()

    if action == "menu":
        await state.clear()
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Menu:", "Меню:"),
            reply_markup=await get_menu_markup_for_user(user),
        )
        return

    if action == "title":
        await state.set_state(CreateOrder.waiting_title)
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Enter order title:", "Введіть назву замовлення:"),
            reply_markup=kb_nav_menu_help(back="order:back:menu", lang=user.language),
        )
        return

    if action == "category":
        await state.set_state(CreateOrder.waiting_category)
        await send_clean_from_call(
            call,
            state,
            texts.tr(
                user.language,
                "Step 2/8. Choose video category:",
                "Крок 2/8. Оберіть категорію відео:",
            ),
            reply_markup=kb_order_category(user.language),
        )
        return

    if action == "platform":
        await state.set_state(CreateOrder.waiting_platform)
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Step 3/8. Choose target platform:", "Крок 3/8. Оберіть платформу публікації:"),
            reply_markup=kb_order_platform(user.language),
        )
        return

    if action == "task_details":
        await state.set_state(CreateOrder.waiting_task_details)
        await send_clean_from_call(
            call,
            state,
            texts.tr(
                user.language,
                "Step 4/8. Describe exactly what should be done (structure, style, important moments).",
                "Крок 4/8. Опишіть, що саме треба зробити (структура, стиль, важливі моменти).",
            ),
            reply_markup=kb_nav_menu_help(back="order:back:platform", lang=user.language),
        )
        return

    if action == "materials":
        await state.set_state(CreateOrder.waiting_materials)
        await send_clean_from_call(
            call,
            state,
            texts.tr(
                user.language,
                "Step 5/8. Paste links to source materials (Google Drive, Dropbox, OneDrive, Mega, WeTransfer, MediaFire, PixelDrain).",
                "Крок 5/8. Вставте посилання на матеріали (Google Drive, Dropbox, OneDrive, Mega, WeTransfer, MediaFire, PixelDrain).",
            ),
            reply_markup=kb_order_materials_controls(user.language),
        )
        return

    if action == "reference":
        await state.set_state(CreateOrder.waiting_reference_url)
        await send_clean_from_call(
            call,
            state,
            texts.tr(
                user.language,
                "Step 6/8. Paste a YouTube link as a reference (example style). You can skip this step.",
                "Крок 6/8. Вставте YouTube-посилання на приклад монтажу. Цей крок можна пропустити.",
            ),
            reply_markup=kb_order_reference_controls(user.language),
        )
        return

    if action == "budget":
        await state.set_state(CreateOrder.waiting_budget)
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Step 7/8. Enter budget in USD. Example: 50", "Крок 7/8. Введіть бюджет у USD. Приклад: 50"),
            reply_markup=kb_nav_menu_help(back="order:back:reference", lang=user.language),
        )
        return

    if action == "revision_price":
        await state.set_state(CreateOrder.waiting_revision_price)
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Step 8/8. Enter revision price in USD. Example: 10", "Крок 8/8. Введіть ціну правки у USD. Приклад: 10"),
            reply_markup=kb_nav_menu_help(back="order:back:budget", lang=user.language),
        )
        return

@router.callback_query(F.data == "order:cancel")
async def create_order_cancel(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return

    await state.clear()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        texts.tr(user.language, "OK, canceled.", "Добре, скасовано."),
        reply_markup=await get_menu_markup_for_user(user),
    )

@router.message(CreateOrder.waiting_title)
async def create_order_title(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(texts.tr(user.language, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    title = (message.text or "").strip()
    await safe_delete_message(message)

    if not title:
        await send_clean(
            message,
            state,
            texts.tr(user.language, "Title cannot be empty. Enter order title:", "Назва не може бути порожньою. Введіть назву замовлення:"),
            reply_markup=kb_nav_menu_help(back="order:back:menu", lang=user.language),
        )
        return

    await state.update_data(title=title)
    await state.set_state(CreateOrder.waiting_category)
    data = await state.get_data()
    await send_clean(
        message,
        state,
        f"{_build_order_preview(user.language, data)}\n\n"
        + texts.tr(user.language, "Step 2/8. Choose video category:", "Крок 2/8. Оберіть категорію відео:"),
        reply_markup=kb_order_category(user.language),
    )

@router.callback_query(F.data.startswith("order:create:category:"))
async def create_order_category_choose(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    await state.update_data(category=call.data.split(":")[-1])
    await state.set_state(CreateOrder.waiting_platform)
    data = await state.get_data()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 3/8. Choose target platform:', 'Крок 3/8. Оберіть платформу публікації:')}",
        reply_markup=kb_order_platform(user.language),
    )

@router.callback_query(F.data.startswith("order:create:platform:"))
async def create_order_platform_choose(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    await state.update_data(platform=call.data.split(":")[-1])
    await state.set_state(CreateOrder.waiting_task_details)
    data = await state.get_data()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 4/8. Describe exactly what should be done (structure, style, important moments).', 'Крок 4/8. Опишіть, що саме треба зробити (структура, стиль, важливі моменти).')}",
        reply_markup=kb_nav_menu_help(back="order:back:platform", lang=user.language),
    )

@router.message(CreateOrder.waiting_task_details)
async def create_order_task_details(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(texts.tr(user.language, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    description = (message.text or "").strip()
    await safe_delete_message(message)

    if not description:
        await send_clean(
            message,
            state,
            texts.tr(user.language, "Task details cannot be empty.", "Опис завдання не може бути порожнім."),
            reply_markup=kb_nav_menu_help(back="order:back:platform", lang=user.language),
        )
        return

    await state.update_data(task_details=description)
    await state.set_state(CreateOrder.waiting_materials)
    data = await state.get_data()
    await send_clean(
        message,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 5/8. Paste links to source materials (Google Drive, Dropbox, OneDrive, Mega, WeTransfer, MediaFire, PixelDrain).', 'Крок 5/8. Вставте посилання на матеріали (Google Drive, Dropbox, OneDrive, Mega, WeTransfer, MediaFire, PixelDrain).')}",
        reply_markup=kb_order_materials_controls(user.language),
    )

@router.message(CreateOrder.waiting_materials)
async def create_order_materials(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(texts.tr(user.language, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    if not raw:
        await send_clean(
            message,
            state,
            texts.tr(user.language, "Please paste material links.", "Будь ласка, вставте посилання на матеріали."),
            reply_markup=kb_order_materials_controls(user.language),
        )
        return

    if not _has_only_allowed_material_links(raw):
        await send_clean(
            message,
            state,
            texts.tr(
                user.language,
                "Only Google Drive, Dropbox, OneDrive, Mega, WeTransfer, MediaFire, and PixelDrain links are allowed for materials.",
                "Для матеріалів дозволені лише посилання Google Drive, Dropbox, OneDrive, Mega, WeTransfer, MediaFire та PixelDrain.",
            ),
            reply_markup=kb_order_materials_controls(user.language),
        )
        return

    await state.update_data(materials=raw)
    await state.set_state(CreateOrder.waiting_reference_url)
    data = await state.get_data()
    await send_clean(
        message,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 6/8. Paste a YouTube link as a reference (example style). You can skip this step.', 'Крок 6/8. Вставте YouTube-посилання на приклад монтажу. Цей крок можна пропустити.')}",
        reply_markup=kb_order_reference_controls(user.language),
    )

@router.callback_query(F.data == "order:create:materials:skip")
async def create_order_materials_skip(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    await state.update_data(materials="__skipped__")
    await state.set_state(CreateOrder.waiting_reference_url)
    data = await state.get_data()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 6/8. Paste a YouTube link as a reference (example style). You can skip this step.', 'Крок 6/8. Вставте YouTube-посилання на приклад монтажу. Цей крок можна пропустити.')}",
        reply_markup=kb_order_reference_controls(user.language),
    )

@router.callback_query(F.data == "order:create:reference:skip")
async def create_order_reference_skip(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    await state.update_data(reference_url="")
    await state.set_state(CreateOrder.waiting_budget)
    data = await state.get_data()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 7/8. Enter budget in USD. Example: 50', 'Крок 7/8. Введіть бюджет у USD. Приклад: 50')}",
        reply_markup=kb_nav_menu_help(back="order:back:reference", lang=user.language),
    )

@router.message(CreateOrder.waiting_reference_url)
async def create_order_reference_url(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(texts.tr(user.language, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)
    if not _is_valid_youtube_url(raw):
        await send_clean(
            message,
            state,
            texts.tr(
                user.language,
                "Please paste a valid YouTube URL (youtube.com or youtu.be), or press Skip.",
                "Вставте коректне посилання YouTube (youtube.com або youtu.be), або натисніть Пропустити.",
            ),
            reply_markup=kb_order_reference_controls(user.language),
        )
        return

    await state.update_data(reference_url=raw)
    await state.set_state(CreateOrder.waiting_budget)
    data = await state.get_data()
    await send_clean(
        message,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 7/8. Enter budget in USD. Example: 50', 'Крок 7/8. Введіть бюджет у USD. Приклад: 50')}",
        reply_markup=kb_nav_menu_help(back="order:back:reference", lang=user.language),
    )

@router.message(CreateOrder.waiting_budget)
async def create_order_budget(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(texts.tr(user.language, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    if not raw.isdigit():
        await send_clean(
            message,
            state,
            texts.tr(user.language, "Budget must be a number. Example: 50", "Бюджет має бути числом. Приклад: 50"),
            reply_markup=kb_nav_menu_help(back="order:back:reference", lang=user.language),
        )
        return

    await state.update_data(budget_minor=int(raw) * 100)
    await state.set_state(CreateOrder.waiting_revision_price)
    data = await state.get_data()
    await send_clean(
        message,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 8/8. Enter revision price in USD. Example: 10', 'Крок 8/8. Введіть ціну правки у USD. Приклад: 10')}",
        reply_markup=kb_nav_menu_help(back="order:back:budget", lang=user.language),
    )

@router.message(CreateOrder.waiting_revision_price)
async def create_order_revision_price(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(texts.tr(user.language, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    if not raw.isdigit():
        await send_clean(
            message,
            state,
            texts.tr(user.language, "Revision price must be a number. Example: 10", "Ціна за правки має бути числом. Приклад: 10"),
            reply_markup=kb_nav_menu_help(back="order:back:budget", lang=user.language),
        )
        return

    await state.update_data(revision_price_minor=int(raw) * 100)
    await state.set_state(CreateOrder.waiting_deadline)
    data = await state.get_data()
    await send_clean(
        message,
        state,
        f"{_build_order_preview(user.language, data)}\n\n"
        + texts.tr(
            user.language,
            "Choose a deadline or type a custom date (YYYY-MM-DD HH:MM).",
            "Оберіть термін або введіть власну дату (РРРР-ММ-ДД ГГ:ХХ).",
        ),
        reply_markup=kb_deadline_quick(back="order:back:revision_price", cancel="order:cancel", lang=user.language),
    )

@router.callback_query(F.data.startswith("deadline:"))
async def deadline_quick_select(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return

    current_state = await state.get_state()
    if current_state not in (CreateOrder.waiting_deadline.state, EditOrder.waiting_deadline.state):
        await call.answer(_t(user, "This step is no longer active.", "Цей крок більше не активний."), show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) < 2:
        await call.answer(_t(user, "Invalid data.", "Некоректні дані."), show_alert=True)
        return

    action = parts[1]
    if action == "custom":
        back_cb = "order:back:revision_price" if current_state == CreateOrder.waiting_deadline.state else "order_edit:back:revision_price"
        cancel_cb = "order:cancel" if current_state == CreateOrder.waiting_deadline.state else "order_edit:cancel"
        await call.answer()
        await send_clean_from_call(
            call,
            state,
            _t(user, "Enter deadline (YYYY-MM-DD HH:MM). Example: 2026-03-15 18:30", "Введіть термін (РРРР-ММ-ДД ГГ:ХХ). Приклад: 2026-03-15 18:30"),
            reply_markup=kb_deadline_quick(back=back_cb, cancel=cancel_cb, lang=user.language),
        )
        return

    deadline_at = None
    now = datetime.now()
    try:
        if action == "hours" and len(parts) == 3:
            deadline_at = now + timedelta(hours=int(parts[2]))
        elif action == "days" and len(parts) == 3:
            deadline_at = now + timedelta(days=int(parts[2]))
    except Exception:
        deadline_at = None

    if not deadline_at:
        await call.answer(_t(user, "Invalid deadline.", "Некоректний термін."), show_alert=True)
        return

    await call.answer()
    if current_state == CreateOrder.waiting_deadline.state:
        await _finalize_create_order(user, state, call.bot, call.message.chat.id, deadline_at)
    else:
        await _finalize_edit_order(user, state, call.bot, call.message.chat.id, deadline_at)

@router.message(CreateOrder.waiting_deadline)
async def create_order_deadline(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(texts.tr(user.language, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    try:
        deadline_at = datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except ValueError:
        await send_clean(
            message,
            state,
            texts.tr(
                user.language,
                "Deadline must be in YYYY-MM-DD HH:MM format. Example: 2026-03-15 18:30",
                "Термін має бути у форматі РРРР-ММ-ДД ГГ:ХХ. Приклад: 2026-03-15 18:30",
            ),
            reply_markup=kb_deadline_quick(back="order:back:revision_price", cancel="order:cancel", lang=user.language),
        )
        return

    await _finalize_create_order(user, state, message.bot, message.chat.id, deadline_at)

@router.callback_query(F.data == "client:my_orders")
async def my_orders(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(texts.tr(user.language, "This section is for clients only.", "Цей розділ тільки для клієнтів."), show_alert=True)
        return

    orders = await list_orders_for_client(user.id, limit=10)
    if not orders:
        await call.message.answer(texts.tr(user.language, "You have no orders yet.", "У вас ще немає замовлень."), reply_markup=await get_menu_markup_for_user(user))
        await call.answer()
        return

    text = texts.tr(user.language, "Your orders:\n\nChoose an order to view.", "Ваші замовлення:\n\nОберіть замовлення для перегляду.")
    await call.message.answer(text, reply_markup=kb_orders_list(orders, user.language))
    await call.answer()

@router.callback_query(F.data.startswith("order:view:"))
async def order_view(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(texts.tr(user.language, "This section is for clients only.", "Цей розділ тільки для клієнтів."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(texts.tr(user.language, "Invalid number.", "Некоректне число."), show_alert=True)
        return

    order = await get_order_for_client(order_id, user.id)
    if not order:
        await call.answer(texts.tr(user.language, "Order not found.", "Замовлення не знайдено."), show_alert=True)
        return

    price = f"{int(order.get('budget_minor') or 0) / 100:.2f} {order.get('currency') or 'USD'}"
    revision_price = f"{int(order.get('revision_price_minor') or 0) / 100:.2f} {order.get('currency') or 'USD'}"
    created_at = order.get("created_at")
    created_label = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "-"
    deadline_at = order.get("deadline_at")
    deadline_label = deadline_at.strftime("%Y-%m-%d %H:%M") if deadline_at else "-"

    title = order.get("title") or "-"
    description = order.get("description") or "-"
    if len(description) > 1500:
        description = description[:1497] + "..."

    allow_edit = order.get("status") == "open" and not order.get("editor_id")
    text = (
        f"{texts.tr(user.language, 'Order', 'Замовлення')} #{order['id']}\n\n"
        f"{texts.tr(user.language, 'Title', 'Назва')}: {title}\n"
        f"{texts.tr(user.language, 'Description', 'Опис')}: {description}\n"
        f"{texts.tr(user.language, 'Budget', 'Бюджет')}: {price}\n"
        f"{texts.tr(user.language, 'Revision price', 'Ціна за правки')}: {revision_price}\n"
        f"{texts.tr(user.language, 'Status', 'Статус')}: {order.get('status')}\n"
        f"{texts.tr(user.language, 'Created', 'Створено')}: {created_label}\n"
        f"{texts.tr(user.language, 'Deadline', 'Термін')}: {deadline_label}"
    )

    await call.message.answer(text, reply_markup=kb_order_detail(order_id, allow_edit=allow_edit, lang=user.language))
    await call.answer()

@router.callback_query(F.data == "order_edit:cancel")
async def order_edit_cancel(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    await state.clear()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        texts.tr(user.language, "Menu:", "Меню:"),
        reply_markup=await get_menu_markup_for_user(user),
    )

@router.callback_query(F.data.startswith("order_edit:back:"))
async def order_edit_back(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    action = call.data.split(":")[-1]
    data = await state.get_data()
    await call.answer()

    if action == "title":
        await state.set_state(EditOrder.waiting_title)
        await send_clean_from_call(
            call,
            state,
            texts.tr(user.language, "Step 1/8. Enter a short order title.", "Крок 1/8. Введіть коротку назву замовлення."),
            reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
        )
        return
    if action == "category":
        await state.set_state(EditOrder.waiting_category)
        await send_clean_from_call(
            call,
            state,
            f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 2/8. Choose video category:', 'Крок 2/8. Оберіть категорію відео:')}",
            reply_markup=kb_order_category_edit(user.language),
        )
        return
    if action == "platform":
        await state.set_state(EditOrder.waiting_platform)
        await send_clean_from_call(
            call,
            state,
            f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 3/8. Choose target platform:', 'Крок 3/8. Оберіть платформу публікації:')}",
            reply_markup=kb_order_platform_edit(user.language),
        )
        return
    if action == "task_details":
        await state.set_state(EditOrder.waiting_task_details)
        await send_clean_from_call(
            call,
            state,
            f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 4/8. Describe exactly what should be done (structure, style, important moments).', 'Крок 4/8. Опишіть, що саме треба зробити (структура, стиль, важливі моменти).')}",
            reply_markup=kb_nav_menu_help(back="order_edit:back:platform", lang=user.language),
        )
        return
    if action == "materials":
        await state.set_state(EditOrder.waiting_materials)
        await send_clean_from_call(
            call,
            state,
            f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 5/8. Paste links to source materials (Google Drive, Dropbox, OneDrive, Mega, WeTransfer, MediaFire, PixelDrain).', 'Крок 5/8. Вставте посилання на матеріали (Google Drive, Dropbox, OneDrive, Mega, WeTransfer, MediaFire, PixelDrain).')}",
            reply_markup=kb_order_materials_controls_edit(user.language),
        )
        return
    if action == "reference":
        await state.set_state(EditOrder.waiting_reference_url)
        await send_clean_from_call(
            call,
            state,
            f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 6/8. Paste a YouTube link as a reference (example style). You can skip this step.', 'Крок 6/8. Вставте YouTube-посилання на приклад монтажу. Цей крок можна пропустити.')}",
            reply_markup=kb_order_reference_controls_edit(user.language),
        )
        return
    if action == "budget":
        await state.set_state(EditOrder.waiting_budget)
        await send_clean_from_call(
            call,
            state,
            f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 7/8. Enter budget in USD. Example: 50', 'Крок 7/8. Введіть бюджет у USD. Приклад: 50')}",
            reply_markup=kb_nav_menu_help(back="order_edit:back:reference", lang=user.language),
        )
        return
    if action == "revision_price":
        await state.set_state(EditOrder.waiting_revision_price)
        await send_clean_from_call(
            call,
            state,
            f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 8/8. Enter revision price in USD. Example: 10', 'Крок 8/8. Введіть ціну правки у USD. Приклад: 10')}",
            reply_markup=kb_nav_menu_help(back="order_edit:back:budget", lang=user.language),
        )
        return

@router.callback_query(F.data.startswith("order:edit:"))
async def order_edit_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(texts.tr(user.language, "This section is for clients only.", "Цей розділ тільки для замовників."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(texts.tr(user.language, "Invalid number.", "Некоректне число."), show_alert=True)
        return

    order = await get_order_for_client(order_id, user.id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await call.answer(texts.tr(user.language, "Order cannot be edited.", "Замовлення не можна редагувати."), show_alert=True)
        return

    structured = _parse_structured_description(order.get("description") or "")
    await state.clear()
    await state.set_state(EditOrder.waiting_title)
    await state.update_data(
        order_id=order_id,
        title=order.get("title") or "",
        category=structured.get("category") or "",
        platform=structured.get("platform") or "",
        task_details=structured.get("task_details") or "",
        materials=structured.get("materials") or "",
        reference_url=structured.get("reference_url") or "",
        budget_minor=int(order.get("budget_minor") or 0),
        revision_price_minor=int(order.get("revision_price_minor") or 0),
    )
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        texts.tr(
            user.language,
            f"Step 1/8. Enter new title (current: {order.get('title') or '-'})",
            f"Крок 1/8. Введіть нову назву (поточна: {order.get('title') or '-'})",
        ),
        reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
    )

@router.message(EditOrder.waiting_title)
async def order_edit_title(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(_t(user, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    title = (message.text or "").strip()
    await safe_delete_message(message)
    if not title:
        await send_clean(
            message,
            state,
            _t(user, "Title cannot be empty.", "Назва не може бути порожньою."),
            reply_markup=kb_nav_menu_help(back="order_edit:cancel", lang=user.language),
        )
        return

    await state.update_data(title=title)
    await state.set_state(EditOrder.waiting_category)
    data = await state.get_data()
    await send_clean(
        message,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 2/8. Choose video category:', 'Крок 2/8. Оберіть категорію відео:')}",
        reply_markup=kb_order_category_edit(user.language),
    )

@router.callback_query(F.data.startswith("order:edit:category:"))
async def order_edit_category_choose(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    await state.update_data(category=call.data.split(":")[-1])
    await state.set_state(EditOrder.waiting_platform)
    data = await state.get_data()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 3/8. Choose target platform:', 'Крок 3/8. Оберіть платформу публікації:')}",
        reply_markup=kb_order_platform_edit(user.language),
    )

@router.callback_query(F.data.startswith("order:edit:platform:"))
async def order_edit_platform_choose(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    await state.update_data(platform=call.data.split(":")[-1])
    await state.set_state(EditOrder.waiting_task_details)
    data = await state.get_data()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 4/8. Describe exactly what should be done (structure, style, important moments).', 'Крок 4/8. Опишіть, що саме треба зробити (структура, стиль, важливі моменти).')}",
        reply_markup=kb_nav_menu_help(back="order_edit:back:platform", lang=user.language),
    )

@router.message(EditOrder.waiting_task_details)
async def order_edit_task_details(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(_t(user, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    description = (message.text or "").strip()
    await safe_delete_message(message)
    if not description:
        await send_clean(
            message,
            state,
            _t(user, "Task details cannot be empty.", "Опис завдання не може бути порожнім."),
            reply_markup=kb_nav_menu_help(back="order_edit:back:platform", lang=user.language),
        )
        return

    await state.update_data(task_details=description)
    await state.set_state(EditOrder.waiting_materials)
    data = await state.get_data()
    await send_clean(
        message,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 5/8. Paste links to source materials (Google Drive, Dropbox, OneDrive, Mega, WeTransfer, MediaFire, PixelDrain).', 'Крок 5/8. Вставте посилання на матеріали (Google Drive, Dropbox, OneDrive, Mega, WeTransfer, MediaFire, PixelDrain).')}",
        reply_markup=kb_order_materials_controls_edit(user.language),
    )

@router.message(EditOrder.waiting_materials)
async def order_edit_materials(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(_t(user, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)
    if not raw:
        await send_clean(
            message,
            state,
            _t(user, "Please paste material links.", "Будь ласка, вставте посилання на матеріали."),
            reply_markup=kb_order_materials_controls_edit(user.language),
        )
        return

    if not _has_only_allowed_material_links(raw):
        await send_clean(
            message,
            state,
            _t(
                user,
                "Only Google Drive, Dropbox, OneDrive, Mega, WeTransfer, MediaFire, and PixelDrain links are allowed for materials.",
                "Для матеріалів дозволені лише посилання Google Drive, Dropbox, OneDrive, Mega, WeTransfer, MediaFire та PixelDrain.",
            ),
            reply_markup=kb_order_materials_controls_edit(user.language),
        )
        return

    await state.update_data(materials=raw)
    await state.set_state(EditOrder.waiting_reference_url)
    data = await state.get_data()
    await send_clean(
        message,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 6/8. Paste a YouTube link as a reference (example style). You can skip this step.', 'Крок 6/8. Вставте YouTube-посилання на приклад монтажу. Цей крок можна пропустити.')}",
        reply_markup=kb_order_reference_controls_edit(user.language),
    )

@router.callback_query(F.data == "order:edit:materials:skip")
async def order_edit_materials_skip(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    await state.update_data(materials="__skipped__")
    await state.set_state(EditOrder.waiting_reference_url)
    data = await state.get_data()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 6/8. Paste a YouTube link as a reference (example style). You can skip this step.', 'Крок 6/8. Вставте YouTube-посилання на приклад монтажу. Цей крок можна пропустити.')}",
        reply_markup=kb_order_reference_controls_edit(user.language),
    )

@router.callback_query(F.data == "order:edit:reference:skip")
async def order_edit_reference_skip(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(texts.tr(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    await state.update_data(reference_url="")
    await state.set_state(EditOrder.waiting_budget)
    data = await state.get_data()
    await call.answer()
    await send_clean_from_call(
        call,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 7/8. Enter budget in USD. Example: 50', 'Крок 7/8. Введіть бюджет у USD. Приклад: 50')}",
        reply_markup=kb_nav_menu_help(back="order_edit:back:reference", lang=user.language),
    )

@router.message(EditOrder.waiting_reference_url)
async def order_edit_reference_url(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(_t(user, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)
    if not _is_valid_youtube_url(raw):
        await send_clean(
            message,
            state,
            _t(
                user,
                "Please paste a valid YouTube URL (youtube.com or youtu.be), or press Skip.",
                "Вставте коректне посилання YouTube (youtube.com або youtu.be), або натисніть Пропустити.",
            ),
            reply_markup=kb_order_reference_controls_edit(user.language),
        )
        return

    await state.update_data(reference_url=raw)
    await state.set_state(EditOrder.waiting_budget)
    data = await state.get_data()
    await send_clean(
        message,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 7/8. Enter budget in USD. Example: 50', 'Крок 7/8. Введіть бюджет у USD. Приклад: 50')}",
        reply_markup=kb_nav_menu_help(back="order_edit:back:reference", lang=user.language),
    )

@router.message(EditOrder.waiting_budget)
async def order_edit_budget(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(_t(user, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)
    if not raw.isdigit():
        await send_clean(
            message,
            state,
            _t(user, "Budget must be a number. Example: 50", "Бюджет має бути числом. Приклад: 50"),
            reply_markup=kb_nav_menu_help(back="order_edit:back:reference", lang=user.language),
        )
        return

    await state.update_data(budget_minor=int(raw) * 100)
    await state.set_state(EditOrder.waiting_revision_price)
    data = await state.get_data()
    await send_clean(
        message,
        state,
        f"{_build_order_preview(user.language, data)}\n\n{_t(user, 'Step 8/8. Enter revision price in USD. Example: 10', 'Крок 8/8. Введіть ціну правки у USD. Приклад: 10')}",
        reply_markup=kb_nav_menu_help(back="order_edit:back:budget", lang=user.language),
    )

@router.message(EditOrder.waiting_revision_price)
async def order_edit_revision_price(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(_t(user, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)
    if not raw.isdigit():
        await send_clean(
            message,
            state,
            _t(user, "Revision price must be a number. Example: 10", "Ціна правки має бути числом. Приклад: 10"),
            reply_markup=kb_nav_menu_help(back="order_edit:back:budget", lang=user.language),
        )
        return

    await state.update_data(revision_price_minor=int(raw) * 100)
    await state.set_state(EditOrder.waiting_deadline)
    data = await state.get_data()
    await send_clean(
        message,
        state,
        f"{_build_order_preview(user.language, data)}\n\n"
        + _t(user, "Choose a deadline or type a custom date (YYYY-MM-DD HH:MM).", "Оберіть термін або введіть власну дату (РРРР-ММ-ДД ГГ:ХХ)."),
        reply_markup=kb_deadline_quick(back="order_edit:back:revision_price", cancel="order_edit:cancel", lang=user.language),
    )

@router.message(EditOrder.waiting_deadline)
async def order_edit_deadline(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "client":
        await state.clear()
        await message.answer(_t(user, "Only clients can create orders.", "Тільки клієнти можуть створювати замовлення."))
        return

    raw = (message.text or "").strip()
    await safe_delete_message(message)

    try:
        deadline_at = datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except ValueError:
        await send_clean(
            message,
            state,
            _t(
                user,
                "Deadline must be in YYYY-MM-DD HH:MM format. Example: 2026-03-15 18:30",
                "Термін має бути у форматі РРРР-ММ-ДД ГГ:ХХ. Приклад: 2026-03-15 18:30",
            ),
            reply_markup=kb_deadline_quick(back="order_edit:back:revision_price", cancel="order_edit:cancel", lang=user.language),
        )
        return

    await _finalize_edit_order(user, state, message.bot, message.chat.id, deadline_at)

@router.callback_query(F.data.startswith("order:details:"))
async def order_details_for_editor(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "Тільки для монтажерів."), show_alert=True)
        return

    p = await get_editor_profile(user.id)
    if not p or p.get("verification_status") != "verified":
        await call.answer(_t(user, "⛔ Please verify first.", "⛔ Спочатку пройдіть верифікацію."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "Некоректне число."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await call.answer(_t(user, "Order not available.", "Замовлення недоступне."), show_alert=True)
        return

    price = f"{int(order.get('budget_minor') or 0) / 100:.2f} {order.get('currency') or 'USD'}"
    revision_price = f"{int(order.get('revision_price_minor') or 0) / 100:.2f} {order.get('currency') or 'USD'}"
    created_at = order.get('created_at')
    created_label = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "-"
    deadline_at = order.get('deadline_at')
    deadline_label = deadline_at.strftime("%Y-%m-%d %H:%M") if deadline_at else "-"

    title = order.get('title') or '-'
    description = order.get('description') or '-'
    if len(description) > 1500:
        description = description[:1497] + '...'

    text = (
        f"{_t(user, 'Order', 'Замовлення')} #{order['id']}\n\n"
        f"{_t(user, 'Title', 'Назва')}: {title}\n"
        f"{_t(user, 'Description', 'Опис')}: {description}\n"
        f"{_t(user, 'Budget', 'Бюджет')}: {price}\n"
        f"{_t(user, 'Revision price', 'Ціна за правки')}: {revision_price}\n"
        f"{_t(user, 'Created', 'Створено')}: {created_label}\n"
        f"{_t(user, 'Deadline', 'Термін')}: {deadline_label}"
    )

    await call.message.answer(text, reply_markup=kb_editor_order_detail(order_id, user.language))
    await call.answer()


@router.callback_query(F.data.startswith("order:chat:"))
async def order_chat_request(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "Тільки для монтажерів."), show_alert=True)
        return

    p = await get_editor_profile(user.id)
    if not p or p.get("verification_status") != "verified":
        await call.answer(_t(user, "⛔ Please verify first.", "⛔ Спочатку пройдіть верифікацію."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await call.answer(_t(user, "Order not available.", "?????????? ??????????."), show_alert=True)
        return

    await state.clear()
    await state.set_state(ChatRequest.waiting_text)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(_t(user, "Write a chat request to the client:", "???????? ????? ?????? ?? ??? ??? ?????????:"))

@router.message(ChatRequest.waiting_text)
async def order_chat_request_text(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer(_t(user, "Editors only.", "???????? ???? ??????????."))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer(_t(user, "Text cannot be empty.", "????? ?? ??????? ???? ????????."))
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await state.clear()
        await message.answer(_t(user, "Order not available.", "?????????? ??????????."))
        return

    client = await get_user_by_id(int(order['client_id']))
    if client:
        editor_name = user.display_name or user.username or f"id:{user.telegram_id}"
        editor_username = f"@{user.username}" if user.username else ""
        await message.bot.send_message(
            client.telegram_id,
            _t(client, f"Chat request for order #{order_id} from {editor_name} {editor_username}:\n{text}", f"????? ?? ??? ?? ?????????? #{order_id} ??? {editor_name} {editor_username}:\n{text}"),
        )

    await state.clear()
    await message.answer(_t(user, "Request sent to the client.", "????? ????????? ?????????."))

@router.callback_query(F.data.startswith("order:proposal:"))
async def order_proposal_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "???????? ???? ??????????."), show_alert=True)
        return

    p = await get_editor_profile(user.id)
    if not p or p.get("verification_status") != "verified":
        await call.answer(_t(user, "? Please verify first.", "? ???????? ???????? ???????????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await call.answer(_t(user, "Order not available.", "?????????? ??????????."), show_alert=True)
        return

    await state.clear()
    await state.set_state(EditorProposal.waiting_price)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(_t(user, "Enter your price in USD (number). Example: 80", "??????? ???? ???? ? ??????? (?????). ?????????: 80"))

@router.message(EditorProposal.waiting_price)
async def order_proposal_price(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer(_t(user, "Editors only.", "???????? ???? ??????????."))
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer(_t(user, "Price must be a number. Example: 80", "???? ??? ???? ??????. ?????????: 80"))
        return

    await state.update_data(proposal_price=int(raw) * 100)
    await state.set_state(EditorProposal.waiting_comment)
    await message.answer(_t(user, "Short comment for the proposal (single message).", "???????? ???????? ?? ?????????? (????? ????? ?????????????)."))

@router.message(EditorProposal.waiting_comment)
async def order_proposal_comment(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer(_t(user, "Editors only.", "???????? ???? ??????????."))
        return

    comment = (message.text or "").strip()
    if not comment:
        await message.answer(_t(user, "Write a short comment.", "???????? ???????? ????????."))
        return

    data = await state.get_data()
    order_id = int(data.get('order_id') or 0)
    order = await get_order_by_id(order_id)
    if not order or order.get('status') != 'open' or order.get('editor_id'):
        await state.clear()
        await message.answer(_t(user, "Order not available.", "?????????? ??????????."))
        return

    client = await get_user_by_id(int(order['client_id']))
    if client:
        price = f"{int(data.get('proposal_price') or 0) / 100:.2f} {order.get('currency') or 'USD'}"
        editor_name = user.display_name or user.username or f"id:{user.telegram_id}"
        editor_username = f"@{user.username}" if user.username else ""
        await message.bot.send_message(
            client.telegram_id,
            _t(client, f"Proposal for order #{order_id} from {editor_name} {editor_username}:\n", f"?????????? ?? ?????????? #{order_id} ??? {editor_name} {editor_username}:\n")
            + _t(client, f"Price: {price}\n", f"????: {price}\n")
            + _t(client, f"Comment: {comment}", f"????????: {comment}"),
            reply_markup=kb_proposal_actions(order_id, user.id, int(data.get("proposal_price") or 0), client.language),
        )

    await state.clear()
    await message.answer(_t(user, "Proposal sent to the client.", "?????????? ????????? ?????????."))

@router.callback_query(F.data.startswith("proposal:accept:"))
async def proposal_accept(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(_t(user, "Clients only.", "???????? ???? ?????????."), show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) not in (4, 5):
        await call.answer(_t(user, "Invalid data.", "??????? ????."), show_alert=True)
        return

    try:
        order_id = int(parts[2])
        editor_id = int(parts[3])
        proposal_price_minor = int(parts[4]) if len(parts) == 5 and parts[4].isdigit() else None
    except ValueError:
        await call.answer(_t(user, "Invalid data.", "??????? ????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("client_id") != user.id:
        await call.answer(_t(user, "Order not found.", "?????????? ?? ????????."), show_alert=True)
        return
    if order.get("status") != "open" or order.get("editor_id"):
        await call.answer(_t(user, "Order not available.", "?????????? ??????????."), show_alert=True)
        return

    agreed_price_minor = int(proposal_price_minor or order.get("budget_minor") or 0)
    ok = await accept_order(order_id, editor_id, agreed_price_minor)
    if not ok:
        await call.answer(_t(user, "Failed to accept the order.", "?? ??????? ???????? ??????????."), show_alert=True)
        return

    editor = await get_user_by_id(editor_id)
    if editor:
        await call.bot.send_message(
            editor.telegram_id,
            _t(editor, f"Order #{order_id} accepted by the client.", f"?????????? #{order_id} ???????? ??????????."),
            reply_markup=kb_deal_menu(order_id, editor.language, "editor", "accepted"),
        )

    payment_link = None
    payment_id = ""
    try:
        payment_link, payment_id = await create_payment_link(
            order_id=order_id,
            amount_minor=agreed_price_minor,
            currency=(order.get("currency") or "USD").lower(),
            customer_email=None,
            order_title=order.get("title") or "",
        )
    except Exception:
        payment_link = None

    if payment_link:
        await set_payment_link(order_id, payment_link, payment_id or "")

    amount_label = f"{agreed_price_minor / 100:.2f} {order.get('currency') or 'USD'}"
    if payment_link:
        await call.message.answer(
            _t(
                user,
                f"? Order accepted!\nYour editor is ready to start.\nAwaiting payment.\nTotal to pay: {amount_label}\n\nPay here: {payment_link}",
                f"? ?????????? ????????!\n??? ???????? ??????? ??????.\n?????? ??????.\n?? ??????: {amount_label}\n\n????????: {payment_link}",
            )
        )
    else:
        await call.message.answer(
            _t(
                user,
                f"? Order accepted!\nYour editor is ready to start.\nAwaiting payment.\nTotal to pay: {amount_label}",
                f"? ?????????? ????????!\n??? ???????? ??????? ??????.\n?????? ??????.\n?? ??????: {amount_label}",
            )
        )
    await call.answer(_t(user, "Order accepted.", "?????????? ????????."), show_alert=True)

@router.callback_query(F.data.startswith("proposal:reject:"))
async def proposal_reject(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(_t(user, "Clients only.", "???????? ???? ?????????."), show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer(_t(user, "Invalid data.", "??????? ????."), show_alert=True)
        return

    try:
        order_id = int(parts[2])
        editor_id = int(parts[3])
    except ValueError:
        await call.answer(_t(user, "Invalid data.", "??????? ????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("client_id") != user.id:
        await call.answer(_t(user, "Order not found.", "?????????? ?? ????????."), show_alert=True)
        return

    editor = await get_user_by_id(editor_id)
    if editor:
        await call.bot.send_message(editor.telegram_id, _t(editor, f"Client rejected your proposal for order #{order_id}.", f"???????? ???????? ?????????? ?? ?????????? #{order_id}."))

    await call.answer(_t(user, "Rejected.", "?????????."), show_alert=True)

@router.callback_query(F.data.startswith("proposal:chat:"))
async def proposal_chat(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(_t(user, "Clients only.", "???????? ???? ?????????."), show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer(_t(user, "Invalid data.", "??????? ????."), show_alert=True)
        return

    try:
        order_id = int(parts[2])
        editor_id = int(parts[3])
    except ValueError:
        await call.answer(_t(user, "Invalid data.", "??????? ????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("client_id") != user.id:
        await call.answer(_t(user, "Order not found.", "?????????? ?? ????????."), show_alert=True)
        return

    editor = await get_user_by_id(editor_id)
    if editor:
        client_name = user.display_name or user.username or f"id:{user.telegram_id}"
        client_username = f"@{user.username}" if user.username else ""
        await call.bot.send_message(
            editor.telegram_id,
            _t(
                editor,
                f"Client {client_name} {client_username} wants to start a chat about order #{order_id}.",
                f"???????? {client_name} {client_username} ???? ?????? ??? ?? ?????????? #{order_id}.",
            ),
        )

    await call.answer(_t(user, "Request sent to the editor.", "????? ????????? ?????????."), show_alert=True)

# ---------- Revision and completion handlers ----------

@router.callback_query(F.data.startswith("order:revision:request:"))
async def revision_request_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(_t(user, "Clients only.", "???????? ???? ?????????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid order id.", "Некоректний id угоди."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("client_id") != user.id or order.get("status") != "accepted":
        await call.answer(_t(user, "Order not found or not available.", "Замовлення не знайдено або недоступне."), show_alert=True)
        return

    await state.clear()
    await state.set_state(RevisionRequest.waiting_description)
    await state.update_data(order_id=order_id)

    await call.message.edit_text(
        _t(user, "📝 Describe the revisions you need:", "📝 Опишіть потрібні правки:"),
        reply_markup=kb_nav_menu_help(back=f"order:menu:{order_id}", lang=user.language)
    )
    await call.answer()

@router.message(RevisionRequest.waiting_description)
async def revision_request_description(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user.role != "client":
        await state.clear()
        return

    description = (message.text or "").strip()
    if not description:
        await message.answer(_t(user, "Please describe the revisions.", "Будь ласка, опишіть правки."))
        return

    await state.update_data(revision_description=description)
    await state.set_state(RevisionRequest.waiting_price)

    await message.answer(
        _t(user, "💰 Enter the price for these revisions (in USD):", "💰 Введіть ціну за ці правки (в USD):"),
        reply_markup=kb_nav_menu_help(back="cancel", lang=user.language)
    )

@router.message(RevisionRequest.waiting_price)
async def revision_request_price(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user.role != "client":
        await state.clear()
        return

    try:
        price = float((message.text or "").strip())
        if price <= 0:
            raise ValueError()
        price_minor = int(price * 100)
    except ValueError:
        await message.answer(_t(user, "Please enter a valid price (e.g., 25.50).", "Будь ласка, введіть коректну ціну (наприклад, 25.50)."))
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    description = data.get("revision_description")

    if not order_id or not description:
        await state.clear()
        await message.answer(_t(user, "Session expired. Please try again.", "Сесія закінчилася. Спробуйте ще раз."))
        return

    # Request revision
    ok = await request_revision(order_id, description, price_minor)
    if not ok:
        await state.clear()
        await message.answer(_t(user, "Failed to request revision.", "Не вдалося запросити правки."))
        return

    # Notify editor
    order = await get_order_by_id(order_id)
    if order and order.get("editor_id"):
        editor = await get_user_by_id(order["editor_id"])
        if editor:
            await message.bot.send_message(
                editor.telegram_id,
                _t(editor, f"📝 Client requested revisions for order #{order_id}:\n{description}\n\n💰 Proposed price: ${price:.2f}", f"📝 Замовник запросив правки до замовлення #{order_id}:\n{description}\n\n💰 Запропонована ціна: ${price:.2f}"),
                reply_markup=kb_revision_response_menu(order_id, description, price_minor, editor.language)
            )

    await state.clear()
    await message.answer(
        _t(user, "✅ Revision request sent to the editor.", "✅ Запит на правки надіслано монтажеру."),
        reply_markup=await get_menu_markup_for_user(user)
    )

@router.callback_query(F.data.startswith("revision:accept:"))
async def revision_accept(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "Напишіть /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "Тільки монтажники."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid order id.", "Некоректний id угоди."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id or order.get("revision_status") != "requested":
        await call.answer(_t(user, "Revision request not found.", "Запит на правки не знайдено."), show_alert=True)
        return

    # Accept revision
    ok = await respond_to_revision(order_id, True)
    if not ok:
        await call.answer(_t(user, "Failed to accept revision.", "Не вдалося прийняти правки."), show_alert=True)
        return

    # Create payment link for revision
    revision_price = order.get("revision_price_minor", 0)
    payment_link, payment_id = await create_payment_link(
        order_id=order_id,
        amount_minor=revision_price,
        currency=(order.get("currency") or "USD").lower(),
        customer_email=None,
        order_title=f"Revision for order #{order_id}",
    )

    if payment_link:
        await set_revision_payment_link(order_id, payment_link, payment_id or "")

    # Notify client
    client = await get_user_by_id(order["client_id"])
    if client:
        price_text = f"{revision_price / 100:.2f} USD"
        await call.bot.send_message(
            client.telegram_id,
            _t(client, f"✅ Editor accepted your revision request for order #{order_id}.\n💰 Pay for revisions: {price_text}\n\n{payment_link}", f"✅ Монтажер прийняв ваш запит на правки до замовлення #{order_id}.\n💰 Сплатіть за правки: {price_text}\n\n{payment_link}")
        )

    await call.message.edit_text(_t(user, "✅ Revision accepted. Payment link sent to client.", "✅ Правки прийнято. Посилання на оплату надіслано замовнику."))
    await call.answer()

@router.callback_query(F.data.startswith("revision:counter:"))
async def revision_counter_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "???????? ???? ??????????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid order id.", "Некоректний id угоди."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id or order.get("revision_status") != "requested":
        await call.answer(_t(user, "Revision request not found.", "Запит на правки не знайдено."), show_alert=True)
        return

    await state.clear()
    await state.set_state(RevisionCounter.waiting_price)
    await state.update_data(order_id=order_id)

    await call.message.edit_text(
        _t(user, "💰 Enter your counter price for the revisions (in USD):", "💰 Введіть вашу зустрічну ціну за правки (в USD):"),
        reply_markup=kb_nav_menu_help(back=f"revision:menu:{order_id}", lang=user.language)
    )
    await call.answer()

@router.message(RevisionCounter.waiting_price)
async def revision_counter_price(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user.role != "editor":
        await state.clear()
        return

    try:
        price = float((message.text or "").strip())
        if price <= 0:
            raise ValueError()
        counter_price_minor = int(price * 100)
    except ValueError:
        await message.answer(_t(user, "Please enter a valid price (e.g., 25.50).", "Будь ласка, введіть коректну ціну (наприклад, 25.50)."))
        return

    data = await state.get_data()
    order_id = data.get("order_id")

    if not order_id:
        await state.clear()
        await message.answer(_t(user, "Session expired. Please try again.", "Сесія закінчилася. Спробуйте ще раз."))
        return

    # Accept revision with counter price
    ok = await respond_to_revision(order_id, True, counter_price_minor)
    if not ok:
        await state.clear()
        await message.answer(_t(user, "Failed to propose counter price.", "Не вдалося запропонувати зустрічну ціну."))
        return

    # Create payment link for revision
    payment_link, payment_id = await create_payment_link(
        order_id=order_id,
        amount_minor=counter_price_minor,
        currency="usd",
        customer_email=None,
        order_title=f"Revision for order #{order_id}",
    )

    if payment_link:
        await set_revision_payment_link(order_id, payment_link, payment_id or "")

    # Notify client
    order = await get_order_by_id(order_id)
    if order and order.get("client_id"):
        client = await get_user_by_id(order["client_id"])
        if client:
            await message.bot.send_message(
                client.telegram_id,
                _t(client, f"💰 Editor proposed a different price for revisions on order #{order_id}: ${price:.2f}\n\n{payment_link}", f"💰 Монтажер запропонував іншу ціну за правки до замовлення #{order_id}: ${price:.2f}\n\n{payment_link}")
            )

    await state.clear()
    await message.answer(
        _t(user, "✅ Counter price proposed. Payment link sent to client.", "✅ Зустрічну ціну запропоновано. Посилання на оплату надіслано замовнику."),
        reply_markup=await get_menu_markup_for_user(user)
    )

@router.callback_query(F.data.startswith("revision:reject:"))
async def revision_reject(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "???????? ???? ??????????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid order id.", "Некоректний id угоди."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id or order.get("revision_status") != "requested":
        await call.answer(_t(user, "Revision request not found.", "Запит на правки не знайдено."), show_alert=True)
        return

    # Reject revision
    ok = await respond_to_revision(order_id, False)
    if not ok:
        await call.answer(_t(user, "Failed to reject revision.", "Не вдалося відхилити правки."), show_alert=True)
        return

    # Notify client
    client = await get_user_by_id(order["client_id"])
    if client:
        await call.bot.send_message(
            client.telegram_id,
            _t(client, f"❌ Editor rejected your revision request for order #{order_id}.", f"❌ Монтажер відхилив ваш запит на правки до замовлення #{order_id}.")
        )

    await call.message.edit_text(_t(user, "❌ Revision request rejected.", "❌ Запит на правки відхилено."))
    await call.answer()

@router.callback_query(F.data.startswith("order:complete:send_video:"))
async def order_complete_send_video(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "???????? ???? ??????????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid order id.", "Некоректний id угоди."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id or order.get("status") != "accepted":
        await call.answer(_t(user, "Order not found.", "Замовлення не знайдено."), show_alert=True)
        return

    # Mark final video sent
    ok = await mark_final_video_sent(order_id)
    if not ok:
        await call.answer(_t(user, "Failed to mark video as sent.", "Не вдалося позначити відео як надіслане."), show_alert=True)
        return

    # Notify client
    client = await get_user_by_id(order["client_id"])
    if client:
        await call.bot.send_message(
            client.telegram_id,
            _t(client, f"🎬 Editor has sent the final video for order #{order_id}.\n\nPlease confirm completion or request revisions.", f"🎬 Монтажер надіслав фінальне відео для замовлення #{order_id}.\n\nБудь ласка, підтвердіть завершення або запросіть правки."),
            reply_markup=kb_client_completion_menu(order_id, order.get("revision_requested", False), client.language)
        )

    await call.message.edit_text(_t(user, "✅ Final video marked as sent. Client notified.", "✅ Фінальне відео позначено як надіслане. Замовника повідомлено."))
    await call.answer()

@router.callback_query(F.data.startswith("order:complete:confirm:"))
async def order_complete_confirm(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "client":
        await call.answer(_t(user, "Clients only.", "???????? ???? ?????????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid order id.", "Некоректний id угоди."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("client_id") != user.id or order.get("status") != "accepted" or not order.get("final_video_sent"):
        await call.answer(_t(user, "Order not ready for completion.", "Замовлення не готове до завершення."), show_alert=True)
        return

    # Confirm completion
    ok = await confirm_order_completion(order_id)
    if not ok:
        await call.answer(_t(user, "Failed to confirm completion.", "Не вдалося підтвердити завершення."), show_alert=True)
        return

    # Complete order and credit editor (if no disputes)
    await complete_order_and_credit_editor(order_id)

    # Notify editor
    editor = await get_user_by_id(order["editor_id"])
    if editor:
        await call.bot.send_message(
            editor.telegram_id,
            _t(editor, f"✅ Client confirmed completion of order #{order_id}. Funds credited to your balance.", f"✅ Замовник підтвердив завершення замовлення #{order_id}. Кошти зараховані на ваш баланс.")
        )

    await call.message.edit_text(_t(user, "✅ Order completed successfully!", "✅ Замовлення успішно завершено!"))
    await call.answer()

@router.callback_query(F.data.startswith("deal:change:"))
async def deal_change_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "???????? ???? ??????????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id:
        await call.answer(_t(user, "Order not found.", "?????????? ?? ????????."), show_alert=True)
        return

    await state.clear()
    await state.set_state(DealChange.waiting_text)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(_t(user, "Describe what needs to be changed:", "??????? ?? ???????? ???????:"))

@router.message(DealChange.waiting_text)
async def deal_change_submit(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return
    if user.role != "editor":
        await state.clear()
        await message.answer(_t(user, "Editors only.", "???????? ???? ??????????."))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer(_t(user, "Describe what needs to be changed.", "??????? ?? ???????? ???????."))
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id:
        await state.clear()
        await message.answer(_t(user, "Order not found.", "?????????? ?? ????????."))
        return

    client = await get_user_by_id(int(order["client_id"]))
    if client:
        await message.bot.send_message(
            client.telegram_id,
            _t(
                    client,
                    f"Change request for order #{order_id}:\n{text}",
                    f"????? ?? ????? ?? ?????????? #{order_id}:\n{text}",
                ),
        )

    await state.clear()
    await message.answer(_t(user, "Sent to the client.", "????????? ?????????."))

@router.callback_query(F.data.startswith("order:menu:"))
async def order_menu_open(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "editor":
        await call.answer(_t(user, "Editors only.", "???????? ???? ??????????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("editor_id") != user.id:
        await call.answer(_t(user, "Order not found.", "?????????? ?? ????????."), show_alert=True)
        return

    await call.message.answer(_t(user, "Order menu:", "???? ??????????:"), reply_markup=kb_deal_menu(order_id, user.language, "editor", order.get("status"), order.get("final_video_sent", False), order.get("revision_requested", False)))
    await call.answer()

# ---------- deal chat & dispute ----------

_LINK_RE = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/|bit\.ly/|goo\.gl/|drive\.google\.com/|docs\.google\.com/|dropbox\.com/|mega\.nz/|onedrive\.live\.com/)",
    re.IGNORECASE,
)
_ALLOWED_LINK_HOSTS = {
    "drive.google.com",
    "docs.google.com",
    "dropbox.com",
    "www.dropbox.com",
    "mega.nz",
    "onedrive.live.com",
}

def _message_has_link(message: Message, text: str) -> bool:
    if message.entities:
        for ent in message.entities:
            if ent.type in ("url", "text_link"):
                return True
    return bool(_LINK_RE.search(text))

def _extract_urls(message: Message, text: str) -> list[str]:
    urls: list[str] = []
    if message.entities:
        for ent in message.entities:
            if ent.type == "text_link" and ent.url:
                urls.append(ent.url)
            elif ent.type == "url":
                urls.append(text[ent.offset : ent.offset + ent.length])
    if not urls:
        # Fallback for raw text without entities
        urls.extend(re.findall(r"(https?://\S+|www\.\S+)", text))
    return urls

def _is_allowed_link(url: str) -> bool:
    candidate = url.strip()
    if candidate.startswith("www."):
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    return host in _ALLOWED_LINK_HOSTS

def _user_label(user) -> str:
    name = user.display_name or user.username or f"id:{user.telegram_id}"
    username = f"@{user.username}" if user.username else ""
    return f"{name} {username}".strip()

async def _activate_deal_chat_for_user(
    state: FSMContext,
    bot,
    telegram_id: int,
    order_id: int,
) -> None:
    # Ensure recipient can reply without manually starting the chat
    key = StorageKey(
        bot_id=bot.id,
        chat_id=telegram_id,
        user_id=telegram_id,
    )
    ctx = FSMContext(storage=state.storage, key=key)
    await ctx.set_state(DealChat.chatting)
    await ctx.update_data(order_id=order_id)

async def _flag_and_hold_message(message: Message, order_id: int, user, text: str) -> bool:
    forbidden, word = contains_forbidden_words(text)
    if not forbidden:
        return False

    normalized = normalize_text(text)
    await create_held_message(
        deal_id=order_id,
        sender_user_id=user.id,
        original_text=text,
        normalized_text=normalized,
        flag_reason=f"forbidden_word:{word}",
    )

    moderators = await list_moderators()
    for m in moderators:
        try:
            await message.bot.send_message(
                m.telegram_id,
                _t(m, f"🔒 Message held for review in order #{order_id}.", f"🔒 Повідомлення утримано для перевірки у замовленні #{order_id}."),
            )
        except:
            pass

    await message.answer(
        _t(
            user,
            "Your message was held for moderator review because it contained forbidden content.",
            "Ваше повідомлення утримано для перевірки модератором, оскільки воно містить заборонений вміст.",
        )
    )
    return True

@router.callback_query(F.data.startswith("deal:menu:"))
async def deal_menu_open(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or (user.id not in (order.get("client_id"), order.get("editor_id")) and not is_moderator_telegram_id(call.from_user.id)):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    await call.answer()
    if is_moderator_telegram_id(call.from_user.id):
        is_dispute = order.get("status") == "dispute"
        await call.message.answer(
            _t(user, "Deal menu:", "Меню угоди:"),
            reply_markup=kb_mod_deal_menu(order_id, is_dispute, order.get("payment_status"), user.language),
        )
    else:
        user_role = "client" if order.get("client_id") == user.id else "editor"
        await call.message.answer(_t(user, "Order menu:", "???? ??????????:"), reply_markup=kb_deal_menu(order_id, user.language, user_role, order.get("status"), order.get("final_video_sent", False), order.get("revision_requested", False)))

@router.callback_query(F.data.startswith("deal:chat:exit:"))
async def deal_chat_exit(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    await state.clear()
    await call.answer()
    await call.message.answer(_t(user, "Chat closed.", "??? ???????."), reply_markup=kb_deal_chat_menu(order_id, user.language))

@router.callback_query(F.data.startswith("deal:chat:start:"))
async def deal_chat_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await call.answer(_t(user, "Deal not found.", "????? ?? ????????."), show_alert=True)
        return

    if order.get("status") == "dispute" and not is_moderator_telegram_id(call.from_user.id):
        await call.answer(_t(user, "Dispute is active. Go to the dispute.", "???? ????????. ????????? ? ????."), show_alert=True)
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")) and not is_moderator_telegram_id(call.from_user.id):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    await state.clear()
    await state.set_state(DealChat.chatting)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(_t(user, "Chat opened.", "Чат відкрито."), reply_markup=kb_deal_chat_controls(order_id, user.language))

@router.callback_query(F.data.startswith("deal:chat:link:"))
async def deal_chat_link_start(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await call.answer(_t(user, "Deal not found.", "????? ?? ????????."), show_alert=True)
        return

    if order.get("status") == "dispute" and not is_moderator_telegram_id(call.from_user.id):
        await call.answer(_t(user, "Dispute is active. Go to the dispute.", "???? ????????. ????????? ? ????."), show_alert=True)
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")) and not is_moderator_telegram_id(call.from_user.id):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    await state.clear()
    await state.set_state(DealChat.waiting_link)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(
        _t(
            user,
            f"Send a link for order #{order_id} in one message.\n"
            "Hint: you can send links only to Google Drive, Dropbox, OneDrive, Mega.",
            f"\u041d\u0430\u0434\u0456\u0441\u043b\u0456\u0442\u044c \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043f\u043e \u0437\u0430\u043c\u043e\u0432\u043b\u0435\u043d\u043d\u044e #{order_id} \u043e\u0434\u043d\u0438\u043c \u043f\u043e\u0432\u0456\u0434\u043e\u043c\u043b\u0435\u043d\u043d\u044f\u043c.\n"
            "\u041f\u0456\u0434\u043a\u0430\u0437\u043a\u0430: \u043c\u043e\u0436\u043d\u0430 \u043d\u0430\u0434\u0441\u0438\u043b\u0430\u0442\u0438 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043b\u0438\u0448\u0435 \u043d\u0430 Google Drive, Dropbox, OneDrive, Mega.",
        ),
        reply_markup=kb_deal_chat_link_controls(order_id, user.language),
    )

@router.callback_query(F.data.startswith("deal:chat:"))
async def deal_chat_menu(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 3:
        return

    try:
        order_id = int(parts[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or (user.id not in (order.get("client_id"), order.get("editor_id")) and not is_moderator_telegram_id(call.from_user.id)):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    await call.answer()
    await call.message.answer(_t(user, "Chat menu:", "???? ????:"), reply_markup=kb_deal_chat_menu(order_id, user.language))

@router.message(DealChat.waiting_link)
async def deal_chat_link_message(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    if not order_id:
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await state.clear()
        await message.answer(_t(user, "Deal not found.", "????? ?? ????????."))
        return

    if order.get("status") == "dispute" and not is_moderator_telegram_id(message.from_user.id):
        await message.answer(_t(user, "Dispute is active. Go to the dispute.", "???? ????????. ????????? ? ????."))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer(_t(user, "Send the link as a single text message.", "????????? ????????? ????? ????????? ?????????????."))
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")) and not is_moderator_telegram_id(message.from_user.id):
        await message.answer(_t(user, "No access.", "????? ???????."))
        return

    if await _flag_and_hold_message(message, order_id, user, text):
        await state.clear()
        return

    if not _message_has_link(message, text):
        await message.answer(
            _t(
                user,
                "This doesn't look like a link. Send the full link.\n"
                "Hint: you can send links only to Google Drive, Dropbox, OneDrive, Mega.",
                "\u0426\u0435 \u043d\u0435 \u0441\u0445\u043e\u0436\u0435 \u043d\u0430 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f. \u041d\u0430\u0434\u0456\u0441\u043b\u0456\u0442\u044c \u043f\u043e\u0432\u043d\u0435 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f.\n"
                "\u041f\u0456\u0434\u043a\u0430\u0437\u043a\u0430: \u043c\u043e\u0436\u043d\u0430 \u043d\u0430\u0434\u0441\u0438\u043b\u0430\u0442\u0438 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043b\u0438\u0448\u0435 \u043d\u0430 Google Drive, Dropbox, OneDrive, Mega.",
            ),
            reply_markup=kb_deal_chat_link_controls(order_id, user.language),
        )
        return

    urls = _extract_urls(message, text)
    if not urls or any(not _is_allowed_link(u) for u in urls):
        await message.answer(
            _t(
                user,
                "Link must be from an allowed service.\n"
                "Allowed: Google Drive, Dropbox, OneDrive, Mega.",
                "\u041f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043c\u0430\u0454 \u0431\u0443\u0442\u0438 \u0437 \u0434\u043e\u0437\u0432\u043e\u043b\u0435\u043d\u043e\u0433\u043e \u0441\u0435\u0440\u0432\u0456\u0441\u0443.\n"
                "\u0414\u043e\u0437\u0432\u043e\u043b\u0435\u043d\u0456: Google Drive, Dropbox, OneDrive, Mega.",
            ),
            reply_markup=kb_deal_chat_link_controls(order_id, user.language),
        )
        return

    recipient_id = order.get("editor_id") if user.id == order.get("client_id") else order.get("client_id")
    recipient = await get_user_by_id(int(recipient_id))
    if recipient:
        await create_deal_message(order_id, user.id, user.role, text)
        await message.bot.send_message(
            recipient.telegram_id,
            _t(
                recipient,
                f"Link for order #{order_id} from {_user_label(user)}\n{text}",
                f"????????? ?? ?????????? #{order_id} ??? {_user_label(user)}\n{text}",
            ),
            reply_markup=kb_deal_chat_controls(order_id, recipient.language),
        )
        await _activate_deal_chat_for_user(state, message.bot, recipient.telegram_id, order_id)

    await state.set_state(DealChat.chatting)
    await message.answer(_t(user, "Link sent.", "????????? ?????????."), reply_markup=kb_deal_chat_controls(order_id, user.language))

@router.message(DealChat.chatting)
async def deal_chat_message(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    if not order_id:
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await state.clear()
        await message.answer(_t(user, "Deal not found.", "????? ?? ????????."))
        return

    if order.get("status") == "dispute" and not is_moderator_telegram_id(message.from_user.id):
        await message.answer(_t(user, "Dispute is active. Go to the dispute.", "???? ????????. ????????? ? ????."))
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")) and not is_moderator_telegram_id(message.from_user.id):
        await message.answer(_t(user, "No access.", "????? ???????."))
        return

    text = (message.text or "").strip()
    if not text:
        return

    if await _flag_and_hold_message(message, order_id, user, text):
        await state.clear()
        return

    if _message_has_link(message, text):
        await message.answer(
            _t(
                user,
                "Links are not allowed in chat. Use the Send link menu.\n"
                "Hint: you can send links only to Google Drive, Dropbox, OneDrive, Mega.",
                "\u041f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u0432 \u0447\u0430\u0442\u0456 \u0437\u0430\u0431\u0440\u043e\u043d\u0435\u043d\u0456. \u0412\u0438\u043a\u043e\u0440\u0438\u0441\u0442\u043e\u0432\u0443\u0439\u0442\u0435 \u043c\u0435\u043d\u044e \u041d\u0430\u0434\u0456\u0441\u043b\u0430\u0442\u0438 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f.\n"
                "\u041f\u0456\u0434\u043a\u0430\u0437\u043a\u0430: \u043c\u043e\u0436\u043d\u0430 \u043d\u0430\u0434\u0441\u0438\u043b\u0430\u0442\u0438 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043b\u0438\u0448\u0435 \u043d\u0430 Google Drive, Dropbox, OneDrive, Mega.",
            ),
            reply_markup=kb_deal_chat_controls(order_id, user.language),
        )
        return

    recipient_ids = []
    if is_moderator_telegram_id(message.from_user.id):
        if order.get("client_id"):
            recipient_ids.append(int(order["client_id"]))
        if order.get("editor_id"):
            recipient_ids.append(int(order["editor_id"]))
    else:
        recipient_ids.append(int(order.get("editor_id") if user.id == order.get("client_id") else order.get("client_id")))

    await create_deal_message(order_id, user.id, user.role, text)
    for rid in recipient_ids:
        recipient = await get_user_by_id(rid)
        if not recipient or recipient.id == user.id:
            continue
        await message.bot.send_message(
            recipient.telegram_id,
            _t(
                recipient,
                f"Chat for order #{order_id} from {_user_label(user)}\n{text}",
                f"??? ?? ?????????? #{order_id} ??? {_user_label(user)}\n{text}",
            ),
            reply_markup=kb_deal_chat_controls(order_id, recipient.language),
        )
        await _activate_deal_chat_for_user(state, message.bot, recipient.telegram_id, order_id)

    await message.answer(_t(user, "Message sent.", "Повідомлення надіслано."), reply_markup=kb_deal_chat_controls(order_id, user.language))

@router.callback_query(F.data.startswith("deal:dispute:exit:"))
async def dispute_exit(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    user_role = "client" if order and order.get("client_id") == user.id else "editor"

    await state.clear()
    await call.answer()
    await call.message.answer(_t(user, "You left the dispute.", "?? ?????? ?? ?????."), reply_markup=kb_deal_menu(order_id, user.language, user_role, order.get("status") if order else None, order.get("final_video_sent", False) if order else False, order.get("revision_requested", False) if order else False))

@router.callback_query(F.data.startswith("deal:dispute:join:"))
async def dispute_join(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("status") != "dispute":
        await call.answer(_t(user, "Dispute is not active.", "???? ?? ????????."), show_alert=True)
        return

    if user.role != "moderator" and user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    await state.clear()
    await state.set_state(DisputeChat.chatting)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(
        _t(
            user,
            "Dispute opened. Final decision is made by a moderator.\n"
            "The dispute can be closed by a moderator or if both parties agree.",
            "\u0421\u043f\u0456\u0440 \u0432\u0456\u0434\u043a\u0440\u0438\u0442\u043e. \u041e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u0435 \u0440\u0456\u0448\u0435\u043d\u043d\u044f \u043f\u0440\u0438\u0439\u043c\u0430\u0454 \u043c\u043e\u0434\u0435\u0440\u0430\u0442\u043e\u0440.\n"
            "\u0421\u043f\u0456\u0440 \u043c\u043e\u0436\u0435 \u0437\u0430\u043a\u0440\u0438\u0442\u0438 \u043c\u043e\u0434\u0435\u0440\u0430\u0442\u043e\u0440 \u0430\u0431\u043e \u044f\u043a\u0449\u043e \u043e\u0431\u0438\u0434\u0432\u0456 \u0441\u0442\u043e\u0440\u043e\u043d\u0438 \u043f\u043e\u0433\u043e\u0434\u044f\u0442\u044c\u0441\u044f.",
        ),
        reply_markup=kb_dispute_controls(order_id, is_moderator=(user.role == "moderator"), lang=user.language),
    )

@router.callback_query(F.data.startswith("deal:dispute:agree:"))
async def dispute_agree(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role not in ("client", "editor"):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("status") != "dispute":
        await call.answer(_t(user, "Dispute is not active.", "???? ?? ????????."), show_alert=True)
        return

    client_agree, editor_agree = await set_dispute_agree(order_id, user.role)
    await call.answer(_t(user, "Marked.", "?????????."), show_alert=True)

    if client_agree and editor_agree:
        await close_dispute(order_id)
        client = await get_user_by_id(int(order["client_id"]))
        editor = await get_user_by_id(int(order["editor_id"]))
        moderators = await list_moderators()
        if client:
            await call.bot.send_message(
                client.telegram_id,
                _t(client, f"Dispute for order #{order_id} closed by agreement.", f"???? ?? ?????????? #{order_id} ??????? ?? ?????? ??????."),
            )
        if editor:
            await call.bot.send_message(
                editor.telegram_id,
                _t(editor, f"Dispute for order #{order_id} closed by agreement.", f"???? ?? ?????????? #{order_id} ??????? ?? ?????? ??????."),
            )
        for m in moderators:
            await call.bot.send_message(
                m.telegram_id,
                _t(m, f"Dispute for order #{order_id} closed by agreement.", f"???? ?? ?????????? #{order_id} ??????? ?? ?????? ??????."),
            )

@router.callback_query(F.data.startswith("deal:dispute:close:"))
async def dispute_close(call: CallbackQuery):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return
    if user.role != "moderator":
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    try:
        order_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    ok = await close_dispute(order_id)
    if not ok:
        await call.answer(_t(user, "Dispute is not active.", "???? ?? ????????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    client = await get_user_by_id(int(order["client_id"])) if order else None
    editor = await get_user_by_id(int(order["editor_id"])) if order else None
    moderators = await list_moderators()
    if client:
        await call.bot.send_message(
            client.telegram_id,
            _t(client, f"Dispute for order #{order_id} closed by moderator.", f"???? ?? ?????????? #{order_id} ??????? ???????????."),
        )
    if editor:
        await call.bot.send_message(
            editor.telegram_id,
            _t(editor, f"Dispute for order #{order_id} closed by moderator.", f"???? ?? ?????????? #{order_id} ??????? ???????????."),
        )
    for m in moderators:
        await call.bot.send_message(
            m.telegram_id,
            _t(m, f"Dispute for order #{order_id} closed by moderator.", f"???? ?? ?????????? #{order_id} ??????? ???????????."),
        )

@router.callback_query(F.data.startswith("deal:dispute:"))
async def dispute_open(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer(_tl(None, "Type /start", "????????? /start"), show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) != 3:
        return

    try:
        order_id = int(parts[-1])
    except ValueError:
        await call.answer(_t(user, "Invalid number.", "??????????? ?????."), show_alert=True)
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await call.answer(_t(user, "Deal not found.", "????? ?? ????????."), show_alert=True)
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")):
        await call.answer(_t(user, "No access.", "????? ???????."), show_alert=True)
        return

    if order.get("status") == "dispute":
        await call.answer(_t(user, "Dispute is already active.", "???? ??? ????????."), show_alert=True)
        return

    await state.clear()
    await state.set_state(DisputeOpenReason.waiting_text)
    await state.update_data(order_id=order_id)
    await call.answer()
    await call.message.answer(_t(user, "Describe the dispute reason in one message.", "??????? ??????? ????? ????? ?????????????."))

@router.message(DisputeOpenReason.waiting_text)
async def dispute_open_reason(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    if not order_id:
        await state.clear()
        return

    reason = (message.text or "").strip()
    if not reason:
        await message.answer(_t(user, "Reason cannot be empty.", "??????? ?? ??????? ???? ?????????."))
        return

    order = await get_order_by_id(order_id)
    if not order or not order.get("editor_id"):
        await state.clear()
        await message.answer(_t(user, "Deal not found.", "????? ?? ????????."))
        return

    if user.id not in (order.get("client_id"), order.get("editor_id")):
        await state.clear()
        await message.answer(_t(user, "No access.", "????? ???????."))
        return

    ok = await open_dispute(order_id, user.id)
    if not ok:
        await state.clear()
        await message.answer(_t(user, "Failed to open dispute.", "?? ??????? ???????? ????."))
        return

    await state.clear()
    await state.set_state(DisputeChat.chatting)
    await state.update_data(order_id=order_id)

    warning_en = (
        "Attention! The deal is frozen until the dispute is resolved.\n"
        "Final decision is made by a moderator.\n"
        "The dispute can be closed by a moderator or if both parties agree."
    )
    warning_ua = (
        "\u0423\u0432\u0430\u0433\u0430! \u0423\u0433\u043e\u0434\u0443 \u0437\u0430\u043c\u043e\u0440\u043e\u0436\u0435\u043d\u043e \u0434\u043e \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043d\u044f \u0441\u043f\u043e\u0440\u0443.\n"
        "\u041e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u0435 \u0440\u0456\u0448\u0435\u043d\u043d\u044f \u043f\u0440\u0438\u0439\u043c\u0430\u0454 \u043c\u043e\u0434\u0435\u0440\u0430\u0442\u043e\u0440.\n"
        "\u0421\u043f\u0456\u0440 \u043c\u043e\u0436\u0435 \u0437\u0430\u043a\u0440\u0438\u0442\u0438 \u043c\u043e\u0434\u0435\u0440\u0430\u0442\u043e\u0440 \u0430\u0431\u043e \u044f\u043a\u0449\u043e \u043e\u0431\u0438\u0434\u0432\u0456 \u0441\u0442\u043e\u0440\u043e\u043d\u0438 \u043f\u043e\u0433\u043e\u0434\u044f\u0442\u044c\u0441\u044f."
    )
    warning = _t(user, warning_en, warning_ua)

    client = await get_user_by_id(int(order["client_id"]))
    editor = await get_user_by_id(int(order["editor_id"]))
    moderators = await list_moderators()

    if client and client.telegram_id != message.from_user.id:
        await message.bot.send_message(
            client.telegram_id,
            _t(client, warning_en, warning_ua),
            reply_markup=kb_dispute_join(order_id, lang=client.language),
        )
    if editor and editor.telegram_id != message.from_user.id:
        await message.bot.send_message(
            editor.telegram_id,
            _t(editor, warning_en, warning_ua),
            reply_markup=kb_dispute_join(order_id, lang=editor.language),
        )
    for m in moderators:
        await message.bot.send_message(
            m.telegram_id,
            _t(m, f"Dispute for order #{order_id} opened. Reason: {reason}", f"???? ?? ?????????? #{order_id} ????????. ???????: {reason}"),
            reply_markup=kb_dispute_join(order_id, lang=m.language),
        )

    await message.answer(warning, reply_markup=kb_dispute_controls(order_id, is_moderator=False, lang=user.language))

@router.message(DisputeChat.chatting)
async def dispute_chat_message(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        return

    data = await state.get_data()
    order_id = int(data.get("order_id") or 0)
    if not order_id:
        return

    order = await get_order_by_id(order_id)
    if not order or order.get("status") != "dispute":
        await state.clear()
        await message.answer(_t(user, "Dispute is not active.", "???? ?? ????????."))
        return

    if user.role != "moderator" and user.id not in (order.get("client_id"), order.get("editor_id")):
        await message.answer(_t(user, "No access.", "????? ???????."))
        return

    text = (message.text or "").strip()
    if not text:
        return

    moderators = await list_moderators()
    recipients = []
    if order.get("client_id"):
        recipients.append(int(order.get("client_id")))
    if order.get("editor_id"):
        recipients.append(int(order.get("editor_id")))

    for uid in recipients:
        if uid == user.id:
            continue
        u = await get_user_by_id(uid)
        if u:
            prefix = _t(u, f"DISPUTE #{order_id} from {_user_label(user)}\n", f"???? #{order_id} ??? {_user_label(user)}\n")
            await message.bot.send_message(
                u.telegram_id,
                prefix + text,
                reply_markup=kb_dispute_controls(order_id, is_moderator=False, lang=u.language),
            )

    for m in moderators:
        if m.id == user.id:
            continue
        prefix = _t(m, f"DISPUTE #{order_id} from {_user_label(user)}\n", f"???? #{order_id} ??? {_user_label(user)}\n")
        await message.bot.send_message(
            m.telegram_id,
            prefix + text,
            reply_markup=kb_dispute_controls(order_id, is_moderator=True, lang=m.language),
        )
