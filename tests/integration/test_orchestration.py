from datetime import UTC, datetime

import pytest

from orchestration.graph import investigate
from simulator.replay import run_scenario

ANCHOR = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


@pytest.fixture
async def incident_id():
    return await run_scenario("db_connection_pool", anchor_time=ANCHOR)


async def test_full_investigation_end_to_end(incident_id):
    """incident -> agents -> hypotheses -> evidence -> RCA (spec §5),
    with no LLM configured — the deterministic path this sandbox can
    actually exercise."""
    state = await investigate(incident_id, llm=None)

    assert state["triage"].affected_services == ["checkout"]
    assert state["logs_finding"].agent_name == "logs"
    assert state["metrics_finding"].agent_name == "metrics"
    assert state["code_finding"].agent_name == "code"
    assert state["knowledge_finding"].agent_name == "knowledge"

    assert len(state["hypotheses"]) > 0
    assert state["hypotheses"] == sorted(
        state["hypotheses"], key=lambda h: h.confidence, reverse=True
    )

    adjudication = state["adjudication"]
    assert adjudication.selected_hypothesis == "Connection pool exhaustion"
    assert adjudication.confidence > 0.9
    assert adjudication.needs_human_review is False
    assert adjudication.contradicting_evidence == []
    assert "db-connection-pool-exhaustion" in adjudication.recommended_action


async def test_investigation_evidence_never_carries_is_distractor(incident_id):
    state = await investigate(incident_id, llm=None)
    for e in state["adjudication"].supporting_evidence:
        assert not hasattr(e, "is_distractor")


async def test_second_scenario_selects_a_different_hypothesis():
    """The system must be able to tell two different root causes apart,
    not always land on whatever the one well-tested scenario favors. Also
    exercises the contradiction detector for real: this scenario's
    elevated latency alone would suggest "connectivity issue", but the
    confirmed-normal error_rate reading contradicts it — the detector
    must penalize that hypothesis below the correct Redis one."""
    incident_id = await run_scenario("redis_unavailable", anchor_time=ANCHOR)
    state = await investigate(incident_id, llm=None)

    adjudication = state["adjudication"]
    assert adjudication.selected_hypothesis == "Cache layer (Redis) involvement"
    assert adjudication.confidence > 0.9
    assert adjudication.needs_human_review is False

    by_description = {h.description: h for h in state["hypotheses"]}
    connectivity = by_description.get("Database or downstream connectivity issue")
    if connectivity is not None:
        assert connectivity.contradicting_evidence != []
        assert connectivity.confidence < adjudication.confidence
