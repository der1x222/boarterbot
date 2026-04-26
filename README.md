# marketbot (MVP)

## Run locally
1) Create a bot via BotFather and copy token
2) Copy `.env.example` -> `.env` and set BOT_TOKEN
3) Start Postgres + Redis:
```bash
docker compose up -d
```
4) Install deps and run:
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

The application will start both the Telegram bot (polling) and a web server for payment webhooks on port 8080. Ensure the APP_URL in .env points to your server's URL for webhook callbacks.

## Withdrawal System
Editors can withdraw funds from their virtual balance.
- Minimum withdrawal: 10 USD
- Fee: 10% of withdrawal amount
- To withdraw: Go to profile -> "Withdraw funds" -> Send message "withdraw <amount> <payment details>"
- Example: withdraw 50 PayPal email@example.com
- Funds are deducted immediately, request goes to pending status.
- Admins can process withdrawals manually.
