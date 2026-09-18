from datetime import UTC, datetime

from evidence.models import Provenance, SourceType

_ID_PREFIX = {
    SourceType.LOG: "LOG",
    SourceType.METRIC: "METRIC",
    SourceType.DEPLOYMENT: "DEPLOY",
    SourceType.RUNBOOK: "RUNBOOK",
    SourceType.DOCUMENTATION: "DOC",
    SourceType.HISTORICAL_INCIDENT: "HIST",
}


def build_evidence_id(source_type: SourceType, row_id: int | str) -> str:
    prefix = _ID_PREFIX.get(source_type)
    if prefix is None:
        raise ValueError(f"No evidence_id prefix registered for source type {source_type!r}")
    return f"{prefix}-{row_id}"


def build_provenance(*, table: str, row_id: int | str, incident_id: str) -> Provenance:
    return Provenance(
        table=table,
        row_id=str(row_id),
        incident_id=incident_id,
        retrieved_at=datetime.now(UTC),
    )
