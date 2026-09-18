from agents.base import summarize_or_fallback
from agents.models import HypothesisSignal, InvestigatorFinding
from core.llm import LLMProvider
from tools.knowledge import search_historical_incidents, search_knowledge

_SYSTEM_PROMPT = (
    "You are the Knowledge Investigator agent. Summarize which runbooks, "
    "architecture notes, or historical incidents are relevant, in 2-3 "
    "sentences. Base every claim strictly on the evidence given — never "
    "invent facts not present in it."
)


async def investigate(incident_id: str, llm: LLMProvider | None = None) -> InvestigatorFinding:
    """spec §14: search_knowledge() + search_historical_incidents() over
    the hand-authored knowledge/ corpus (keyword search — no Qdrant/
    embeddings yet, see docs/design-decisions.md). Runs unscoped by query
    (no cross-agent coordination exists until Phase 5's orchestrator) —
    fine at this corpus size, revisit once it's too big to search whole.
    """
    knowledge = await search_knowledge(incident_id)
    historical = await search_historical_incidents(incident_id)
    evidence = knowledge + historical

    findings = [f"Found {e.source_type.value} '{e.source}'" for e in evidence]
    if not findings:
        findings.append("No matching knowledge base entries found.")

    # Knowledge doesn't assert new root-cause hypotheses of its own — it
    # contextualizes ones the other agents raise. The Adjudicator (Phase 5)
    # is what ties this evidence back to the winning hypothesis.
    hypotheses_supported: list[HypothesisSignal] = []

    fallback = " ".join(findings)
    prompt = "Knowledge base matches:\n" + "\n".join(
        f"- {e.source}: {e.content[:300]}" for e in evidence
    )
    summary = await summarize_or_fallback(
        llm, prompt=prompt, system=_SYSTEM_PROMPT, fallback=fallback
    )

    return InvestigatorFinding(
        agent_name="knowledge",
        findings=findings,
        evidence=evidence,
        hypotheses_supported=hypotheses_supported,
        summary=summary,
    )
