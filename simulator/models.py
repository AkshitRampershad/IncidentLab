from datetime import datetime

from pydantic import BaseModel


class GroundTruth(BaseModel):
    """Never exposed to the investigator — evaluation-only (spec §8)."""

    scenario_id: str
    root_cause: str
    affected_component: str
    trigger: str


class LogEvent(BaseModel):
    service: str
    timestamp: datetime
    level: str
    message: str
    is_distractor: bool = False


class MetricPoint(BaseModel):
    service: str
    timestamp: datetime
    metric_name: str
    value: float
    is_distractor: bool = False


class Deployment(BaseModel):
    service: str
    timestamp: datetime
    version: str
    commit_sha: str
    description: str
    is_distractor: bool = False


class IncidentDraft(BaseModel):
    """Everything a failure injector produces for one incident, before it
    has an incident_id (assigned at persistence time)."""

    service: str
    severity: str
    description: str
    start_time: datetime
    end_time: datetime
    ground_truth: GroundTruth
    logs: list[LogEvent]
    metrics: list[MetricPoint]
    deployments: list[Deployment]
