from pydantic import BaseModel
from sqlalchemy import select

from core.db import get_session_factory
from core.models import (
    DeploymentRecord,
    IncidentGroundTruthRecord,
    LogEventRecord,
    MetricPointRecord,
)
from evidence.models import SourceType
from evidence.provenance import build_evidence_id

# root_cause (as written by simulator/failure_injector/) -> the exact
# canonical hypothesis description (hypotheses/manager.py's
# _CANONICAL_HYPOTHESES keys) that counts as "the system got it right" if
# selected. This mapping is the one place ground truth and the
# investigator's hypothesis vocabulary are allowed to touch — nowhere else
# in the codebase do they (spec §8, §18: ground truth is evaluation-only).
_ROOT_CAUSE_TO_HYPOTHESIS: dict[str, str] = {
    "database_connection_pool_exhaustion": "Connection pool exhaustion",
    "redis_unavailable": "Cache layer (Redis) involvement",
}

_TELEMETRY_TABLES = [
    (LogEventRecord, SourceType.LOG),
    (MetricPointRecord, SourceType.METRIC),
    (DeploymentRecord, SourceType.DEPLOYMENT),
]


class GroundTruthLookup(BaseModel):
    incident_id: str
    scenario_id: str
    root_cause: str
    correct_hypothesis: str
    non_distractor_evidence_ids: set[str]


async def get_ground_truth(incident_id: str) -> GroundTruthLookup:
    """Reads `core.models.IncidentGroundTruthRecord` and the
    `is_distractor` flag directly — this module (and the simulator that
    writes them) are the only code in the project allowed to. No agent,
    tool, or orchestration code imports from here.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        record = await session.get(IncidentGroundTruthRecord, incident_id)
        if record is None:
            raise ValueError(f"No ground truth recorded for incident '{incident_id}'")

        non_distractor_ids: set[str] = set()
        for model, source_type in _TELEMETRY_TABLES:
            rows = (
                await session.scalars(
                    select(model).where(
                        model.incident_id == incident_id, model.is_distractor.is_(False)
                    )
                )
            ).all()
            non_distractor_ids.update(build_evidence_id(source_type, row.id) for row in rows)

    correct_hypothesis = _ROOT_CAUSE_TO_HYPOTHESIS.get(record.root_cause)
    if correct_hypothesis is None:
        raise ValueError(
            f"No hypothesis-text mapping registered for root_cause '{record.root_cause}'"
        )

    return GroundTruthLookup(
        incident_id=incident_id,
        scenario_id=record.scenario_id,
        root_cause=record.root_cause,
        correct_hypothesis=correct_hypothesis,
        non_distractor_evidence_ids=non_distractor_ids,
    )
