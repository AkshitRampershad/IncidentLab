from pydantic import BaseModel

from agents.adjudicator import AdjudicationResult
from evaluation.ground_truth import GroundTruthLookup


class Trial(BaseModel):
    """One (incident, architecture) run's result plus what it should have
    found — the only place a scored result and ground truth sit next to
    each other in this codebase."""

    incident_id: str
    architecture: str
    ground_truth: GroundTruthLookup
    result: AdjudicationResult
    latency_seconds: float


def is_correct(trial: Trial) -> bool:
    """spec §27's Root Cause Accuracy, per trial."""
    return trial.result.selected_hypothesis == trial.ground_truth.correct_hypothesis


def evidence_recall(trial: Trial) -> float:
    """Of the incident's real (non-distractor) evidence, what fraction did
    the selected hypothesis's supporting evidence include?"""
    expected = trial.ground_truth.non_distractor_evidence_ids
    if not expected:
        return 0.0
    found = {e.evidence_id for e in trial.result.supporting_evidence}
    return len(found & expected) / len(expected)


def evidence_precision(trial: Trial) -> float:
    """Of the evidence the selected hypothesis actually cited, what
    fraction was genuinely non-distractor rather than noise it mistook
    for support?"""
    cited = {e.evidence_id for e in trial.result.supporting_evidence}
    if not cited:
        return 0.0
    return len(cited & trial.ground_truth.non_distractor_evidence_ids) / len(cited)


def is_unsupported_claim(trial: Trial) -> bool:
    """spec §27's Unsupported Claim Rate: a selected_hypothesis asserted
    with zero supporting evidence behind it."""
    return (
        trial.result.selected_hypothesis is not None and len(trial.result.supporting_evidence) == 0
    )


def is_false_confidence(trial: Trial, *, strong_threshold: float) -> bool:
    """spec §27's False Confidence Rate: confidently wrong."""
    return trial.result.confidence >= strong_threshold and not is_correct(trial)


class AggregateMetrics(BaseModel):
    architecture: str
    n: int
    root_cause_accuracy: float
    evidence_recall: float
    evidence_precision: float
    unsupported_claim_rate: float
    false_confidence_rate: float
    human_escalation_rate: float
    avg_latency_seconds: float


def aggregate(
    architecture: str, trials: list[Trial], *, strong_threshold: float
) -> AggregateMetrics:
    n = len(trials)
    if n == 0:
        return AggregateMetrics(
            architecture=architecture,
            n=0,
            root_cause_accuracy=0.0,
            evidence_recall=0.0,
            evidence_precision=0.0,
            unsupported_claim_rate=0.0,
            false_confidence_rate=0.0,
            human_escalation_rate=0.0,
            avg_latency_seconds=0.0,
        )
    return AggregateMetrics(
        architecture=architecture,
        n=n,
        root_cause_accuracy=sum(is_correct(t) for t in trials) / n,
        evidence_recall=sum(evidence_recall(t) for t in trials) / n,
        evidence_precision=sum(evidence_precision(t) for t in trials) / n,
        unsupported_claim_rate=sum(is_unsupported_claim(t) for t in trials) / n,
        false_confidence_rate=sum(
            is_false_confidence(t, strong_threshold=strong_threshold) for t in trials
        )
        / n,
        human_escalation_rate=sum(t.result.needs_human_review for t in trials) / n,
        avg_latency_seconds=sum(t.latency_seconds for t in trials) / n,
    )
