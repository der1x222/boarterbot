from typing import Optional
from app.db import pool

async def upsert_editor_profile(
    user_id: int, 
    name: str, 
    skills: str, 
    price_from_minor: int, 
    portfolio_url: str,
    skill_level: str | None = None,
    experience_description: str | None = None,
    avg_price_minor: int | None = None,
) -> None:
    p = pool()
    async with p.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO editor_profiles (
                user_id,
                name,
                skills,
                price_from_minor,
                portfolio_url,
                skill_level,
                experience_description,
                avg_price_minor
            )
            VALUES ($1, $2, $3, $4, $5, COALESCE($6, ''), COALESCE($7, ''), $8)
            ON CONFLICT (user_id)
            DO UPDATE SET name=EXCLUDED.name,
                          skills=EXCLUDED.skills,
                          price_from_minor=EXCLUDED.price_from_minor,
                          portfolio_url=EXCLUDED.portfolio_url,
                          skill_level=COALESCE(EXCLUDED.skill_level, editor_profiles.skill_level),
                          experience_description=COALESCE(EXCLUDED.experience_description, editor_profiles.experience_description),
                          avg_price_minor=COALESCE(EXCLUDED.avg_price_minor, editor_profiles.avg_price_minor),
                          updated_at=NOW()
            """,
            user_id, name, skills, price_from_minor, portfolio_url, skill_level, experience_description, avg_price_minor
        )

async def get_editor_profile(user_id: int) -> Optional[dict]:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT user_id,
                   name,
                   skills,
                   price_from_minor,
                   avg_price_minor,
                   portfolio_url,
                   skill_level,
                   experience_description,
                   verification_status,
                   verification_note,
                   test_submission
            FROM editor_profiles
            WHERE user_id=$1
            """,
            user_id,
        )
    return dict(row) if row else None

async def upsert_client_profile(user_id: int, name: str) -> None:
    p = pool()
    async with p.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO client_profiles (user_id, name)
            VALUES ($1,$2)
            ON CONFLICT (user_id)
            DO UPDATE SET name=EXCLUDED.name, updated_at=NOW()
            """,
            user_id, name
        )

async def get_client_profile(user_id: int) -> Optional[dict]:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id,name FROM client_profiles WHERE user_id=$1", user_id)
    return dict(row) if row else None

async def get_editor_profile_card(user_id: int) -> Optional[dict]:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                u.id AS user_id,
                u.role,
                u.username,
                u.display_name,
                u.created_at AS joined_at,
                ep.name,
                ep.skills,
                ep.price_from_minor,
                ep.avg_price_minor,
                ep.portfolio_url,
                ep.skill_level,
                ep.experience_description,
                ep.verification_status,
                ep.verification_note,
                COALESCE(stats.completed_orders, 0) AS completed_orders,
                ratings.avg_rating,
                COALESCE(ratings.review_count, 0) AS review_count
            FROM users u
            LEFT JOIN editor_profiles ep ON ep.user_id = u.id
            LEFT JOIN LATERAL (
                SELECT COUNT(*)::int AS completed_orders
                FROM orders
                WHERE editor_id = u.id
                  AND status = 'completed'
            ) stats ON TRUE
            LEFT JOIN LATERAL (
                SELECT ROUND(AVG(rating)::numeric, 2) AS avg_rating,
                       COUNT(*)::int AS review_count
                FROM order_reviews
                WHERE reviewee_user_id = u.id
            ) ratings ON TRUE
            WHERE u.id = $1
            """,
            user_id,
        )
    return dict(row) if row else None

async def get_client_profile_card(user_id: int) -> Optional[dict]:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                u.id AS user_id,
                u.role,
                u.username,
                u.display_name,
                u.created_at AS joined_at,
                cp.name,
                COALESCE(stats.completed_orders, 0) AS completed_orders,
                ratings.avg_rating,
                COALESCE(ratings.review_count, 0) AS review_count
            FROM users u
            LEFT JOIN client_profiles cp ON cp.user_id = u.id
            LEFT JOIN LATERAL (
                SELECT COUNT(*)::int AS completed_orders
                FROM orders
                WHERE client_id = u.id
                  AND status = 'completed'
            ) stats ON TRUE
            LEFT JOIN LATERAL (
                SELECT ROUND(AVG(rating)::numeric, 2) AS avg_rating,
                       COUNT(*)::int AS review_count
                FROM order_reviews
                WHERE reviewee_user_id = u.id
            ) ratings ON TRUE
            WHERE u.id = $1
            """,
            user_id,
        )
    return dict(row) if row else None
async def set_editor_verification(user_id: int, status: str, note: str | None = None) -> None:
    p = pool()
    async with p.acquire() as conn:
        await conn.execute(
            """
            UPDATE editor_profiles
            SET verification_status=$2,
                verification_note=$3,
                updated_at=NOW()
            WHERE user_id=$1
            """,
            user_id, status, note
        )

async def set_editor_test_submission(user_id: int, submission: str) -> None:
    p = pool()
    async with p.acquire() as conn:
        await conn.execute(
            """
            UPDATE editor_profiles
            SET test_submission=$2,
                verification_status='pending',
                verification_note=NULL,
                updated_at=NOW()
            WHERE user_id=$1
            """,
            user_id, submission
        )
