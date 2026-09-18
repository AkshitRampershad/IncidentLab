from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect, select

from core.db import get_session_factory
from core.models import (
    DeploymentRecord,
    IncidentGroundTruthRecord,
    IncidentRecord,
    LogEventRecord,
    MetricPointRecord,
)
from simulator.replay import run_scenario

ANCHOR = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


async def test_run_scenario_persists_incident_and_telemetry():
    incident_id = await run_scenario("db_connection_pool", anchor_time=ANCHOR)

    assert incident_id == "INC-0001"

    session_factory = get_session_factory()
    async with session_factory() as session:
        incident = await session.get(IncidentRecord, incident_id)
        assert incident is not None
        assert incident.service == "checkout"
        assert incident.severity == "critical"
        assert incident.start_time == ANCHOR - timedelta(minutes=15)
        assert incident.end_time == ANCHOR

        logs = (
            await session.scalars(
                select(LogEventRecord).where(LogEventRecord.incident_id == incident_id)
            )
        ).all()
        metrics = (
            await session.scalars(
                select(MetricPointRecord).where(MetricPointRecord.incident_id == incident_id)
            )
        ).all()
        deployments = (
            await session.scalars(
                select(DeploymentRecord).where(DeploymentRecord.incident_id == incident_id)
            )
        ).all()

        assert len(logs) > 0
        assert len(metrics) > 0
        assert len(deployments) == 2  # the trigger deploy + one distractor
        assert any(log.is_distractor for log in logs)
        assert any(not log.is_distractor for log in logs)


async def test_ground_truth_is_never_on_the_public_incident_table():
    incident_id = await run_scenario("db_connection_pool", anchor_time=ANCHOR)

    public_columns = {c.key for c in inspect(IncidentRecord).columns}
    assert not public_columns & {"root_cause", "affected_component", "trigger", "scenario_id"}

    session_factory = get_session_factory()
    async with session_factory() as session:
        ground_truth = await session.get(IncidentGroundTruthRecord, incident_id)
        assert ground_truth is not None
        assert ground_truth.root_cause == "database_connection_pool_exhaustion"
        assert ground_truth.affected_component == "postgres"
        assert ground_truth.trigger == "deployment"
        assert ground_truth.scenario_id == "db_connection_pool"


async def test_incident_ids_are_sequential():
    first = await run_scenario("db_connection_pool", anchor_time=ANCHOR)
    second = await run_scenario("db_connection_pool", anchor_time=ANCHOR)

    assert first == "INC-0001"
    assert second == "INC-0002"


async def test_unknown_scenario_raises_before_touching_the_database():
    with pytest.raises(ValueError, match="Unknown scenario"):
        await run_scenario("does_not_exist", anchor_time=ANCHOR)

    session_factory = get_session_factory()
    async with session_factory() as session:
        count = len((await session.scalars(select(IncidentRecord))).all())
    assert count == 0
