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


class InvestigatorFinding(BaseModel):
    """spec §11's shared output shape for the Log/Metrics/Code/Knowledge
    investigator agents."""

    agent_name: str
    findings: list[str]
    evidence: list[Evidence]
    hypotheses_supported: list[str]
    summary: str
