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
