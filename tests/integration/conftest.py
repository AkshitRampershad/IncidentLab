import pytest
from sqlalchemy import delete

from core.db import create_all_tables, get_engine
from core.models import (
    DeploymentRecord,
    IncidentGroundTruthRecord,
    IncidentRecord,
    LogEventRecord,
    MetricPointRecord,
)

# Children before parent, or the FK constraints on incident_id reject the delete.
_TABLES_CHILD_FIRST = [
    LogEventRecord,
    MetricPointRecord,
    DeploymentRecord,
    IncidentGroundTruthRecord,
    IncidentRecord,
]


@pytest.fixture(autouse=True)
async def clean_db():
    """Integration tests need a real, reachable Postgres (see
    docs/architecture.md) — same one `make incident` uses. Each test starts
    from an empty schema so incident_id sequencing is predictable."""
    await create_all_tables()
    engine = get_engine()
    async with engine.begin() as conn:
        for table in _TABLES_CHILD_FIRST:
            await conn.execute(delete(table))
    yield
