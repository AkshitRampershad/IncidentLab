from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for every ORM model in the project."""


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


def get_session_factory() -> async_sessionmaker:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def check_connection() -> bool:
    """Raw connectivity check for the API's readiness probe."""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True


async def create_all_tables() -> None:
    """Idempotent schema creation for local/dev use.

    No migration tool (Alembic) yet — the schema is still small and
    actively changing across phases. Introduce Alembic once it stabilizes
    enough that hand-editing migrations is worth the ceremony.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
