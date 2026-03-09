import asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None

async def init_db(dsn: str) -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=10)
    return _pool

def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    return _pool

async def run_migration_file(path: str) -> None:
    p = pool()
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    async with p.acquire() as conn:
        await conn.execute(sql)
