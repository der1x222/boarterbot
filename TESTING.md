# Payment System Testing Guide

## Sandbox Configuration
The system is configured for LiqPay sandbox testing with the following credentials:
- **Public Key**: sandbox_i72374573737
- **Private Key**: sandbox_20VMmJ4yqulwirDjGqOXa7ECHZlVivI0CaLFI2M3
- **Sandbox Mode**: Enabled (LIQPAY_SANDBOX=1)

## LiqPay Sandbox Test Cards

### Successful Payment
- **Card**: 4111111111111111
- **Month**: 12
- **Year**: 25
- **CVV**: 000
- **Result**: Payment will succeed

### Failed Payment
- **Card**: 4222222222222222
- **Month**: 12
- **Year**: 25
- **CVV**: 000
- **Result**: Payment will fail

### Reversal Test
- **Card**: 5555555555554444
- **Month**: 12
- **Year**: 25
- **CVV**: 000
- **Result**: Payment will be reversed

## Testing Workflow

### 1. Start the Bot
```bash
python app/main.py
```
This will:
- Start the Telegram bot with polling
- Start the webhook server on port 8080
- Start the payment verification task (runs every 5 minutes)

### 2. Test Main Order Payment
1. Start a chat with the bot: `/start`
2. Register as **Client**
3. Create an order with budget (e.g., 100 USD)
4. Once order is accepted by editor, proceed to payment
5. Click payment link
6. Use test card: **4111111111111111**
7. Payment should succeed immediately
8. Check logs for webhook confirmation

### 3. Test Failed Payment
1. Start new order
2. In payment, use failed card: **4222222222222222**
3. Payment should fail
4. Check that order is automatically cancelled
5. Verify you receive cancellation notification

### 4. Test Revision Payment
1. After successful main order payment
2. Request revision with price (e.g., 50 USD)
3. Editor accepts revision
4. Proceed to revision payment using test card
5. Payment should succeed
6. Check reserved revision amount in logs

### 5. Test Withdrawal System
1. Login as **Editor**
2. Complete orders and earn virtual balance (simulated by admin)
3. Go to Profile → Balance → "Withdraw funds"
4. Send: `withdraw 50 PayPal email@example.com`
5. System will:
   - Calculate 10% fee (5 USD)
   - Deduct total from balance (55 USD)
   - Create withdrawal request with status "pending"

### 6. Monitor Payment Status

#### Via Logs
```bash
# Watch logs for payment events
tail -f logs/payment.log
```

Key log messages:
- `Webhook received: order_id=X, status=Y, amount=Z` - Webhook received
- `Verified main payment for order X` - Payment confirmed via periodic check
- `Payment failed for order X` - Payment failed
- `Reserved amount X for order Y` - Funds reserved in escrow

#### Via Database
```sql
SELECT id, payment_status, revision_status, paid_at 
FROM orders 
ORDER BY created_at DESC 
LIMIT 5;

SELECT * FROM withdrawal_requests 
ORDER BY created_at DESC;
```

## Automated Verification

### Webhook Handler
- Receives real-time payment notifications from LiqPay
- Validates signature for security
- Updates order status immediately
- Reserves funds in escrow

### Periodic Verification (Every 5 minutes)
- Checks all pending payments against LiqPay API
- Confirms successful payments
- Cancels failed payments
- Sends user notifications

## Expected Behavior

### Successful Payment Flow
1. **Webhook** → Status updated to "paid"
2. **Escrow** → Funds reserved from client's account
3. **Notification** → Both parties notified
4. **Periodic Check** → Confirms payment status

### Failed Payment Flow
1. **Webhook/Periodic Check** → Detects failure
2. **Cancellation** → Order status set to "cancelled"
3. **Notification** → Client notified
4. **No Escrow** → Funds not charged

### Withdrawal Flow
1. **Request** → Funds deducted from balance immediately
2. **Fee Calculation** → 10% commission calculated
3. **Status** → Request marked as "pending"
4. **Admin Review** → Admin can approve/reject
5. **Completion** → Funds transferred to external account

## Troubleshooting

### Payment not confirming
1. Check logs for webhook errors
2. Verify signature validation passed
3. Check database `stripe_session_id` matches order_id
4. Wait for periodic verification (max 5 minutes)

### Withdrawal not working
1. Verify user is verified editor
2. Check balance >= 10 USD minimum
3. Verify message format: `withdraw <amount> <details>`
4. Check withdrawal_requests table for pending requests

### Webhook not receiving
1. Verify APP_URL is correct and accessible
2. Check firewall/NAT allows port 8080
3. Verify LiqPay webhook configuration includes correct URL
4. Check webhook server logs

## Testing Notes
- All test payments use real LiqPay sandbox infrastructure
- Sandbox transactions do not charge real cards
- Balances are simulated (can be manually inserted via SQL)
- Data persists in PostgreSQL for debugging
