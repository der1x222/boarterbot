import asyncio
import json
import base64
import hashlib
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from app.config import load_config
from app.db import init_db, run_migration_file
from app.handlers.start import router as start_router
from app.handlers.menus import router as menus_router
from app.handlers.registration import router as reg_router
from app.handlers.profile import router as profile_router
from app.handlers.orders import router as orders_router
from app.handlers.verify import router as verify_router
from app.handlers.moderation import router as moderation_router
from app.handlers.settings import router as settings_router
from app.order_repo import set_payment_status, set_reserved_amount, set_reserved_revision_amount, get_order_by_id, mark_revision_paid, get_pending_payments, update_payment_status_if_needed, cancel_order_if_payment_failed
from app.payment_api import PaymentAPI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

cfg = None  # Global config
bot = None  # Global bot instance

async def notify_payment_success(order_id: int, is_revision: bool = False):
    """Notify users about successful payment"""
    try:
        order = await get_order_by_id(order_id)
        if not order:
            return

        client_id = order['client_id']
        editor_id = order.get('editor_id')

        # Get user telegram IDs
        from app.models import get_user_by_id
        client = await get_user_by_id(client_id)
        editor = await get_user_by_id(editor_id) if editor_id else None

        message = f"✅ Payment successful for order #{order_id}"
        if is_revision:
            message += " (revision)"

        if client and client.get('telegram_id'):
            try:
                await bot.send_message(client['telegram_id'], message)
            except Exception as e:
                logger.error(f"Failed to notify client {client_id}: {e}")

        if editor and editor.get('telegram_id'):
            try:
                await bot.send_message(editor['telegram_id'], message)
            except Exception as e:
                logger.error(f"Failed to notify editor {editor_id}: {e}")

    except Exception as e:
        logger.error(f"Error notifying payment success for order {order_id}: {e}")

async def notify_payment_failure(order_id: int, is_revision: bool = False):
    """Notify users about failed payment"""
    try:
        order = await get_order_by_id(order_id)
        if not order:
            return

        client_id = order['client_id']

        from app.models import get_user_by_id
        client = await get_user_by_id(client_id)

        message = f"❌ Payment failed for order #{order_id}"
        if is_revision:
            message += " (revision)"
        message += ". The order has been cancelled. Please try again."

        if client and client.get('telegram_id'):
            try:
                await bot.send_message(client['telegram_id'], message)
            except Exception as e:
                logger.error(f"Failed to notify client {client_id}: {e}")

    except Exception as e:
        logger.error(f"Error notifying payment failure for order {order_id}: {e}")

