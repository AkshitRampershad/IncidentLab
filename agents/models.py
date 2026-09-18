from datetime import datetime

from pydantic import BaseModel

from evidence.models import Evidence


class TimeWindow(BaseModel):
    start: datetime
    end: datetime


class TriageFinding(BaseModel):
    """spec §10's Triage Agent output shape."""

    affected_services: list[str]
    time_window: TimeWindow
    investigation_targets: list[str]
    initial_hypotheses: list[str]
    summary: str


class HypothesisSignal(BaseModel):
    """One hypothesis an agent's evidence supports, with exactly which
    evidence items support it. The Hypothesis Manager (Phase 5) needs this
    precise linkage — re-deriving it later by re-parsing evidence content
    would be fragile and duplicate logic the agent already has."""

    hypothesis: str
    evidence_ids: list[str]


class InvestigatorFinding(BaseModel):
    """spec §11's shared output shape for the Log/Metrics/Code/Knowledge
    investigator agents."""

    agent_name: str
    findings: list[str]
    evidence: list[Evidence]
    hypotheses_supported: list[HypothesisSignal]
    summary: str
