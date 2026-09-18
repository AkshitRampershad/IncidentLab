import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import func, select

from core.db import create_all_tables, get_session_factory
from core.models import (
    DeploymentRecord,
    IncidentGroundTruthRecord,
    IncidentRecord,
    LogEventRecord,
    MetricPointRecord,
)
from simulator.models import IncidentDraft
from simulator.scenarios import get_injector


async def _next_incident_id(session) -> str:
    count = await session.scalar(select(func.count()).select_from(IncidentRecord))
    return f"INC-{count + 1:04d}"


async def persist_incident_draft(draft: IncidentDraft) -> str:
    """Persist an already-built `IncidentDraft` and return its incident_id.

    Shared by `run_scenario` (synthetic `FailureInjector` output) and
    `simulator.rcaeval_import` (real telemetry parsed from an RCAEval
    case) — everything past this point treats the two sources identically.
    Ground truth is written to its own table — nothing here ever writes it
    onto the investigator-visible `incidents` row.
    """
    await create_all_tables()

    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        incident_id = await _next_incident_id(session)

        session.add(
            IncidentRecord(
                incident_id=incident_id,
                service=draft.service,
                severity=draft.severity,
                description=draft.description,
                start_time=draft.start_time,
                end_time=draft.end_time,
            )
        )
        # Flush the parent row before adding its FK-dependent children —
        # cross-mapper flush ordering isn't guaranteed without an explicit
        # relationship() between them.
        await session.flush()

        session.add(
            IncidentGroundTruthRecord(
                incident_id=incident_id,
                scenario_id=draft.ground_truth.scenario_id,
                root_cause=draft.ground_truth.root_cause,
                affected_component=draft.ground_truth.affected_component,
                trigger=draft.ground_truth.trigger,
            )
        )
        session.add_all(
            LogEventRecord(
                incident_id=incident_id,
                service=log.service,
                timestamp=log.timestamp,
                level=log.level,
                message=log.message,
                is_distractor=log.is_distractor,
            )
            for log in draft.logs
        )
        session.add_all(
            MetricPointRecord(
                incident_id=incident_id,
                service=metric.service,
                timestamp=metric.timestamp,
                metric_name=metric.metric_name,
                value=metric.value,
                is_distractor=metric.is_distractor,
            )
            for metric in draft.metrics
        )
        session.add_all(
            DeploymentRecord(
                incident_id=incident_id,
                service=deploy.service,
                timestamp=deploy.timestamp,
                version=deploy.version,
                commit_sha=deploy.commit_sha,
                description=deploy.description,
                is_distractor=deploy.is_distractor,
            )
            for deploy in draft.deployments
        )

    return incident_id


async def run_scenario(scenario_id: str, anchor_time: datetime | None = None) -> str:
    """Generate, persist, and return the incident_id for one scenario run."""
    injector = get_injector(scenario_id)
    draft: IncidentDraft = injector.generate(anchor_time or datetime.now(UTC))
    return await persist_incident_draft(draft)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a reproducible incident from a scenario."
    )
    parser.add_argument("--scenario", required=True, help="Scenario ID, e.g. db_connection_pool")
    args = parser.parse_args()

    incident_id = asyncio.run(run_scenario(args.scenario))

    print(f"Created incident {incident_id} (scenario: {args.scenario})")
    print("Ground truth stored separately — never exposed to the investigator.")
    print(f"Next: make investigate INCIDENT={incident_id}  (lands in Phase 5)")


if __name__ == "__main__":
    main()
