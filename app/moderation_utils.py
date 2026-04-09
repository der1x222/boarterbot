import os
import re

DEFAULT_FORBIDDEN_WORDS = [
    "badword",
    "spam",
    "scam",
]

def get_moderator_ids() -> set[int]:
    raw = os.getenv("MODERATOR_IDS", "").strip()
    if not raw:
        return set()
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids

def is_moderator_telegram_id(telegram_id: int) -> bool:
    return telegram_id in get_moderator_ids()

def get_forbidden_words() -> list[str]:
    raw = os.getenv("FORBIDDEN_WORDS", ",".join(DEFAULT_FORBIDDEN_WORDS)).strip()
    if not raw:
        return DEFAULT_FORBIDDEN_WORDS
    return [w.strip().lower() for w in raw.split(",") if w.strip()]

def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

def contains_forbidden_words(text: str) -> tuple[bool, str | None]:
    normalized = normalize_text(text)
    words = set(normalized.split())
    forbidden = get_forbidden_words()
    for word in forbidden:
        if word and word in words:
            return True, word
    return False, None
