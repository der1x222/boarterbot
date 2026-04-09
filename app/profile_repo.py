from typing import Optional
from app.db import pool

async def upsert_editor_profile(
    user_id: int, 
    name: str, 
    skills: str, 
    price_from_minor: int, 
    portfolio_url: str,
    skill_level: str = "",
    experience_description: str = "",
) -> None:
    p = pool()
    async with p.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO editor_profiles (user_id, name, skills, price_from_minor, portfolio_url, skill_level, experience_description)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (user_id)
            DO UPDATE SET name=EXCLUDED.name,
                          skills=EXCLUDED.skills,
                          price_from_minor=EXCLUDED.price_from_minor,
                          portfolio_url=EXCLUDED.portfolio_url,
                          skill_level=EXCLUDED.skill_level,
                          experience_description=EXCLUDED.experience_description,
                          updated_at=NOW()
            """,
            user_id, name, skills, price_from_minor, portfolio_url, skill_level, experience_description
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
