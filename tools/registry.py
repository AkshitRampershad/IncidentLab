import time
from asyncio import wait_for
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from functools import wraps
from typing import ParamSpec, TypeVar

import structlog

from core.config import get_settings
from core.telemetry import get_tracer

logger = structlog.get_logger()
tracer = get_tracer("incidentlab.tools")

P = ParamSpec("P")
R = TypeVar("R")


class ToolNotAllowed(RuntimeError):
    """Raised when something tries to invoke a tool name that was never
    registered through @allowlisted_tool (spec §38's tool permission
    model: agents may only call tools explicitly registered here, not an
    arbitrary function)."""


class ToolTimeoutError(RuntimeError):
    """Raised when a single tool call exceeds Settings.tool_timeout_seconds."""


class ToolBudgetExceededError(RuntimeError):
    """Raised when one investigation's tool calls exceed
    Settings.max_tool_calls_per_investigation — a circuit breaker against a
    stuck retry loop or a future adversarial/buggy agent, not something a
    healthy investigation should ever hit."""


_ALLOWED_TOOLS: set[str] = set()
_REGISTERED_TOOLS: dict[str, Callable[..., Awaitable]] = {}

# A single-element list used as a mutable counter cell. LangGraph's
# investigator nodes run as concurrent asyncio Tasks created from the same
# parent context (graph.ainvoke's fan-out); asyncio.Task copies the
# ContextVar *mapping* at creation time but each entry's *value* is shared
# by reference, so every node sees and mutates the same list instance here
# — a plain `int` would not work, since each Task would get its own copy
# the moment it tried to rebind the ContextVar to a new int.
_call_count: ContextVar[list[int] | None] = ContextVar("tool_call_count", default=None)


def reset_tool_budget() -> None:
    """Call once at the start of an investigation (orchestration.graph.
    investigate) to zero the shared per-investigation call counter. Tests
    that call a tool function directly, outside of an investigation, never
    call this — _consume_budget then has nothing to enforce against, which
    is intentional (a unit test isn't "an investigation")."""
    _call_count.set([0])


def current_tool_call_count() -> int:
    counter = _call_count.get()
    return counter[0] if counter is not None else 0


def _consume_budget() -> None:
    counter = _call_count.get()
    if counter is None:
        return
    counter[0] += 1
    limit = get_settings().max_tool_calls_per_investigation
    if counter[0] > limit:
        raise ToolBudgetExceededError(
            f"Investigation exceeded its tool-call budget of {limit} calls"
        )


def allowlisted_tool(name: str) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """spec §38's tool permission layer, applied as a decorator on every
    function an agent is allowed to call as a "tool": the decorator itself
    IS the allowlist (a function it never wraps cannot be invoked as a
    tool the way agents do), plus a per-call timeout (spec §40), a shared
    per-investigation call budget (spec §40), and structured audit logging
    of every call — name, duration, outcome (spec §39's audit trail and
    §42's observability, both satisfied by the same log line rather than
    two separate mechanisms).
    """
    _ALLOWED_TOOLS.add(name)

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            incident_id = kwargs.get("incident_id") or (args[0] if args else None)
            with tracer.start_as_current_span(f"tool.{name}") as span:
                span.set_attribute("incidentlab.tool", name)
                if incident_id is not None:
                    span.set_attribute("incidentlab.incident_id", str(incident_id))

                _consume_budget()
                timeout = get_settings().tool_timeout_seconds
                start = time.monotonic()
                try:
                    result = await wait_for(func(*args, **kwargs), timeout=timeout)
                except TimeoutError as exc:
                    duration = time.monotonic() - start
                    span.set_attribute("incidentlab.outcome", "timeout")
                    span.set_attribute("incidentlab.duration_seconds", duration)
                    span.record_exception(exc)
                    logger.warning(
                        "tool_call_failed",
                        tool=name,
                        duration_seconds=round(duration, 3),
                        outcome="timeout",
                    )
                    raise ToolTimeoutError(
                        f"Tool '{name}' did not complete within {timeout}s"
                    ) from exc
                except Exception as exc:
                    duration = time.monotonic() - start
                    span.set_attribute("incidentlab.outcome", "error")
                    span.set_attribute("incidentlab.duration_seconds", duration)
                    span.record_exception(exc)
                    logger.warning(
                        "tool_call_failed",
                        tool=name,
                        duration_seconds=round(duration, 3),
                        outcome="error",
                    )
                    raise
                else:
                    duration = time.monotonic() - start
                    span.set_attribute("incidentlab.outcome", "success")
                    span.set_attribute("incidentlab.duration_seconds", duration)
                    logger.info(
                        "tool_call_succeeded",
                        tool=name,
                        duration_seconds=round(duration, 3),
                        outcome="success",
                    )
                    return result

        wrapper.__tool_name__ = name  # type: ignore[attr-defined]
        _REGISTERED_TOOLS[name] = wrapper
        return wrapper

    return decorator


def allowed_tools() -> list[str]:
    """Every tool name currently registered via @allowlisted_tool — the
    live allowlist, not a hand-maintained list that can drift from it."""
    return sorted(_ALLOWED_TOOLS)


async def call_tool(name: str, *args, **kwargs):
    """Invoke a registered tool by name — the shape a future LLM-driven
    tool-calling loop would use (this project's agents currently call tool
    functions directly via Python imports, since the LLM here is never
    the one choosing which tool to call; this is the enforced boundary
    that path would have to go through). Raises ToolNotAllowed for any
    name that was never registered via @allowlisted_tool, making spec
    §38's allowlist an actual enforced check rather than just an implicit
    side effect of which functions happen to carry the decorator.
    """
    if name not in _REGISTERED_TOOLS:
        raise ToolNotAllowed(f"'{name}' is not a registered tool")
    return await _REGISTERED_TOOLS[name](*args, **kwargs)
