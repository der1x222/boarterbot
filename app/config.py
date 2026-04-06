from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    db_dsn: str
    redis_dsn: str
    moderator_ids: set[int]
    default_language: str

def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is missing")

    db_dsn = os.getenv("DB_DSN", "").strip()
    redis_dsn = os.getenv("REDIS_DSN", "").strip()
    default_language = os.getenv("DEFAULT_LANGUAGE", "en").strip()

    raw_mods = os.getenv("MODERATOR_IDS", "").strip()
    moderator_ids: set[int] = set()
    if raw_mods:
        for x in raw_mods.split(","):
            x = x.strip()
            if x.isdigit():
                moderator_ids.add(int(x))

    return Config(
        bot_token=token,
        db_dsn=db_dsn,
        redis_dsn=redis_dsn,
        moderator_ids=moderator_ids,
        default_language=default_language,
    )
