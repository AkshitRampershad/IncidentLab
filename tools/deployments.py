from sqlalchemy import select

from core.db import get_session_factory
from core.models import DeploymentRecord
from evidence.models import Evidence, SourceType
from evidence.provenance import build_evidence_id, build_provenance
from evidence.scoring import SEARCH_WINDOW_PADDING, temporal_relevance
from tools.incidents import get_incident
from tools.registry import allowlisted_tool


def _to_evidence(row: DeploymentRecord, *, relevance: float) -> Evidence:
    return Evidence(
        evidence_id=build_evidence_id(SourceType.DEPLOYMENT, row.id),
        source_type=SourceType.DEPLOYMENT,
        source=row.service,
        timestamp=row.timestamp,
        content=f"{row.description} (version={row.version}, commit={row.commit_sha})",
        relevance=relevance,
        provenance=build_provenance(
            table="deployments", row_id=row.id, incident_id=row.incident_id
        ),
    )


@allowlisted_tool("get_recent_deployments")
async def get_recent_deployments(incident_id: str) -> list[Evidence]:
    """spec §10/§13's get_recent_deployments(): deployments in a padded
    window before/after the incident, across every service (not just the
    affected one — a deploy to an unrelated service is exactly the kind of
    distractor an agent needs to be able to see and correctly discount)."""
    incident = await get_incident(incident_id)
    window_start = incident.start_time - SEARCH_WINDOW_PADDING
    window_end = incident.end_time + SEARCH_WINDOW_PADDING

    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(DeploymentRecord)
                .where(DeploymentRecord.incident_id == incident_id)
                .where(DeploymentRecord.timestamp >= window_start)
                .where(DeploymentRecord.timestamp <= window_end)
                .order_by(DeploymentRecord.timestamp)
            )
        ).all()

    return [
        _to_evidence(
            row, relevance=temporal_relevance(row.timestamp, incident.start_time, incident.end_time)
        )
        for row in rows
    ]
