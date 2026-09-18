from agents.models import InvestigatorFinding
from hypotheses.contradiction import detect_contradictions
from hypotheses.models import Hypothesis
from hypotheses.scoring import score_confidence

# Groups hypothesis-signal texts from different agents that describe the
# same underlying root cause, so their evidence is merged into one
# multi-source Hypothesis instead of staying as separate, weaker,
# single-source ones — spec §15's "correlate evidence across sources".
# Deliberately small and specific to the one scenario that exists today
# (see agents/base.py's _HYPOTHESIS_PATTERNS) — extend both together as
# simulator/failure_injector/ grows more scenarios. Any signal text not
# listed here still becomes its own standalone hypothesis; nothing is
# silently dropped for being unmapped.
_CANONICAL_HYPOTHESES: dict[str, list[str]] = {
    "Connection pool exhaustion": [
        "Connection pool exhaustion",
        "db_connections_active anomaly",
    ],
    "Database or downstream connectivity issue": [
        "Database or downstream connectivity issue (connection timeouts)",
        "latency_p99_ms anomaly",
        "error_rate anomaly",
    ],
    "Cache layer (Redis) involvement": [
        "Cache layer (Redis) involvement",
        "cache_hit_rate anomaly",
    ],
}


def build_hypotheses(
    logs_finding: InvestigatorFinding,
    metrics_finding: InvestigatorFinding,
    code_finding: InvestigatorFinding,
) -> list[Hypothesis]:
    """spec §15's Hypothesis Manager: consolidates every investigator's
    hypotheses_supported into competing, evidence-backed Hypotheses,
    scored deterministically (hypotheses/scoring.py) after contradiction
    detection (hypotheses/contradiction.py). Sorted highest-confidence
    first.

    Only Logs/Metrics/Code feed this — Knowledge doesn't assert its own
    hypotheses (see agents/knowledge.py); its evidence corroborates the
    Adjudicator's already-selected winner instead (agents/adjudicator.py).
    """
    all_evidence_by_id = {
        e.evidence_id: e
        for finding in (logs_finding, metrics_finding, code_finding)
        for e in finding.evidence
    }
    all_signals = (
        logs_finding.hypotheses_supported
        + metrics_finding.hypotheses_supported
        + code_finding.hypotheses_supported
    )
    signals_by_text = {s.hypothesis: s for s in all_signals}

    grouped_evidence_ids: dict[str, list[str]] = {}
    consumed_texts: set[str] = set()
    for canonical, member_texts in _CANONICAL_HYPOTHESES.items():
        matched = [signals_by_text[t] for t in member_texts if t in signals_by_text]
        if not matched:
            continue
        grouped_evidence_ids[canonical] = [eid for s in matched for eid in s.evidence_ids]
        consumed_texts.update(s.hypothesis for s in matched)

    for s in all_signals:
        if s.hypothesis not in consumed_texts:
            grouped_evidence_ids.setdefault(s.hypothesis, []).extend(s.evidence_ids)

    hypotheses = []
    for i, (description, evidence_ids) in enumerate(grouped_evidence_ids.items(), start=1):
        supporting = [
            all_evidence_by_id[eid]
            for eid in dict.fromkeys(evidence_ids)
            if eid in all_evidence_by_id
        ]
        expected_signals = _CANONICAL_HYPOTHESES.get(description, [description])
        contradicting = detect_contradictions(expected_signals, metrics_finding)

        source_diversity = len({e.source_type for e in supporting})
        temporal_alignment = (
            sum(e.relevance for e in supporting) / len(supporting) if supporting else 0.0
        )
        confidence = score_confidence(
            supporting_count=len(supporting),
            source_diversity=source_diversity,
            temporal_alignment=temporal_alignment,
            contradiction_count=len(contradicting),
        )

        hypotheses.append(
            Hypothesis(
                hypothesis_id=f"H{i}",
                description=description,
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                source_diversity=source_diversity,
                temporal_alignment=temporal_alignment,
                confidence=confidence,
            )
        )

    return sorted(hypotheses, key=lambda h: h.confidence, reverse=True)
