from app.db import pool

async def create_order(
    client_id: int,
    title: str,
    description: str,
    budget_minor: int,
    currency: str = "USD",
) -> int:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO orders (client_id, title, description, budget_minor, currency)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            client_id,
            title,
            description,
            budget_minor,
            currency,
        )
    return int(row["id"])
