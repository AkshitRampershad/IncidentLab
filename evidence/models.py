from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class SourceType(StrEnum):
    """Spec §9's supported evidence source types. LOG, METRIC, DEPLOYMENT
    (Phase 2 telemetry) and RUNBOOK, DOCUMENTATION, HISTORICAL_INCIDENT
    (Phase 4's file-backed knowledge base) are produced; COMMIT,
    PULL_REQUEST, and TRACE still aren't — no real git/tracing
    integration exists yet (see docs/design-decisions.md)."""

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
    underlying row or file. Deliberately has no `is_distractor` field, or
    anything else derived from ground truth — Provenance describes origin,
    not correctness.

    `row_id` is a str (not int) so it can be either a DB primary key
    (stringified) or a knowledge-base file's relative path — one shape for
    "where did this come from", regardless of source.
    """

    table: str
    row_id: str
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