async def verify_pending_payments():
    """Periodically verify pending payments with LiqPay"""
    payment_api = PaymentAPI()
    while True:
        try:
            pending_orders = await get_pending_payments()
            logger.info(f"Checking {len(pending_orders)} pending payments")

            for order in pending_orders:
                order_id = order['id']
                payment_session_id = order['stripe_session_id']  # Actually LiqPay order_id

                # Check if it's revision payment
                is_revision = order.get('revision_status') == 'payment_pending'

                # Verify payment status
                if await payment_api.verify_payment(payment_session_id):
                    # Payment successful
                    if is_revision:
                        await mark_revision_paid(order_id)
                        revision_price = (await get_order_by_id(order_id)).get('revision_price_minor', 0)
                        if revision_price > 0:
                            await set_reserved_revision_amount(order_id, revision_price)
                        logger.info(f"Verified revision payment for order {order_id}")
                        # Notify users
                        await notify_payment_success(order_id, is_revision=True)
                    else:
                        await update_payment_status_if_needed(order_id, 'paid')
                        agreed_price = (await get_order_by_id(order_id)).get('agreed_price_minor', 0)
                        if agreed_price > 0:
                            await set_reserved_amount(order_id, agreed_price)
                        logger.info(f"Verified main payment for order {order_id}")
                        # Notify users
                        await notify_payment_success(order_id, is_revision=False)
                else:
                    # Check if payment failed or expired
                    details = await payment_api.get_payment_details(payment_session_id)
                    if details:
                        status = details.get('status', '').lower()
                        if status in ('failure', 'error', 'reversed'):
                            # Payment failed
                            await cancel_order_if_payment_failed(order_id, is_revision)
                            logger.warning(f"Payment failed for order {order_id}, status={status}")
                            # Notify users
                            await notify_payment_failure(order_id, is_revision)
                        elif status in ('pending', 'wait_accept'):
                            # Still pending, continue checking
                            pass
                        else:
                            logger.info(f"Payment status for order {order_id}: {status}")
                    else:
                        logger.warning(f"Could not get payment details for order {order_id}")

            await asyncio.sleep(300)  # Check every 5 minutes

        except Exception as e:
            logger.error(f"Error in payment verification task: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute on error

def verify_liqpay_signature(data: str, signature: str, private_key: str) -> bool:
    """Verify LiqPay webhook signature"""
    payload = private_key + data + private_key
    expected_signature = base64.b64encode(hashlib.sha1(payload.encode("utf-8")).digest()).decode("utf-8")
    return expected_signature == signature

async def handle_payment_webhook(request):
    """Handle LiqPay payment webhook"""
    global cfg
    try:
        data = await request.post()
        liqpay_data = data.get('data')
        liqpay_signature = data.get('signature')

        if not liqpay_data or not liqpay_signature:
            logger.warning("Webhook: Missing data or signature")
            return web.Response(status=400, text="Missing data or signature")

        if not verify_liqpay_signature(liqpay_data, liqpay_signature, cfg.liqpay_private_key):
            logger.warning("Webhook: Invalid signature")
            return web.Response(status=403, text="Invalid signature")

        # Decode payment data
        payment_info = json.loads(base64.b64decode(liqpay_data).decode("utf-8"))
        status = payment_info.get('status', '').lower()
        order_id_str = payment_info.get('order_id', '')
        amount = payment_info.get('amount', 0)

        logger.info(f"Webhook received: order_id={order_id_str}, status={status}, amount={amount}")

        if status not in ('success', 'sandbox'):
            logger.info(f"Webhook: Payment not successful for order {order_id_str}, status={status}")
            return web.Response(status=200, text="Payment not successful")

        # Determine if it's revision payment or main payment
        is_revision = order_id_str.startswith('revision_')
        if is_revision:
            actual_order_id = int(order_id_str.split('_', 1)[1])
        else:
            actual_order_id = int(order_id_str)

        order = await get_order_by_id(actual_order_id)
        if not order:
            logger.error(f"Webhook: Order {actual_order_id} not found")
            return web.Response(status=400, text="Order not found")

        if is_revision:
            # Handle revision payment
            if order.get('revision_status') != 'payment_pending':
                logger.warning(f"Webhook: Revision not pending payment for order {actual_order_id}")
                return web.Response(status=200, text="Revision not pending payment")

            ok = await mark_revision_paid(actual_order_id)
            if not ok:
                logger.error(f"Webhook: Failed to mark revision paid for order {actual_order_id}")
                return web.Response(status=500, text="Failed to mark revision paid")

            # Reserve revision amount
            revision_price = order.get('revision_price_minor', 0)
            if revision_price > 0:
                await set_reserved_revision_amount(actual_order_id, revision_price)
                logger.info(f"Webhook: Reserved revision amount {revision_price} for order {actual_order_id}")
        else:
            # Handle main payment
            if order.get('payment_status') == 'paid':
                logger.info(f"Webhook: Order {actual_order_id} already paid")
                return web.Response(status=200, text="Already paid")

            ok = await set_payment_status(actual_order_id, 'paid')
            if not ok:
                logger.error(f"Webhook: Failed to update payment status for order {actual_order_id}")
                return web.Response(status=500, text="Failed to update payment status")

            # Reserve main amount
            agreed_price = order.get('agreed_price_minor', 0)
            if agreed_price > 0:
                await set_reserved_amount(actual_order_id, agreed_price)
                logger.info(f"Webhook: Reserved amount {agreed_price} for order {actual_order_id}")

        logger.info(f"Webhook: Successfully processed payment for order {actual_order_id}, is_revision={is_revision}")
        return web.Response(status=200, text="OK")

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500, text="Internal error")

async def main():
    global cfg
    cfg = load_config()

    await init_db(cfg.db_dsn)
    await run_migration_file("migrations/001_init.sql")
    await run_migration_file("migrations/002_profiles.sql")
    await run_migration_file("migrations/003_verification.sql")
    await run_migration_file("migrations/004_orders.sql")
    await run_migration_file("migrations/005_orders_editor.sql")
    await run_migration_file("migrations/006_orders_deadline.sql")
    await run_migration_file("migrations/007_orders_revision_price.sql")
    await run_migration_file("migrations/008_orders_dispute.sql")
    await run_migration_file("migrations/009_moderation.sql")
    await run_migration_file("migrations/010_payment.sql")
    await run_migration_file("migrations/011_editor_profile_extended.sql")
    await run_migration_file("migrations/012_orders_agreed_price.sql")
    await run_migration_file("migrations/013_deal_messages.sql")
    await run_migration_file("migrations/014_balance_and_revisions.sql")
    await run_migration_file("migrations/015_reviews_and_profile_stats.sql")

    global bot
    bot = Bot(token=cfg.bot_token, parse_mode=ParseMode.HTML)
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher()
    dp.include_router(reg_router)
    dp.include_router(profile_router)
    dp.include_router(orders_router)
    dp.include_router(verify_router)
    dp.include_router(moderation_router)
    dp.include_router(settings_router)
    dp.include_router(menus_router)

    # Setup aiohttp app for webhooks
    app = web.Application()
    app.router.add_post('/webhook/payment', handle_payment_webhook)

    # Start payment verification task
    asyncio.create_task(verify_pending_payments())

    # Run both polling and web server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)  # Adjust port as needed
    await site.start()

    print("Webhook server started on port 8080")
    print("Starting bot polling...")

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
