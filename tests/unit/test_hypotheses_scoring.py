from hypotheses.scoring import score_confidence


def test_no_supporting_evidence_is_zero_confidence():
    assert (
        score_confidence(
            supporting_count=0, source_diversity=0, temporal_alignment=0, contradiction_count=0
        )
        == 0.0
    )


def test_full_coverage_diversity_and_temporal_alignment_scores_near_one():
    confidence = score_confidence(
        supporting_count=5, source_diversity=3, temporal_alignment=1.0, contradiction_count=0
    )
    assert confidence == 1.0


def test_partial_coverage_and_diversity_score_proportionally():
    confidence = score_confidence(
        supporting_count=1, source_diversity=1, temporal_alignment=1.0, contradiction_count=0
    )
    # evidence_coverage=0.2, diversity=0.333..., temporal=1.0
    # raw = 0.5*0.2 + 0.2*(1/3) + 0.3*1.0 = 0.1 + 0.0667 + 0.3 = 0.4667
    assert 0.46 < confidence < 0.47


def test_contradictions_reduce_confidence():
    without = score_confidence(
        supporting_count=5, source_diversity=3, temporal_alignment=1.0, contradiction_count=0
    )
    with_one = score_confidence(
        supporting_count=5, source_diversity=3, temporal_alignment=1.0, contradiction_count=1
    )
    assert with_one == without - 0.3


def test_confidence_never_goes_below_zero():
    confidence = score_confidence(
        supporting_count=1, source_diversity=1, temporal_alignment=0.2, contradiction_count=10
    )
    assert confidence == 0.0
