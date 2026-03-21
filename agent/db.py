"""Asyncpg connection pool for Temporal worker activities."""
import asyncpg
import os

_pool = None


async def get_db_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        db_url = os.environ.get("SUPABASE_DB_URL", "")
        _pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
    return _pool
