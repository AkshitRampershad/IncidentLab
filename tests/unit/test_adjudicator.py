from datetime import UTC, datetime

from agents.adjudicator import adjudicate
from agents.models import InvestigatorFinding
from core.llm.base import LLMProvider
from evidence.models import Evidence, Provenance, SourceType
from hypotheses.models import Hypothesis

NOW = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


def _evidence(
    evidence_id: str, source_type: SourceType, content: str, source: str = "checkout"
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_type=source_type,
        source=source,
        timestamp=NOW,
        content=content,
        relevance=1.0,
        provenance=Provenance(table="t", row_id="1", incident_id="INC-0001", retrieved_at=NOW),
    )


def _hypothesis(description: str, confidence: float, *, contradicting=None) -> Hypothesis:
    return Hypothesis(
        hypothesis_id="H1",
        description=description,
        supporting_evidence=[_evidence("LOG-1", SourceType.LOG, "supporting fact")],
        contradicting_evidence=contradicting or [],
        source_diversity=1,
        temporal_alignment=1.0,
        confidence=confidence,
    )


def _knowledge_finding(evidence: list[Evidence]) -> InvestigatorFinding:
    return InvestigatorFinding(
        agent_name="knowledge", findings=[], evidence=evidence, hypotheses_supported=[], summary=""
    )


class FakeLLM(LLMProvider):
    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        return "fake reasoning"


async def test_no_hypotheses_means_insufficient_evidence():
    result = await adjudicate([], _knowledge_finding([]))
    assert result.selected_hypothesis is None
    assert result.confidence == 0.0
    assert result.needs_human_review is True


async def test_selects_the_top_hypothesis():
    hypotheses = [
        _hypothesis("Connection pool exhaustion", 0.93),
        _hypothesis("Redis involvement", 0.4),
    ]
    result = await adjudicate(hypotheses, _knowledge_finding([]))
    assert result.selected_hypothesis == "Connection pool exhaustion"
    assert result.confidence == 0.93


async def test_strong_confidence_does_not_need_review():
    hypotheses = [_hypothesis("Connection pool exhaustion", 0.95)]
    result = await adjudicate(hypotheses, _knowledge_finding([]))
    assert result.needs_human_review is False


async def test_weak_confidence_needs_review():
    hypotheses = [_hypothesis("Connection pool exhaustion", 0.5)]
    result = await adjudicate(hypotheses, _knowledge_finding([]))
    assert result.needs_human_review is True


async def test_matching_runbook_becomes_the_recommended_action():
    runbook = _evidence(
        "RUNBOOK-db-connection-pool-exhaustion",
        SourceType.RUNBOOK,
        "Runbook: Database Connection Pool Exhaustion remediation steps",
        source="runbooks/db-connection-pool-exhaustion.md",
    )
    hypotheses = [_hypothesis("Connection pool exhaustion", 0.93)]
    result = await adjudicate(hypotheses, _knowledge_finding([runbook]))

    assert "runbooks/db-connection-pool-exhaustion.md" in result.recommended_action
    assert runbook in result.supporting_evidence


async def test_no_matching_runbook_falls_back_to_escalation_action():
    hypotheses = [_hypothesis("Connection pool exhaustion", 0.93)]
    result = await adjudicate(hypotheses, _knowledge_finding([]))
    assert "escalate" in result.recommended_action.lower()


async def test_contradicting_evidence_is_carried_through():
    contradiction = _evidence("METRIC-1", SourceType.METRIC, "db_connections_active=2.0")
    hypotheses = [_hypothesis("Connection pool exhaustion", 0.6, contradicting=[contradiction])]
    result = await adjudicate(hypotheses, _knowledge_finding([]))
    assert result.contradicting_evidence == [contradiction]


async def test_uses_llm_when_provided():
    hypotheses = [_hypothesis("Connection pool exhaustion", 0.93)]
    result = await adjudicate(hypotheses, _knowledge_finding([]), llm=FakeLLM())
    assert result.reasoning_summary == "fake reasoning"
