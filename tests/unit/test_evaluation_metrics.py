from datetime import UTC, datetime

from agents.adjudicator import AdjudicationResult
from evaluation.ground_truth import GroundTruthLookup
from evaluation.metrics import (
    Trial,
    aggregate,
    evidence_precision,
    evidence_recall,
    is_correct,
    is_false_confidence,
    is_unsupported_claim,
)
from evidence.models import Evidence, Provenance, SourceType

NOW = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


def _evidence(evidence_id: str) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_type=SourceType.LOG,
        source="checkout",
        timestamp=NOW,
        content="x",
        relevance=1.0,
        provenance=Provenance(table="t", row_id="1", incident_id="INC-0001", retrieved_at=NOW),
    )


def _ground_truth(correct_hypothesis: str, non_distractor_ids: set[str]) -> GroundTruthLookup:
    return GroundTruthLookup(
        incident_id="INC-0001",
        scenario_id="db_connection_pool",
        root_cause="database_connection_pool_exhaustion",
        correct_hypothesis=correct_hypothesis,
        non_distractor_evidence_ids=non_distractor_ids,
    )


def _result(selected: str | None, confidence: float, evidence_ids: list[str]) -> AdjudicationResult:
    return AdjudicationResult(
        selected_hypothesis=selected,
        confidence=confidence,
        reasoning_summary="",
        supporting_evidence=[_evidence(eid) for eid in evidence_ids],
        contradicting_evidence=[],
        recommended_action="",
        needs_human_review=confidence < 0.9,
    )


def _trial(selected, confidence, evidence_ids, correct_hypothesis, non_distractor_ids) -> Trial:
    return Trial(
        incident_id="INC-0001",
        architecture="multi_agent",
        ground_truth=_ground_truth(correct_hypothesis, non_distractor_ids),
        result=_result(selected, confidence, evidence_ids),
        latency_seconds=0.5,
    )


def test_is_correct_matches_exact_hypothesis_text():
    trial = _trial(
        "Connection pool exhaustion", 0.9, ["LOG-1"], "Connection pool exhaustion", {"LOG-1"}
    )
    assert is_correct(trial) is True

    wrong = _trial(
        "Cache layer (Redis) involvement", 0.9, ["LOG-1"], "Connection pool exhaustion", {"LOG-1"}
    )
    assert is_correct(wrong) is False

    no_answer = _trial(None, 0.0, [], "Connection pool exhaustion", {"LOG-1"})
    assert is_correct(no_answer) is False


def test_evidence_recall_and_precision():
    # cites LOG-1 (real) and LOG-2 (distractor); misses LOG-3 (real, uncited)
    trial = _trial(
        "Connection pool exhaustion",
        0.9,
        ["LOG-1", "LOG-2"],
        "Connection pool exhaustion",
        {"LOG-1", "LOG-3"},
    )
    assert evidence_recall(trial) == 0.5  # found 1 of 2 real evidence items
    assert evidence_precision(trial) == 0.5  # cited 2 items, only 1 was real


def test_evidence_recall_zero_when_no_real_evidence_exists():
    trial = _trial("X", 0.9, ["LOG-1"], "X", set())
    assert evidence_recall(trial) == 0.0


def test_evidence_precision_zero_when_nothing_cited():
    trial = _trial(None, 0.0, [], "X", {"LOG-1"})
    assert evidence_precision(trial) == 0.0


def test_unsupported_claim_is_a_selected_hypothesis_with_no_evidence():
    unsupported = _trial("Some guess", 0.5, [], "Connection pool exhaustion", {"LOG-1"})
    assert is_unsupported_claim(unsupported) is True

    supported = _trial("Some guess", 0.5, ["LOG-1"], "Connection pool exhaustion", {"LOG-1"})
    assert is_unsupported_claim(supported) is False

    no_claim = _trial(None, 0.0, [], "Connection pool exhaustion", {"LOG-1"})
    assert is_unsupported_claim(no_claim) is False


def test_false_confidence_is_high_confidence_and_wrong():
    confidently_wrong = _trial(
        "Wrong answer", 0.95, ["LOG-1"], "Connection pool exhaustion", {"LOG-1"}
    )
    assert is_false_confidence(confidently_wrong, strong_threshold=0.9) is True

    confidently_right = _trial(
        "Connection pool exhaustion", 0.95, ["LOG-1"], "Connection pool exhaustion", {"LOG-1"}
    )
    assert is_false_confidence(confidently_right, strong_threshold=0.9) is False

    unconfidently_wrong = _trial(
        "Wrong answer", 0.5, ["LOG-1"], "Connection pool exhaustion", {"LOG-1"}
    )
    assert is_false_confidence(unconfidently_wrong, strong_threshold=0.9) is False


def test_aggregate_over_multiple_trials():
    trials = [
        _trial(
            "Connection pool exhaustion", 0.95, ["LOG-1"], "Connection pool exhaustion", {"LOG-1"}
        ),
        _trial("Wrong", 0.5, [], "Connection pool exhaustion", {"LOG-1"}),
    ]
    result = aggregate("multi_agent", trials, strong_threshold=0.9)
    assert result.architecture == "multi_agent"
    assert result.n == 2
    assert result.root_cause_accuracy == 0.5
    assert result.human_escalation_rate == 0.5  # only the 0.5-confidence trial needs review


def test_aggregate_empty_dataset():
    result = aggregate("multi_agent", [], strong_threshold=0.9)
    assert result.n == 0
    assert result.root_cause_accuracy == 0.0
