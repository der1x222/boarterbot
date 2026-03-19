import os

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
