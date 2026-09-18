from sqlalchemy import select

from apps.api.main import app, lifespan
from core.db import Base, get_engine, get_session_factory
from core.models import IncidentRecord


async def test_lifespan_creates_schema_against_a_truly_fresh_database():
    """Regression test for a real bug found by manual browser testing: a
    freshly-started API process against an empty Postgres (nobody has ever
    created an incident) 500'd on GET /incidents with "relation incidents
    does not exist", because only simulator.replay.run_scenario() ever
    called create_all_tables() — a read-only route had no write to
    piggyback schema creation on.

    tests/integration/conftest.py's autouse `clean_db` fixture calls
    create_all_tables() itself before every test, which means it was
    silently masking this exact bug from the rest of the suite — this
    test deliberately drops everything first and drives the app's actual
    lifespan hook (ASGITransport doesn't trigger ASGI lifespan events the
    way a real server does, so this is the one place that hook gets
    exercised at all).
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    async with lifespan(app):
        pass

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.scalars(select(IncidentRecord))
        assert list(result) == []
