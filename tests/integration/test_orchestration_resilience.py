from datetime import UTC, datetime

import pytest

import agents.code
import agents.knowledge
import agents.logs
import agents.metrics
import agents.triage
from core.config import Settings
from orchestration import graph as graph_module
from orchestration.graph import InvestigationTimeoutError, investigate
from simulator.replay import run_scenario
from tools.registry import ToolTimeoutError

ANCHOR = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


@pytest.fixture
async def incident_id():
    return await run_scenario("db_connection_pool", anchor_time=ANCHOR)


async def test_one_agent_failing_does_not_crash_the_investigation(incident_id, monkeypatch):
    """spec §43's own worked example, verified end to end: "If Log Agent
    fails ... continue investigation with: Metrics, Code, Knowledge." A
    tool timeout, a DB hiccup, anything — one investigator raising must
    not take down the whole graph."""

    async def _boom(incident_id, llm=None):
        raise ToolTimeoutError("simulated log agent failure")

    monkeypatch.setattr(agents.logs, "investigate", _boom)

    state = await investigate(incident_id, llm=None)

    assert state["logs_finding"].degraded is True
    assert state["logs_finding"].evidence == []
    assert "simulated log agent failure" in state["logs_finding"].summary

    # The rest of the investigation proceeded normally on real evidence.
    assert state["metrics_finding"].degraded is False
    assert state["code_finding"].degraded is False
    assert state["knowledge_finding"].degraded is False
    assert state["triage"].degraded is False
    # Metrics/code/knowledge alone still produce a real conclusion — losing
    # one agent's evidence changes which hypothesis wins (metrics still
    # supports both "connection pool" and "connectivity" readings), but the
    # investigation isn't left with nothing.
    assert state["adjudication"].selected_hypothesis is not None


async def test_triage_failing_still_lets_the_rest_of_the_graph_run(incident_id, monkeypatch):
    async def _boom(incident_id, llm=None):
        raise RuntimeError("simulated triage failure")

    monkeypatch.setattr(agents.triage, "investigate", _boom)

    state = await investigate(incident_id, llm=None)

    assert state["triage"].degraded is True
    assert "simulated triage failure" in state["triage"].summary
    assert state["logs_finding"].degraded is False
    assert state["adjudication"].selected_hypothesis == "Connection pool exhaustion"


async def test_unknown_incident_still_raises_value_error_rather_than_degrading(monkeypatch):
    """A nonexistent incident_id is a genuine bad request, not a
    degraded-but-continuable agent failure — every agent would fail
    identically and there's nothing to investigate. This must keep
    propagating as ValueError so the API layer's 404 handling still
    works (apps/api/routes/investigations.py)."""
    with pytest.raises(ValueError):
        await investigate("INC-9999", llm=None)


async def test_all_investigator_agents_failing_still_produces_a_safe_adjudication(
    incident_id, monkeypatch
):
    async def _boom(incident_id, llm=None):
        raise RuntimeError("simulated total agent outage")

    monkeypatch.setattr(agents.logs, "investigate", _boom)
    monkeypatch.setattr(agents.metrics, "investigate", _boom)
    monkeypatch.setattr(agents.code, "investigate", _boom)
    monkeypatch.setattr(agents.knowledge, "investigate", _boom)

    state = await investigate(incident_id, llm=None)

    for key in ("logs_finding", "metrics_finding", "code_finding", "knowledge_finding"):
        assert state[key].degraded is True

    # No evidence at all -> no hypotheses -> the adjudicator's own
    # documented "no hypotheses" fallback, not a crash.
    assert state["hypotheses"] == []
    assert state["adjudication"].selected_hypothesis is None
    assert state["adjudication"].needs_human_review is True


async def test_investigation_timeout_is_enforced(incident_id, monkeypatch):
    async def _slow(incident_id, llm=None):
        import asyncio

        await asyncio.sleep(1)
        raise AssertionError("should have been cancelled by the investigation timeout")

    monkeypatch.setattr(
        graph_module,
        "get_settings",
        lambda: Settings(investigation_timeout_seconds=0.02),
    )
    monkeypatch.setattr(agents.triage, "investigate", _slow)

    with pytest.raises(InvestigationTimeoutError):
        await investigate(incident_id, llm=None)
