from app.db import pool

async def create_order(
    client_id: int,
    title: str,
    description: str,
    budget_minor: int,
    revision_price_minor: int,
    deadline_at,
    currency: str = "USD",
) -> int:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO orders (client_id, title, description, budget_minor, revision_price_minor, deadline_at, currency)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            client_id,
            title,
            description,
            budget_minor,
            revision_price_minor,
            deadline_at,
            currency,
        )
    return int(row["id"])

async def list_orders_for_client(user_id: int, limit: int = 10) -> list[dict]:
    p = pool()
    async with p.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, budget_minor, currency, status, created_at, deadline_at
            FROM orders
            WHERE client_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
    return [dict(r) for r in rows]

async def get_order_for_client(order_id: int, user_id: int) -> dict | None:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, title, description, budget_minor, revision_price_minor, currency, status, created_at, deadline_at, editor_id
            FROM orders
            WHERE id = $1 AND client_id = $2
            """,
            order_id,
            user_id,
        )
    return dict(row) if row else None

async def list_open_orders(limit: int = 10) -> list[dict]:
    p = pool()
    async with p.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, budget_minor, currency, created_at, deadline_at
            FROM orders
            WHERE status = 'open'
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]

async def list_orders_for_editor(user_id: int, limit: int = 10) -> list[dict]:
    p = pool()
    async with p.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, status, created_at
            FROM orders
            WHERE editor_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
    return [dict(r) for r in rows]

async def get_order_by_id(order_id: int) -> dict | None:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, client_id, editor_id, title, description, budget_minor, revision_price_minor, currency, status,
                   created_at, deadline_at, dispute_opened_at, dispute_opened_by, dispute_client_agree, dispute_editor_agree
            FROM orders
            WHERE id = $1
            """,
            order_id,
        )
    return dict(row) if row else None

async def open_dispute(order_id: int, opened_by: int) -> bool:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE orders
            SET status = 'dispute',
                dispute_opened_at = NOW(),
                dispute_opened_by = $2,
                dispute_client_agree = FALSE,
                dispute_editor_agree = FALSE,
                updated_at = NOW()
            WHERE id = $1
              AND status = 'accepted'
              AND editor_id IS NOT NULL
            RETURNING id
            """,
            order_id,
            opened_by,
        )
    return bool(row)

async def set_dispute_agree(order_id: int, user_role: str) -> tuple[bool, bool]:
    p = pool()
    async with p.acquire() as conn:
        if user_role == "client":
            row = await conn.fetchrow(
                """
                UPDATE orders
                SET dispute_client_agree = TRUE,
                    updated_at = NOW()
                WHERE id = $1 AND status = 'dispute'
                RETURNING dispute_client_agree, dispute_editor_agree
                """,
                order_id,
            )
        else:
            row = await conn.fetchrow(
                """
                UPDATE orders
                SET dispute_editor_agree = TRUE,
                    updated_at = NOW()
                WHERE id = $1 AND status = 'dispute'
                RETURNING dispute_client_agree, dispute_editor_agree
                """,
                order_id,
            )
    if not row:
        return False, False
    return bool(row["dispute_client_agree"]), bool(row["dispute_editor_agree"])

async def close_dispute(order_id: int) -> bool:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE orders
            SET status = 'accepted',
                updated_at = NOW()
            WHERE id = $1 AND status = 'dispute'
            RETURNING id
            """,
            order_id,
        )
    return bool(row)

async def update_order_if_open(
    order_id: int,
    client_id: int,
    title: str,
    description: str,
    budget_minor: int,
    revision_price_minor: int,
    deadline_at,
) -> bool:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE orders
            SET title = $3,
                description = $4,
                budget_minor = $5,
                revision_price_minor = $6,
                deadline_at = $7,
                updated_at = NOW()
            WHERE id = $1
              AND client_id = $2
              AND status = 'open'
              AND editor_id IS NULL
            RETURNING id
            """,
            order_id,
            client_id,
            title,
            description,
            budget_minor,
            revision_price_minor,
            deadline_at,
        )
    return bool(row)

async def accept_order(order_id: int, editor_id: int) -> bool:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE orders
            SET status = 'accepted',
                editor_id = $2,
                updated_at = NOW()
            WHERE id = $1
              AND status = 'open'
              AND editor_id IS NULL
            RETURNING id
            """,
            order_id,
            editor_id,
        )
    return bool(row)
