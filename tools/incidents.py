from datetime import datetime

from pydantic import BaseModel

from core.db import get_session_factory
from core.models import IncidentRecord
from evidence.models import Evidence


class IncidentPublic(BaseModel):
    """What an investigator is allowed to see about an incident. No
    ground_truth field exists here, ever — that's `core.models.
    IncidentGroundTruthRecord`, a separate table this model never touches.
    """

    incident_id: str
    service: str
    severity: str
    description: str
    start_time: datetime
    end_time: datetime


async def get_incident(incident_id: str) -> IncidentPublic:
    session_factory = get_session_factory()
    async with session_factory() as session:
        record = await session.get(IncidentRecord, incident_id)

    if record is None:
        raise ValueError(f"Incident '{incident_id}' not found")

    return IncidentPublic(
        incident_id=record.incident_id,
        service=record.service,
        severity=record.severity,
        description=record.description,
        start_time=record.start_time,
        end_time=record.end_time,
    )


async def get_incident_timeline(incident_id: str) -> list[Evidence]:
    """Chronological merge of every log/metric/deployment Evidence in this
    incident's search window (spec §10's get_incident_timeline() /
    §32's Investigation Timeline).

    Local imports avoid a circular import: tools/logs.py, tools/metrics.py,
    and tools/deployments.py each import get_incident from this module.
    """
    from tools.deployments import get_recent_deployments
    from tools.logs import search_logs
    from tools.metrics import query_metrics

    logs = await search_logs(incident_id)
    metrics = await query_metrics(incident_id)
    deployments = await get_recent_deployments(incident_id)

    return sorted(logs + metrics + deployments, key=lambda e: e.timestamp)
