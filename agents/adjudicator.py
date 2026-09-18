from pydantic import BaseModel

from agents.base import summarize_or_fallback
from agents.models import InvestigatorFinding
from core.llm import LLMProvider
from evidence.models import Evidence, SourceType
from hypotheses.models import Hypothesis
from orchestration.routing import needs_human_review

_SYSTEM_PROMPT = (
    "You are the Adjudicator in an incident investigation system. Given "
    "the selected hypothesis and its evidence, write a 2-4 sentence "
    "reasoning summary explaining why it was selected. Base every claim "
    "strictly on the evidence given — never invent facts not present in "
    "it, and never claim higher certainty than the stated confidence "
    "supports."
)


class AdjudicationResult(BaseModel):
    """spec §18's Adjudicator output shape — the closest thing this phase
    has to spec §21's RCA (the fully formatted report with a timeline,
    uncertainty section, etc. is Phase 7's UI layer, built on top of
    this)."""

    selected_hypothesis: str | None
    confidence: float
    reasoning_summary: str
    supporting_evidence: list[Evidence]
    contradicting_evidence: list[Evidence]
    recommended_action: str
    needs_human_review: bool


def corroborating_knowledge(description: str, knowledge_evidence: list[Evidence]) -> list[Evidence]:
    """Which knowledge-base evidence textually relates to a hypothesis.

    Deliberately simple (shared-keyword overlap, words > 4 chars), but
    requires at least two matching keywords (or all of them, if only one
    qualifies) rather than any single one — a single shared word like
    "connection" appears in nearly every DB-adjacent document in this
    knowledge base and matched everything, burying the genuinely relevant
    runbook under two irrelevant ones. Public — also used by
    evaluation/baselines.py's single-agent baseline, which needs the same
    "does a runbook back this up" logic without a Hypothesis Manager
    around it.
    """
    keywords = {w.strip("().,;:\"'") for w in description.lower().split()}
    keywords = {w for w in keywords if len(w) > 4}
    if not keywords:
        return []
    required = min(2, len(keywords))
    return [
        e
        for e in knowledge_evidence
        if sum(1 for k in keywords if k in e.content.lower()) >= required
    ]


def recommend_action(evidence: list[Evidence]) -> str:
    """Cites the first matching runbook in `evidence`, if any — never a
    fabricated remediation step (spec §4.3). Public for the same reason
    as corroborating_knowledge above."""
    for e in evidence:
        if e.source_type == SourceType.RUNBOOK:
            return f"See runbook '{e.source}' for remediation steps."
    return "No matching runbook found — escalate to human review for remediation guidance."


async def adjudicate(
    hypotheses: list[Hypothesis],
    knowledge_finding: InvestigatorFinding,
    llm: LLMProvider | None = None,
) -> AdjudicationResult:
    """spec §18: selects the best-supported hypothesis (already sorted by
    hypotheses/manager.py) and produces the final adjudicated result,
    gated by confidence (spec §19-20 — see orchestration/routing.py)."""
    if not hypotheses:
        return AdjudicationResult(
            selected_hypothesis=None,
            confidence=0.0,
            reasoning_summary="No hypotheses were generated from the available evidence.",
            supporting_evidence=[],
            contradicting_evidence=[],
            recommended_action="Insufficient evidence to draw a conclusion — investigate further.",
            needs_human_review=True,
        )

    best = hypotheses[0]
    knowledge_corroboration = corroborating_knowledge(best.description, knowledge_finding.evidence)
    supporting_evidence = best.supporting_evidence + knowledge_corroboration

    fallback = (
        f"{best.description} is the most likely explanation, based on "
        f"{len(best.supporting_evidence)} supporting evidence item(s) across "
        f"{best.source_diversity} source type(s) (confidence {best.confidence:.0%})."
    )
    if best.contradicting_evidence:
        fallback += (
            f" {len(best.contradicting_evidence)} contradicting evidence item(s) were found."
        )
    if len(hypotheses) > 1:
        runner_up = hypotheses[1]
        fallback += (
            f" Next best candidate: '{runner_up.description}' "
            f"(confidence {runner_up.confidence:.0%})."
        )

    prompt = (
        f"Selected hypothesis: {best.description}\n"
        f"Confidence: {best.confidence:.2f}\n"
        "Supporting evidence:\n"
        + "\n".join(f"- {e.content}" for e in supporting_evidence)
        + "\nContradicting evidence:\n"
        + ("\n".join(f"- {e.content}" for e in best.contradicting_evidence) or "(none)")
    )
    reasoning_summary = await summarize_or_fallback(
        llm, prompt=prompt, system=_SYSTEM_PROMPT, fallback=fallback
    )

    return AdjudicationResult(
        selected_hypothesis=best.description,
        confidence=best.confidence,
        reasoning_summary=reasoning_summary,
        supporting_evidence=supporting_evidence,
        contradicting_evidence=best.contradicting_evidence,
        recommended_action=recommend_action(supporting_evidence),
        needs_human_review=needs_human_review(best.confidence),
    )
