from agents.adjudicator import AdjudicationResult, corroborating_knowledge, recommend_action
from agents.base import hypotheses_from_content
from agents.models import HypothesisSignal
from core.llm import LLMProvider, LLMUnavailableError
from evidence.models import Evidence
from tools.deployments import get_recent_deployments
from tools.incidents import get_incident
from tools.knowledge import search_knowledge
from tools.logs import search_logs
from tools.metrics import detect_anomaly, known_anomaly_metrics, query_metrics

_DIRECT_LLM_SYSTEM_PROMPT = (
    "You are investigating a production incident. State the single most "
    "likely root cause in one short phrase. You have no logs, metrics, or "
    "other evidence — only this summary."
)


async def direct_llm_investigate(incident_id: str, llm: LLMProvider | None) -> AdjudicationResult:
    """spec §27 Baseline A: the incident's public summary straight to an
    LLM, no tools, zero evidence. This baseline exists to demonstrate why
    that's not enough, not to perform well — with no evidence to ground a
    confidence score in, confidence is structurally fixed at 0.0 (spec
    §16: never let the LLM assign its own confidence), which correctly
    forces needs_human_review=True regardless of what the LLM says.
    """
    incident = await get_incident(incident_id)

    if llm is None:
        return AdjudicationResult(
            selected_hypothesis=None,
            confidence=0.0,
            reasoning_summary=(
                "No LLM configured — this baseline has no other mechanism to produce a hypothesis."
            ),
            supporting_evidence=[],
            contradicting_evidence=[],
            recommended_action="N/A — this baseline requires a reachable LLM.",
            needs_human_review=True,
        )

    prompt = (
        f"Incident: {incident.description}\n"
        f"Service: {incident.service}\n"
        f"Severity: {incident.severity}\n"
        "What is the most likely root cause?"
    )
    try:
        answer = await llm.generate(prompt, system=_DIRECT_LLM_SYSTEM_PROMPT)
    except LLMUnavailableError as exc:
        return AdjudicationResult(
            selected_hypothesis=None,
            confidence=0.0,
            reasoning_summary=f"LLM unavailable: {exc}",
            supporting_evidence=[],
            contradicting_evidence=[],
            recommended_action="N/A — this baseline requires a reachable LLM.",
            needs_human_review=True,
        )

    return AdjudicationResult(
        selected_hypothesis=answer.strip(),
        confidence=0.0,
        reasoning_summary=answer,
        supporting_evidence=[],
        contradicting_evidence=[],
        recommended_action="N/A — no evidence was gathered to base a remediation on.",
        needs_human_review=True,
    )


async def single_agent_investigate(
    incident_id: str, llm: LLMProvider | None = None
) -> AdjudicationResult:
    """spec §27 Baseline B: one agent, every tool, no Hypothesis Manager.
    Reuses the same keyword-pattern table and anomaly thresholds the real
    agents use (so it isn't a strawman with worse *data*), but picks
    whichever single signal has the most raw supporting evidence — no
    cross-source merging (DDR-013), no contradiction detection, no
    temporal/diversity weighting. Confidence is a single crude ratio, not
    hypotheses/scoring.py's formula. This is what "multi-agent" is being
    measured against.
    """
    logs_evidence = await search_logs(incident_id)
    metrics_evidence = await query_metrics(incident_id)
    deploy_evidence = await get_recent_deployments(incident_id)
    knowledge_evidence = await search_knowledge(incident_id)

    signals: list[HypothesisSignal] = hypotheses_from_content(logs_evidence + deploy_evidence)
    for metric_name in known_anomaly_metrics():
        anomalies = await detect_anomaly(incident_id, metric_name)
        if anomalies:
            signals.append(
                HypothesisSignal(
                    hypothesis=f"{metric_name} anomaly",
                    evidence_ids=[e.evidence_id for e in anomalies],
                )
            )

    if not signals:
        return AdjudicationResult(
            selected_hypothesis=None,
            confidence=0.0,
            reasoning_summary="No evidence matched any known pattern or anomaly threshold.",
            supporting_evidence=[],
            contradicting_evidence=[],
            recommended_action="Insufficient evidence to draw a conclusion — investigate further.",
            needs_human_review=True,
        )

    best = max(signals, key=lambda s: len(s.evidence_ids))
    evidence_by_id: dict[str, Evidence] = {
        e.evidence_id: e for e in logs_evidence + metrics_evidence + deploy_evidence
    }
    supporting = [evidence_by_id[eid] for eid in best.evidence_ids if eid in evidence_by_id]
    supporting += corroborating_knowledge(best.hypothesis, knowledge_evidence)

    confidence = min(1.0, len(supporting) / 5)

    return AdjudicationResult(
        selected_hypothesis=best.hypothesis,
        confidence=confidence,
        reasoning_summary=(
            f"{best.hypothesis}: {len(supporting)} supporting evidence item(s) "
            f"(naive single-agent scoring, confidence {confidence:.0%})."
        ),
        supporting_evidence=supporting,
        contradicting_evidence=[],  # this baseline has no contradiction detection at all
        recommended_action=recommend_action(supporting),
        needs_human_review=confidence < 0.90,
    )
