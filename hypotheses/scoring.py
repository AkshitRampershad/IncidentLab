# spec §16's deterministic confidence formula. Weights and normalization
# constants below are an explicit *experimental baseline* — the spec's own
# words: "do not claim the formula is scientifically optimal." What matters
# is that it's reproducible and inspectable, never an LLM's unconstrained
# guess (spec §4.1, §16).
_EVIDENCE_WEIGHT = 0.5
_DIVERSITY_WEIGHT = 0.2
_TEMPORAL_WEIGHT = 0.3
_CONTRADICTION_PENALTY_PER_ITEM = 0.3

# "Full credit" normalizers: 5+ supporting evidence items, or 3+ distinct
# source types, are treated as maximal coverage/diversity. Both are
# heuristic thresholds, not derived from any calibration data.
_FULL_COVERAGE_EVIDENCE_COUNT = 5
_FULL_DIVERSITY_SOURCE_COUNT = 3


def score_confidence(
    *,
    supporting_count: int,
    source_diversity: int,
    temporal_alignment: float,
    contradiction_count: int,
) -> float:
    """confidence = weighted evidence support + source diversity +
    temporal alignment - contradiction penalty (spec §16), clamped to
    [0, 1]."""
    if supporting_count == 0:
        return 0.0

    evidence_coverage = min(1.0, supporting_count / _FULL_COVERAGE_EVIDENCE_COUNT)
    diversity_score = min(1.0, source_diversity / _FULL_DIVERSITY_SOURCE_COUNT)

    raw = (
        _EVIDENCE_WEIGHT * evidence_coverage
        + _DIVERSITY_WEIGHT * diversity_score
        + _TEMPORAL_WEIGHT * temporal_alignment
    )
    penalty = _CONTRADICTION_PENALTY_PER_ITEM * contradiction_count
    return max(0.0, min(1.0, raw - penalty))
