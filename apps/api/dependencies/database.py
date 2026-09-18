from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from apps.api.dependencies.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


async def check_connection() -> bool:
    """Raw connectivity check for the readiness probe.

    No ORM models exist yet (Phase 3 introduces the evidence/incident
    schema) — Phase 1 only needs to confirm Postgres is reachable.
    """
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
