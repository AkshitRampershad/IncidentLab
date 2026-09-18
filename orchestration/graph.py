import argparse
import asyncio

from langgraph.graph import END, StateGraph

from agents import code, knowledge, logs, metrics, triage
from agents.adjudicator import adjudicate
from core.llm import get_llm_provider
from hypotheses.manager import build_hypotheses
from orchestration.state import InvestigationState


async def _triage_node(state: InvestigationState) -> dict:
    finding = await triage.investigate(state["incident_id"], llm=state.get("llm"))
    return {"triage": finding}


async def _logs_node(state: InvestigationState) -> dict:
    finding = await logs.investigate(state["incident_id"], llm=state.get("llm"))
    return {"logs_finding": finding}


async def _metrics_node(state: InvestigationState) -> dict:
    finding = await metrics.investigate(state["incident_id"], llm=state.get("llm"))
    return {"metrics_finding": finding}


async def _code_node(state: InvestigationState) -> dict:
    finding = await code.investigate(state["incident_id"], llm=state.get("llm"))
    return {"code_finding": finding}


async def _knowledge_node(state: InvestigationState) -> dict:
    finding = await knowledge.investigate(state["incident_id"], llm=state.get("llm"))
    return {"knowledge_finding": finding}


def _hypotheses_node(state: InvestigationState) -> dict:
    hypotheses = build_hypotheses(
        state["logs_finding"], state["metrics_finding"], state["code_finding"]
    )
    return {"hypotheses": hypotheses}


async def _adjudicate_node(state: InvestigationState) -> dict:
    result = await adjudicate(state["hypotheses"], state["knowledge_finding"], llm=state.get("llm"))
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
    words for what Phase 5 must achieve)."""
    app = build_graph()
    return await app.ainvoke({"incident_id": incident_id, "llm": llm})


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
