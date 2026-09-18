from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base

# All timestamps in this schema are timezone-aware (UTC in, UTC out) — the
# simulator and, later, real telemetry sources always produce aware
# datetimes, so every column is TIMESTAMPTZ rather than Postgres's naive
# default.
_TZ = DateTime(timezone=True)


class IncidentRecord(Base):
    """Investigator-visible incident. Never joins to ground truth."""

    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(primary_key=True)
    service: Mapped[str]
    severity: Mapped[str]
    description: Mapped[str]
    start_time: Mapped[datetime] = mapped_column(_TZ)
    end_time: Mapped[datetime] = mapped_column(_TZ)
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())


class IncidentGroundTruthRecord(Base):
    """Ground truth for an incident. Used only by the evaluation system —

    no tool or agent available to an investigation may query this table.
    Kept in its own table (not columns on IncidentRecord) specifically so
    that a query against `incidents` can never accidentally join it in.
    """

    __tablename__ = "incident_ground_truths"

    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), primary_key=True)
    scenario_id: Mapped[str]
    root_cause: Mapped[str]
    affected_component: Mapped[str]
    trigger: Mapped[str]


class LogEventRecord(Base):
    __tablename__ = "log_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    service: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(_TZ)
    level: Mapped[str]
    message: Mapped[str]
    # Ground-truth bookkeeping for the Phase 6 evaluation harness (precision/
    # recall against known-irrelevant noise). Any Phase 3+ tool that exposes
    # this row to an investigating agent MUST NOT include this column in its
    # output — it would trivially leak the answer.
    is_distractor: Mapped[bool] = mapped_column(default=False)


class MetricPointRecord(Base):
    __tablename__ = "metric_points"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    service: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(_TZ)
    metric_name: Mapped[str]
    value: Mapped[float]
    is_distractor: Mapped[bool] = mapped_column(default=False)


class DeploymentRecord(Base):
    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    service: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(_TZ)
    version: Mapped[str]
    commit_sha: Mapped[str]
    description: Mapped[str]
    is_distractor: Mapped[bool] = mapped_column(default=False)
