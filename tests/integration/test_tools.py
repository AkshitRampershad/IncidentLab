from datetime import UTC, datetime

import pytest

from evidence.models import Evidence, SourceType
from simulator.replay import run_scenario
from tools.deployments import get_recent_deployments
from tools.incidents import get_incident, get_incident_timeline
from tools.logs import find_error_spikes, search_logs
from tools.metrics import detect_anomaly, query_metrics

ANCHOR = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


@pytest.fixture
async def incident_id():
    return await run_scenario("db_connection_pool", anchor_time=ANCHOR)


def test_evidence_model_structurally_cannot_carry_is_distractor():
    assert "is_distractor" not in Evidence.model_fields


async def test_get_incident_exposes_only_public_fields(incident_id):
    incident = await get_incident(incident_id)
    assert incident.service == "checkout"
    assert not hasattr(incident, "root_cause")


async def test_get_incident_raises_for_unknown_id():
    with pytest.raises(ValueError, match="not found"):
        await get_incident("INC-9999")


async def test_search_logs_returns_all_logs_in_window_including_distractors(incident_id):
    evidence = await search_logs(incident_id)

    assert len(evidence) == 14  # 12 error logs + 1 redis warning + 1 cache-miss, from the scenario
    assert all(e.source_type == SourceType.LOG for e in evidence)
    # Distractor content is present (an agent must be able to see it to
    # correctly discount it) — it's just not flagged as such.
    assert any("redis" in e.content.lower() for e in evidence)


async def test_search_logs_query_filters_case_insensitively(incident_id):
    redis_only = await search_logs(incident_id, query="REDIS")
    assert len(redis_only) == 1
    assert "redis" in redis_only[0].content.lower()

    timeouts = await search_logs(incident_id, query="connection timeout")
    assert len(timeouts) == 12


async def test_find_error_spikes_detects_the_saturation_spike(incident_id):
    spikes = await find_error_spikes(incident_id)
    assert len(spikes) == 1
    assert spikes[0].error_count == 12
    assert spikes[0].service == "checkout"


async def test_query_metrics_filters_by_name(incident_id):
    error_rate_points = await query_metrics(incident_id, "error_rate")
    assert len(error_rate_points) == 1
    assert error_rate_points[0].content == "error_rate=0.42"

    all_metrics = await query_metrics(incident_id)
    assert len(all_metrics) > len(error_rate_points)


async def test_detect_anomaly_flags_the_expected_points(incident_id):
    error_rate_anomalies = await detect_anomaly(incident_id, "error_rate")
    assert len(error_rate_anomalies) == 1

    connections_anomalies = await detect_anomaly(incident_id, "db_connections_active")
    # Only the saturated (value=5) point should be flagged, not the
    # baseline (value=4) one.
    assert len(connections_anomalies) == 1
    assert connections_anomalies[0].content == "db_connections_active=5.0"


async def test_detect_anomaly_raises_for_unregistered_metric(incident_id):
    with pytest.raises(ValueError, match="No anomaly threshold"):
        await detect_anomaly(incident_id, "made_up_metric")


async def test_get_recent_deployments_spans_services(incident_id):
    deployments = await get_recent_deployments(incident_id)
    services = {d.source for d in deployments}
    assert services == {"checkout", "auth"}


async def test_get_incident_timeline_merges_sources_in_chronological_order(incident_id):
    timeline = await get_incident_timeline(incident_id)

    source_types = {e.source_type for e in timeline}
    assert source_types == {SourceType.LOG, SourceType.METRIC, SourceType.DEPLOYMENT}
    assert timeline == sorted(timeline, key=lambda e: e.timestamp)
