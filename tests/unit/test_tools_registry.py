import asyncio

import pytest
import structlog.testing

from core.config import Settings
from tools import registry as registry_module
from tools.registry import (
    ToolBudgetExceededError,
    ToolNotAllowed,
    ToolTimeoutError,
    allowed_tools,
    allowlisted_tool,
    call_tool,
    current_tool_call_count,
    reset_tool_budget,
)


def _settings(**overrides) -> Settings:
    defaults: dict = {"tool_timeout_seconds": 5.0, "max_tool_calls_per_investigation": 100}
    defaults.update(overrides)
    return Settings(**defaults)


def test_allowlisted_tool_registers_its_name():
    @allowlisted_tool("_unit_test_tool_registration")
    async def _t():
        return None

    assert "_unit_test_tool_registration" in allowed_tools()


async def test_call_tool_dispatches_a_registered_tool_by_name():
    @allowlisted_tool("_unit_test_tool_dispatch")
    async def _t(value):
        return value * 2

    assert await call_tool("_unit_test_tool_dispatch", 21) == 42


async def test_call_tool_rejects_an_unregistered_name():
    with pytest.raises(ToolNotAllowed):
        await call_tool("_never_registered_tool_name")


async def test_tool_call_outside_an_investigation_context_is_unbudgeted():
    """reset_tool_budget() is only ever called by orchestration.graph.
    investigate() at the start of a real investigation — a tool invoked
    directly (as a unit test does, or as a standalone API route that
    isn't running the whole graph) has no active budget to exceed."""

    @allowlisted_tool("_unit_test_tool_unbudgeted")
    async def _t():
        return "ok"

    for _ in range(10):
        assert await _t() == "ok"


async def test_budget_is_enforced_once_an_investigation_resets_it(monkeypatch):
    monkeypatch.setattr(
        registry_module, "get_settings", lambda: _settings(max_tool_calls_per_investigation=2)
    )

    @allowlisted_tool("_unit_test_tool_budget")
    async def _t():
        return "ok"

    reset_tool_budget()
    assert await _t() == "ok"
    assert await _t() == "ok"
    with pytest.raises(ToolBudgetExceededError):
        await _t()
    assert current_tool_call_count() == 3


async def test_budget_is_shared_across_concurrent_calls_in_the_same_context(monkeypatch):
    """The exact mechanism the orchestrator relies on: LangGraph's parallel
    investigator nodes are concurrent asyncio Tasks spawned from the same
    parent context, and must all draw down one shared budget rather than
    each silently getting its own — see registry.py's _call_count
    docstring for why a mutable list, not a plain int, makes that true."""
    monkeypatch.setattr(
        registry_module, "get_settings", lambda: _settings(max_tool_calls_per_investigation=5)
    )

    @allowlisted_tool("_unit_test_tool_concurrent")
    async def _t():
        return "ok"

    reset_tool_budget()
    results = await asyncio.gather(*(_t() for _ in range(5)))
    assert results == ["ok"] * 5
    assert current_tool_call_count() == 5


async def test_tool_call_exceeding_timeout_raises(monkeypatch):
    monkeypatch.setattr(
        registry_module, "get_settings", lambda: _settings(tool_timeout_seconds=0.02)
    )

    @allowlisted_tool("_unit_test_tool_timeout")
    async def _t():
        await asyncio.sleep(1)
        return "should never get here"

    with pytest.raises(ToolTimeoutError):
        await _t()


async def test_successful_call_emits_a_structured_audit_log():
    @allowlisted_tool("_unit_test_tool_audit_success")
    async def _t():
        return "ok"

    with structlog.testing.capture_logs() as logs:
        await _t()

    events = [entry for entry in logs if entry["event"] == "tool_call_succeeded"]
    assert len(events) == 1
    assert events[0]["tool"] == "_unit_test_tool_audit_success"
    assert events[0]["outcome"] == "success"
    assert "duration_seconds" in events[0]


async def test_failed_call_emits_a_structured_audit_log_and_still_reraises():
    @allowlisted_tool("_unit_test_tool_audit_failure")
    async def _t():
        raise ValueError("boom")

    with structlog.testing.capture_logs() as logs:
        with pytest.raises(ValueError, match="boom"):
            await _t()

    events = [entry for entry in logs if entry["event"] == "tool_call_failed"]
    assert len(events) == 1
    assert events[0]["outcome"] == "error"
