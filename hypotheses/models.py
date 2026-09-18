from pydantic import BaseModel

from evidence.models import Evidence


class Hypothesis(BaseModel):
    """spec §15: a candidate root cause, with the evidence for and against
    it and a deterministically-computed confidence (spec §16, §18)."""

    hypothesis_id: str
    description: str
    supporting_evidence: list[Evidence]
    contradicting_evidence: list[Evidence]
    source_diversity: int
    temporal_alignment: float
    confidence: float
