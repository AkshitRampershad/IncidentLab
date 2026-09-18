from collections import Counter
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select

from core.db import get_session_factory
from core.models import LogEventRecord
from evidence.models import Evidence, SourceType
from evidence.provenance import build_evidence_id, build_provenance
from evidence.scoring import SEARCH_WINDOW_PADDING, matches_query, temporal_relevance
from tools.incidents import get_incident

_SPIKE_THRESHOLD = 3  # error-level logs in one minute bucket to call it a spike


class LogSpike(BaseModel):
    """A derived aggregate over several log rows — not itself an Evidence
    (no single row backs it), so it gets its own shape rather than being
    forced into one."""

    service: str
    bucket_start: datetime
    error_count: int


def _to_evidence(row: LogEventRecord, *, relevance: float) -> Evidence:
    return Evidence(
        evidence_id=build_evidence_id(SourceType.LOG, row.id),
        source_type=SourceType.LOG,
        source=row.service,
        timestamp=row.timestamp,
        content=f"[{row.level}] {row.message}",
        relevance=relevance,
        provenance=build_provenance(table="log_events", row_id=row.id, incident_id=row.incident_id),
    )


async def search_logs(incident_id: str, query: str | None = None) -> list[Evidence]:
    """spec §11's search_logs(): every log for this incident's service, in
    a padded window around start/end, optionally filtered by a
    case-insensitive substring in the message."""
    incident = await get_incident(incident_id)
    window_start = incident.start_time - SEARCH_WINDOW_PADDING
    window_end = incident.end_time + SEARCH_WINDOW_PADDING

    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(LogEventRecord)
                .where(LogEventRecord.incident_id == incident_id)
                .where(LogEventRecord.timestamp >= window_start)
                .where(LogEventRecord.timestamp <= window_end)
                .order_by(LogEventRecord.timestamp)
            )
        ).all()

    evidence = []
    for row in rows:
        if not matches_query(row.message, query):
            continue
        relevance = temporal_relevance(row.timestamp, incident.start_time, incident.end_time)
        evidence.append(_to_evidence(row, relevance=relevance))
    return evidence


async def find_error_spikes(incident_id: str) -> list[LogSpike]:
    """spec §11's find_error_spikes(): minute-bucketed error-level log
    counts, only buckets at or above `_SPIKE_THRESHOLD`."""
    logs = await search_logs(incident_id)
    error_logs = [e for e in logs if e.content.startswith("[error]")]

    buckets: Counter[datetime] = Counter()
    for e in error_logs:
        bucket_start = e.timestamp.replace(second=0, microsecond=0)
        buckets[bucket_start] += 1

    incident = await get_incident(incident_id)
    return sorted(
        (
            LogSpike(service=incident.service, bucket_start=bucket_start, error_count=count)
            for bucket_start, count in buckets.items()
            if count >= _SPIKE_THRESHOLD
        ),
        key=lambda spike: spike.bucket_start,
    )
