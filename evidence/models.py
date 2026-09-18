from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class SourceType(StrEnum):
    """Spec §9's supported evidence source types. Only LOG, METRIC, and
    DEPLOYMENT are actually produced as of Phase 3 (that's all the
    simulator generates) — the rest exist so Evidence's shape doesn't
    change again once tools/github.py and tools/knowledge.py land."""

    LOG = "log"
    METRIC = "metric"
    TRACE = "trace"
    DEPLOYMENT = "deployment"
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    DOCUMENTATION = "documentation"
    RUNBOOK = "runbook"
    HISTORICAL_INCIDENT = "historical_incident"


class Provenance(BaseModel):
    """Where this Evidence came from, precisely enough to re-fetch the
    underlying row. Deliberately has no `is_distractor` field, or anything
    else derived from ground truth — Provenance describes origin, not
    correctness."""

    table: str
    row_id: int
    incident_id: str
    retrieved_at: datetime


class Evidence(BaseModel):
    """A single sourced, provenanced fact a tool can hand to an agent.

    No `is_distractor` field exists here by construction: every tool that
    builds an Evidence from a `core.models` row must not copy that column
    across. This model being unable to carry it is the enforcement
    mechanism, not a docstring warning.
    """

    evidence_id: str
    source_type: SourceType
    source: str
    timestamp: datetime
    content: str
    relevance: float
    provenance: Provenance
