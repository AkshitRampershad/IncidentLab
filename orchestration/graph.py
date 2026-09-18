import argparse
import asyncio
from datetime import UTC, datetime

import structlog
from langgraph.graph import END, StateGraph

from agents import code, knowledge, logs, metrics, triage
from agents.adjudicator import AdjudicationResult, adjudicate
from agents.models import InvestigatorFinding, TimeWindow, TriageFinding
from core.config import get_settings
from core.llm import get_llm_provider
from core.telemetry import get_tracer
from hypotheses.manager import build_hypotheses
from orchestration.state import InvestigationState
from tools.registry import reset_tool_budget

logger = structlog.get_logger()
tracer = get_tracer("incidentlab.orchestration")


class InvestigationTimeoutError(RuntimeError):
    """Raised when a whole investigation exceeds
    Settings.investigation_timeout_seconds — the outer ceiling on top of
    each individual tool call's own timeout (tools/registry.py), for the
    case where many small, individually-fine tool calls still add up to an
    unacceptably slow investigation overall."""


def _degraded_investigator_finding(agent_name: str, reason: str) -> InvestigatorFinding:
    return InvestigatorFinding(
        agent_name=agent_name,
        findings=[],
        evidence=[],
        hypotheses_supported=[],
        summary=f"Agent unavailable: {reason}",
        degraded=True,
    )


def _degraded_triage_finding(reason: str) -> TriageFinding:
    now = datetime.now(UTC)
    return TriageFinding(
        affected_services=[],
        time_window=TimeWindow(start=now, end=now),
        investigation_targets=[],
        initial_hypotheses=[],
        summary=f"Agent unavailable: {reason}",
        degraded=True,
    )


async def _run_investigator(
    agent_name: str, module, state: InvestigationState
) -> InvestigatorFinding:
    """spec §43's own worked example: "If Log Agent fails ... continue
    investigation with: Metrics, Code, Knowledge." One agent's failure —
    a tool timeout, its call budget exhausted, a DB error, anything —
    must never crash the whole graph; it degrades to an empty,
    clearly-labeled finding instead (agents/models.py's `degraded` flag),
    and the rest of the investigation proceeds on real evidence from
    whichever agents did succeed."""
    with tracer.start_as_current_span(f"agent.{agent_name}") as span:
        span.set_attribute("incidentlab.agent_name", agent_name)
        try:
            finding = await module.investigate(state["incident_id"], llm=state.get("llm"))
            span.set_attribute("incidentlab.degraded", False)
            return finding
        except ValueError:
            # An incident_id that doesn't exist at all isn't a
            # degraded-but-continuable agent failure — every agent would
            # fail identically and there's no investigation to run at all.
            # investigate() below checks this upfront so it's not expected
            # to reach here in practice, but re-raising (rather than
            # degrading) keeps that contract true even if it does.
            raise
        except Exception as exc:
            span.record_exception(exc)
            span.set_attribute("incidentlab.degraded", True)
            logger.warning("agent_failed", agent=agent_name, error=str(exc))
            return _degraded_investigator_finding(agent_name, str(exc))


async def _triage_node(state: InvestigationState) -> dict:
    with tracer.start_as_current_span("agent.triage") as span:
        span.set_attribute("incidentlab.agent_name", "triage")
        try:
            finding = await triage.investigate(state["incident_id"], llm=state.get("llm"))
            span.set_attribute("incidentlab.degraded", False)
        except ValueError:
            raise  # see _run_investigator's matching comment
        except Exception as exc:
            span.record_exception(exc)
            span.set_attribute("incidentlab.degraded", True)
            logger.warning("agent_failed", agent="triage", error=str(exc))
            finding = _degraded_triage_finding(str(exc))
    return {"triage": finding}


async def _logs_node(state: InvestigationState) -> dict:
    return {"logs_finding": await _run_investigator("logs", logs, state)}


async def _metrics_node(state: InvestigationState) -> dict:
    return {"metrics_finding": await _run_investigator("metrics", metrics, state)}


async def _code_node(state: InvestigationState) -> dict:
    return {"code_finding": await _run_investigator("code", code, state)}


async def _knowledge_node(state: InvestigationState) -> dict:
    return {"knowledge_finding": await _run_investigator("knowledge", knowledge, state)}


