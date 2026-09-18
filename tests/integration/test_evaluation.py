from datetime import UTC, datetime

import pytest

from evaluation.baselines import direct_llm_investigate, single_agent_investigate
from evaluation.datasets import generate_dataset
from evaluation.ground_truth import get_ground_truth
from evaluation.reports import format_report
from evaluation.runner import run_benchmark
from simulator.replay import run_scenario
from tools.logs import search_logs

ANCHOR = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


@pytest.fixture
async def db_pool_incident_id():
    return await run_scenario("db_connection_pool", anchor_time=ANCHOR)


async def test_ground_truth_matches_the_real_scenario(db_pool_incident_id):
    ground_truth = await get_ground_truth(db_pool_incident_id)
    assert ground_truth.correct_hypothesis == "Connection pool exhaustion"
    assert ground_truth.root_cause == "database_connection_pool_exhaustion"

    logs = await search_logs(db_pool_incident_id)
    redis_distractor = next(e for e in logs if "redis" in e.content.lower())
    real_error_log = next(e for e in logs if "pool exhausted" in e.content.lower())

    assert redis_distractor.evidence_id not in ground_truth.non_distractor_evidence_ids
    assert real_error_log.evidence_id in ground_truth.non_distractor_evidence_ids


async def test_ground_truth_raises_for_unknown_incident():
    with pytest.raises(ValueError, match="No ground truth"):
        await get_ground_truth("INC-9999")


async def test_direct_llm_without_llm_is_honestly_insufficient(db_pool_incident_id):
    result = await direct_llm_investigate(db_pool_incident_id, None)
    assert result.selected_hypothesis is None
    assert result.confidence == 0.0
    assert result.needs_human_review is True
    assert result.supporting_evidence == []


async def test_single_agent_picks_a_hypothesis_without_contradiction_detection(db_pool_incident_id):
    result = await single_agent_investigate(db_pool_incident_id, None)
    assert result.selected_hypothesis is not None
    assert result.contradicting_evidence == []  # this baseline never checks for contradictions


async def test_generate_dataset_produces_distinct_incidents_across_both_scenarios():
    dataset = await generate_dataset(instances_per_scenario=2)
    assert len(dataset) == 4
    incident_ids = [incident_id for incident_id, _ in dataset]
    assert len(set(incident_ids)) == 4  # all distinct
    assert {scenario_id for _, scenario_id in dataset} == {
        "db_connection_pool",
        "redis_unavailable",
    }


async def test_run_benchmark_end_to_end():
    """The actual `make benchmark` path, with no LLM (fast, deterministic
    — what this sandbox can run for real)."""
    report = await run_benchmark(instances_per_scenario=1, llm=None)

    assert report.dataset_size == 2
    architectures = {a.architecture: a for a in report.architectures}
    assert set(architectures) == {"direct_llm", "single_agent", "multi_agent"}
    for aggregate in architectures.values():
        assert aggregate.n == 2

    # Direct LLM has zero evidence access and no LLM configured — it can
    # never be right, and this is not a bug in the harness, it's the
    # actual finding this baseline exists to produce.
    assert architectures["direct_llm"].root_cause_accuracy == 0.0
    assert architectures["direct_llm"].human_escalation_rate == 1.0

    # Multi-agent correctly solves both real scenarios deterministically
    # (verified manually in tests/integration/test_orchestration.py).
    assert architectures["multi_agent"].root_cause_accuracy == 1.0

    rendered = format_report(report)
    assert "IncidentLab Evaluation" in rendered
    assert "Direct LLM" in rendered
    assert "Single Agent" in rendered
    assert "Multi-Agent" in rendered
