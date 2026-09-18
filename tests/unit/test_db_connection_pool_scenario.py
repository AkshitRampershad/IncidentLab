from datetime import UTC, datetime, timedelta

from simulator.failure_injector.db_connection_pool import DbConnectionPoolInjector

ANCHOR = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


def test_generation_is_deterministic():
    injector = DbConnectionPoolInjector()
    first = injector.generate(ANCHOR)
    second = injector.generate(ANCHOR)
    assert first == second


def test_timeline_bounds():
    draft = DbConnectionPoolInjector().generate(ANCHOR)
    assert draft.end_time == ANCHOR
    assert draft.start_time == ANCHOR - timedelta(minutes=15)
    assert draft.start_time < draft.end_time


def test_ground_truth_matches_scenario():
    draft = DbConnectionPoolInjector().generate(ANCHOR)
    assert draft.ground_truth.scenario_id == "db_connection_pool"
    assert draft.ground_truth.root_cause == "database_connection_pool_exhaustion"
    assert draft.ground_truth.affected_component == "postgres"
    assert draft.ground_truth.trigger == "deployment"


def test_includes_both_relevant_and_distractor_evidence():
    draft = DbConnectionPoolInjector().generate(ANCHOR)

    assert any(not log.is_distractor for log in draft.logs), "needs real evidence, not just noise"
    assert any(log.is_distractor for log in draft.logs), "needs distractor noise (spec §24)"
    assert any(d.is_distractor for d in draft.deployments), (
        "needs an unrelated distractor deployment"
    )
    assert any(not d.is_distractor for d in draft.deployments), (
        "needs the actual trigger deployment"
    )


def test_trigger_deployment_precedes_incident_start():
    draft = DbConnectionPoolInjector().generate(ANCHOR)
    trigger_deploys = [d for d in draft.deployments if not d.is_distractor]
    assert len(trigger_deploys) == 1
    assert trigger_deploys[0].timestamp < draft.start_time
    assert trigger_deploys[0].service == "checkout"


def test_all_non_distractor_telemetry_is_for_the_affected_service():
    draft = DbConnectionPoolInjector().generate(ANCHOR)
    for log in draft.logs:
        if not log.is_distractor:
            assert log.service == "checkout"
    for metric in draft.metrics:
        if not metric.is_distractor:
            assert metric.service == "checkout"