def _hypotheses_node(state: InvestigationState) -> dict:
    hypotheses = build_hypotheses(
        state["logs_finding"], state["metrics_finding"], state["code_finding"]
    )
    return {"hypotheses": hypotheses}


async def _adjudicate_node(state: InvestigationState) -> dict:
    with tracer.start_as_current_span("agent.adjudicate") as span:
        try:
            result = await adjudicate(
                state["hypotheses"], state["knowledge_finding"], llm=state.get("llm")
            )
            span.set_attribute("incidentlab.degraded", False)
        except Exception as exc:
            span.record_exception(exc)
            span.set_attribute("incidentlab.degraded", True)
            logger.warning("agent_failed", agent="adjudicate", error=str(exc))
            result = AdjudicationResult(
                selected_hypothesis=None,
                confidence=0.0,
                reasoning_summary=f"Adjudication unavailable: {exc}",
                supporting_evidence=[],
                contradicting_evidence=[],
                recommended_action=(
                    "Insufficient evidence to draw a conclusion — investigate further."
                ),
                needs_human_review=True,
            )
    return {"adjudication": result}


def build_graph():
    """spec §5's orchestrator: Triage fans out to the four investigators in
    parallel (they share no state keys, so LangGraph needs no reducer),
    fans back in to the Hypothesis Manager once all four finish, then
    Contradiction Detection + Confidence Gating happen inside the
    Adjudicator node (hypotheses/manager.py already runs contradiction
    detection per-hypothesis — see its docstring) before producing the
    final result."""
    graph = StateGraph(InvestigationState)
    graph.add_node("triage", _triage_node)
    graph.add_node("logs", _logs_node)
    graph.add_node("metrics", _metrics_node)
    graph.add_node("code", _code_node)
    graph.add_node("knowledge", _knowledge_node)
    graph.add_node("hypotheses", _hypotheses_node)
    graph.add_node("adjudicate", _adjudicate_node)

    graph.set_entry_point("triage")
    for investigator in ("logs", "metrics", "code", "knowledge"):
        graph.add_edge("triage", investigator)
        graph.add_edge(investigator, "hypotheses")
    graph.add_edge("hypotheses", "adjudicate")
    graph.add_edge("adjudicate", END)

    return graph.compile()


async def investigate(incident_id: str, llm=None) -> InvestigationState:
    """incident → agents → hypotheses → evidence → RCA (spec §5's own
    words for what Phase 5 must achieve).

    Phase 8 additions: resets the shared tool-call budget so it counts
    only this investigation's calls (tools/registry.py), and enforces an
    overall wall-clock ceiling (Settings.investigation_timeout_seconds) on
    top of each individual tool call's own timeout, for the case where
    many small, individually-fine tool calls still add up to an
    unacceptably slow investigation.
    """
    reset_tool_budget()
    settings = get_settings()
    app = build_graph()
    with tracer.start_as_current_span("investigation") as span:
        span.set_attribute("incidentlab.incident_id", incident_id)
        try:
            result = await asyncio.wait_for(
                app.ainvoke({"incident_id": incident_id, "llm": llm}),
                timeout=settings.investigation_timeout_seconds,
            )
        except TimeoutError as exc:
            span.record_exception(exc)
            span.set_attribute("incidentlab.timed_out", True)
            raise InvestigationTimeoutError(
                f"Investigation of '{incident_id}' did not complete within "
                f"{settings.investigation_timeout_seconds}s"
            ) from exc
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a full investigation against an incident.")
    parser.add_argument("--incident", required=True, help="Incident ID, e.g. INC-0001")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM summarization (use deterministic fallbacks only)",
    )
    args = parser.parse_args()

    llm = None if args.no_llm else get_llm_provider()

    final_state = asyncio.run(investigate(args.incident, llm=llm))
    adjudication = final_state["adjudication"]

    print(f"=== Investigation of {args.incident} ===")
    print(f"Selected hypothesis: {adjudication.selected_hypothesis}")
    print(f"Confidence: {adjudication.confidence:.0%}")
    print(f"Needs human review: {adjudication.needs_human_review}")
    print(f"Recommended action: {adjudication.recommended_action}")
    if adjudication.contradicting_evidence:
        print(f"Contradicting evidence: {len(adjudication.contradicting_evidence)} item(s)")
    else:
        print("Contradicting evidence: none detected")
    print()
    print("Reasoning:")
    print(adjudication.reasoning_summary)


if __name__ == "__main__":
    main()
