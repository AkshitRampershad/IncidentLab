from collections.abc import Callable

from sqlalchemy import select

from core.db import get_session_factory
from core.models import MetricPointRecord
from evidence.models import Evidence, SourceType
from evidence.provenance import build_evidence_id, build_provenance
from evidence.scoring import SEARCH_WINDOW_PADDING, temporal_relevance
from tools.incidents import get_incident
from tools.registry import allowlisted_tool

# metric_name -> (comparison, threshold). A deterministic experimental
# baseline (spec §16), not a calibrated alerting rule — thresholds are
# chosen to catch the simulator's one scenario, not tuned against real
# production data. compare_baseline() (spec §12) is intentionally not
# implemented yet: it needs a pre-incident "normal" window the simulator
# doesn't generate (only a couple of T+0 baseline points) — building it
# against fabricated baseline data would violate "never invent evidence".
_ANOMALY_THRESHOLDS: dict[str, tuple[str, float]] = {
    "error_rate": (">", 0.05),
    "latency_p99_ms": (">", 500),
    "cpu_usage_percent": (">", 90),
    "db_connections_active": (">=", 5),
    "cache_hit_rate": ("<", 0.3),
}

_COMPARISONS: dict[str, Callable[[float, float], bool]] = {
    ">": lambda value, threshold: value > threshold,
    ">=": lambda value, threshold: value >= threshold,
    "<": lambda value, threshold: value < threshold,
    "<=": lambda value, threshold: value <= threshold,
}


def known_anomaly_metrics() -> list[str]:
    """The metric_names detect_anomaly() has a threshold for. Callers
    (e.g. agents/metrics.py) use this instead of reaching into
    _ANOMALY_THRESHOLDS directly, so they never need to know it exists."""
    return sorted(_ANOMALY_THRESHOLDS)


def _to_evidence(row: MetricPointRecord, *, relevance: float) -> Evidence:
    return Evidence(
        evidence_id=build_evidence_id(SourceType.METRIC, row.id),
        source_type=SourceType.METRIC,
        source=row.service,
        timestamp=row.timestamp,
        content=f"{row.metric_name}={row.value}",
        relevance=relevance,
        provenance=build_provenance(
            table="metric_points", row_id=row.id, incident_id=row.incident_id
        ),
    )


@allowlisted_tool("query_metrics")
async def query_metrics(incident_id: str, metric_name: str | None = None) -> list[Evidence]:
    """spec §12's query_metrics(): every metric point for this incident's
    service in a padded window, optionally filtered to one metric_name."""
    incident = await get_incident(incident_id)
    window_start = incident.start_time - SEARCH_WINDOW_PADDING
    window_end = incident.end_time + SEARCH_WINDOW_PADDING

    stmt = (
        select(MetricPointRecord)
        .where(MetricPointRecord.incident_id == incident_id)
        .where(MetricPointRecord.timestamp >= window_start)
        .where(MetricPointRecord.timestamp <= window_end)
        .order_by(MetricPointRecord.timestamp)
    )
    if metric_name is not None:
        stmt = stmt.where(MetricPointRecord.metric_name == metric_name)

    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (await session.scalars(stmt)).all()

    return [
        _to_evidence(
            row, relevance=temporal_relevance(row.timestamp, incident.start_time, incident.end_time)
        )
        for row in rows
    ]


@allowlisted_tool("detect_anomaly")
async def detect_anomaly(incident_id: str, metric_name: str) -> list[Evidence]:
    """spec §12's detect_anomaly(): points for `metric_name` that cross a
    fixed, documented threshold (see _ANOMALY_THRESHOLDS)."""
    if metric_name not in _ANOMALY_THRESHOLDS:
        raise ValueError(
            f"No anomaly threshold registered for metric '{metric_name}'. "
            f"Known metrics: {', '.join(sorted(_ANOMALY_THRESHOLDS))}"
        )
    comparison, threshold = _ANOMALY_THRESHOLDS[metric_name]
    is_anomalous = _COMPARISONS[comparison]
    points = await query_metrics(incident_id, metric_name)

    return [e for e in points if is_anomalous(float(e.content.split("=")[1]), threshold)]
