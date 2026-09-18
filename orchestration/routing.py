from enum import StrEnum

from core.config import Settings, get_settings


class ConfidenceTier(StrEnum):
    """spec §19's confidence gate tiers."""

    STRONG = "strong"  # >= confidence_strong_threshold: confident conclusion
    REVIEW = "review"  # >= confidence_review_threshold: conclusion + human review
    INSUFFICIENT = "insufficient"  # below that: insufficient evidence


def gate_confidence(confidence: float, settings: Settings | None = None) -> ConfidenceTier:
    settings = settings or get_settings()
    if confidence >= settings.confidence_strong_threshold:
        return ConfidenceTier.STRONG
    if confidence >= settings.confidence_review_threshold:
        return ConfidenceTier.REVIEW
    return ConfidenceTier.INSUFFICIENT


def needs_human_review(confidence: float, settings: Settings | None = None) -> bool:
    """spec §20: anything short of a strong, confident conclusion is
    escalated for human review — that includes "insufficient evidence",
    which is itself a valid, non-error outcome (spec §4.4)."""
    return gate_confidence(confidence, settings) != ConfidenceTier.STRONG
