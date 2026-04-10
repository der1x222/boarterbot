from typing import Any, Optional
from app.db import pool

async def list_pending_verifications(offset: int = 0, limit: int = 1) -> list[dict]:
    p = pool()
    async with p.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, name, skills, price_from_minor, portfolio_url, test_submission, verification_status
            FROM editor_profiles
            WHERE verification_status = 'pending'
            ORDER BY updated_at ASC
            OFFSET $1
            LIMIT $2
            """,
            offset,
            limit,
        )
    return [dict(r) for r in rows]

async def list_verified_editors(offset: int = 0, limit: int = 10) -> list[dict]:
    p = pool()
    async with p.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, name, skills, price_from_minor, portfolio_url, verification_status
            FROM editor_profiles
            WHERE verification_status = 'verified'
            ORDER BY updated_at DESC
            OFFSET $1
            LIMIT $2
            """,
            offset,
            limit,
        )
    return [dict(r) for r in rows]

async def list_held_messages(offset: int = 0, limit: int = 1) -> list[dict]:
    p = pool()
    async with p.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, deal_id, sender_user_id, original_text, normalized_text, flag_reason, status, created_at
            FROM held_messages
            WHERE status = 'held'
            ORDER BY created_at ASC
            OFFSET $1
            LIMIT $2
            """,
            offset,
            limit,
        )
    return [dict(r) for r in rows]

async def get_held_message_by_id(message_id: int) -> Optional[dict]:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, deal_id, sender_user_id, original_text, normalized_text, flag_reason, status, created_at
            FROM held_messages
            WHERE id = $1
            """,
            message_id,
        )
    return dict(row) if row else None

async def update_held_message_status(message_id: int, status: str) -> bool:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE held_messages
            SET status = $2
            WHERE id = $1
            RETURNING id
            """,
            message_id,
            status,
        )
    return bool(row)

async def create_held_message(
    deal_id: int,
    sender_user_id: int,
    original_text: str,
    normalized_text: str,
    flag_reason: str,
) -> int:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO held_messages (deal_id, sender_user_id, original_text, normalized_text, flag_reason)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            deal_id,
            sender_user_id,
            original_text,
            normalized_text,
            flag_reason,
        )
    return int(row["id"])

async def list_dispute_deals(offset: int = 0, limit: int = 1) -> list[dict]:
    p = pool()
    async with p.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, client_id, editor_id, status, price_minor
            FROM deals
            WHERE status = 'dispute'
            ORDER BY updated_at ASC
            OFFSET $1
            LIMIT $2
            """,
            offset,
            limit,
        )
    return [dict(r) for r in rows]

async def get_deal_by_id(deal_id: int) -> Optional[dict]:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, client_id, editor_id, status, price_minor, currency
            FROM deals
            WHERE id = $1
            """,
            deal_id,
        )
    return dict(row) if row else None

async def count_stats() -> dict:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM editor_profiles WHERE verification_status = 'pending') AS pending_verifications,
                (SELECT COUNT(*) FROM held_messages WHERE status = 'held') AS held_messages,
                (SELECT COUNT(*) FROM deals WHERE status = 'dispute') AS disputes,
                (SELECT COUNT(*) FROM users) AS users,
                (SELECT COUNT(*) FROM editor_profiles) AS editor_profiles,
                (SELECT COUNT(*) FROM client_profiles) AS client_profiles
            """
        )
    return dict(row) if row else {}

async def create_user_sanction(
    target_user_id: int,
    moderator_user_id: int,
    sanction_type: str,
    reason: str | None = None,
) -> int:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO user_sanctions (target_user_id, moderator_user_id, type, reason)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            target_user_id,
            moderator_user_id,
            sanction_type,
            reason,
        )
    return int(row["id"])

async def log_moderation_action(
    moderator_user_id: int,
    action_type: str,
    target_user_id: int | None,
    object_type: str,
    object_id: int | None,
    payload: dict[str, Any] | None = None,
) -> None:
    p = pool()
    async with p.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO moderation_actions (moderator_user_id, action_type, target_user_id, object_type, object_id, payload)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            moderator_user_id,
            action_type,
            target_user_id,
            object_type,
            object_id,
            payload or {},
        )
