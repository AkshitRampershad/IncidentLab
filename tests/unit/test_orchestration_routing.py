from core.config import Settings
from orchestration.routing import ConfidenceTier, gate_confidence, needs_human_review

_SETTINGS = Settings(confidence_strong_threshold=0.90, confidence_review_threshold=0.70)


def test_gate_boundaries():
    assert gate_confidence(0.90, _SETTINGS) == ConfidenceTier.STRONG
    assert gate_confidence(0.899, _SETTINGS) == ConfidenceTier.REVIEW
    assert gate_confidence(0.70, _SETTINGS) == ConfidenceTier.REVIEW
    assert gate_confidence(0.699, _SETTINGS) == ConfidenceTier.INSUFFICIENT


def test_needs_human_review_only_false_for_strong():
    assert needs_human_review(0.95, _SETTINGS) is False
    assert needs_human_review(0.80, _SETTINGS) is True
    assert needs_human_review(0.10, _SETTINGS) is True


def test_thresholds_are_configurable():
    lenient = Settings(confidence_strong_threshold=0.5, confidence_review_threshold=0.2)
    assert gate_confidence(0.6, lenient) == ConfidenceTier.STRONG
    assert needs_human_review(0.6, lenient) is False
