from typing import Optional

from app.db import pool


async def create_or_update_review(
    order_id: int,
    reviewer_user_id: int,
    reviewee_user_id: int,
    rating: int,
    comment: str = "",
) -> int:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO order_reviews (
                order_id,
                reviewer_user_id,
                reviewee_user_id,
                rating,
                comment
            )
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (order_id, reviewer_user_id, reviewee_user_id)
            DO UPDATE SET
                rating = EXCLUDED.rating,
                comment = EXCLUDED.comment,
                updated_at = NOW()
            RETURNING id
            """,
            order_id,
            reviewer_user_id,
            reviewee_user_id,
            rating,
            comment.strip(),
        )
    return int(row["id"])


async def get_review(
    order_id: int,
    reviewer_user_id: int,
    reviewee_user_id: int,
) -> Optional[dict]:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, order_id, reviewer_user_id, reviewee_user_id, rating, comment, created_at, updated_at
            FROM order_reviews
            WHERE order_id = $1
              AND reviewer_user_id = $2
              AND reviewee_user_id = $3
            """,
            order_id,
            reviewer_user_id,
            reviewee_user_id,
        )
    return dict(row) if row else None


async def list_received_reviews(user_id: int, limit: int = 10) -> list[dict]:
    p = pool()
    async with p.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                r.order_id,
                r.rating,
                r.comment,
                r.created_at,
                o.title AS order_title,
                reviewer.display_name AS reviewer_display_name,
                reviewer.username AS reviewer_username,
                reviewer.role AS reviewer_role
            FROM order_reviews r
            JOIN orders o ON o.id = r.order_id
            JOIN users reviewer ON reviewer.id = r.reviewer_user_id
            WHERE r.reviewee_user_id = $1
            ORDER BY r.created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
    return [dict(row) for row in rows]
