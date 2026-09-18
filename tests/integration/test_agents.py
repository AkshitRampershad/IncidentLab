from datetime import UTC, datetime, timedelta

import pytest

from agents import code, knowledge, logs, metrics, triage
from core.llm.base import LLMProvider
from simulator.replay import run_scenario

ANCHOR = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


class FakeLLM(LLMProvider):
    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        return "fake llm summary"


@pytest.fixture
async def incident_id():
    return await run_scenario("db_connection_pool", anchor_time=ANCHOR)


async def test_triage_agent(incident_id):
    finding = await triage.investigate(incident_id)

    assert finding.affected_services == ["checkout"]
    assert finding.time_window.start == ANCHOR - timedelta(minutes=15)
    assert finding.time_window.end == ANCHOR
    assert set(finding.investigation_targets) == {"checkout", "auth"}
    assert len(finding.initial_hypotheses) == 2  # the trigger deploy + the distractor deploy
    assert finding.summary  # non-empty deterministic fallback, no LLM configured


async def test_logs_agent(incident_id):
    finding = await logs.investigate(incident_id)

    assert finding.agent_name == "logs"
    assert len(finding.evidence) == 14
    assert any("12 error-level" in f for f in finding.findings)
    assert "Connection pool exhaustion" in finding.hypotheses_supported


async def test_metrics_agent(incident_id):
    finding = await metrics.investigate(incident_id)

    assert finding.agent_name == "metrics"
    metric_names_flagged = {h.replace(" anomaly", "") for h in finding.hypotheses_supported}
    assert metric_names_flagged == {"error_rate", "latency_p99_ms", "db_connections_active"}


async def test_code_agent(incident_id):
    finding = await code.investigate(incident_id)

    assert finding.agent_name == "code"
    assert len(finding.evidence) == 2
    assert len(finding.hypotheses_supported) == 1
    assert "checkout" in finding.hypotheses_supported[0]


async def test_knowledge_agent(incident_id):
    finding = await knowledge.investigate(incident_id)

    assert finding.agent_name == "knowledge"
    assert len(finding.evidence) == 3  # 1 runbook + 1 architecture doc + 1 historical incident
    assert finding.hypotheses_supported == []


async def test_agents_use_llm_when_provided(incident_id):
    finding = await logs.investigate(incident_id, llm=FakeLLM())
    assert finding.summary == "fake llm summary"


async def test_agent_finding_evidence_never_carries_is_distractor(incident_id):
    finding = await logs.investigate(incident_id)
    for e in finding.evidence:
        assert not hasattr(e, "is_distractor")
