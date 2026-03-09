from app.db import pool

ACTIVE_DEAL_STATUSES = (
    "created",
    "funding",
    "funded",
    "working",
    "submitted",
    "revision_requested",
    "dispute",
)

async def count_active_deals_for_user(user_id: int) -> int:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM deals
            WHERE status = ANY($1::text[])
              AND (client_id = $2 OR editor_id = $2)
            """,
            list(ACTIVE_DEAL_STATUSES),
            user_id
        )
    return int(row["cnt"])

async def list_active_deals_for_user(user_id: int, limit: int = 5) -> list[dict]:
    p = pool()
    async with p.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, status, created_at
            FROM deals
            WHERE status = ANY($1::text[])
              AND (client_id = $2 OR editor_id = $2)
            ORDER BY created_at DESC
            LIMIT $3
            """,
            list(ACTIVE_DEAL_STATUSES),
            user_id,
            limit
        )
    return [dict(r) for r in rows]