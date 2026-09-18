from datetime import UTC, datetime

from agents.base import hypotheses_from_content, summarize_or_fallback
from core.llm.base import LLMProvider, LLMUnavailableError
from evidence.models import Evidence, Provenance, SourceType

NOW = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


def _evidence(content: str) -> Evidence:
    return Evidence(
        evidence_id="LOG-1",
        source_type=SourceType.LOG,
        source="checkout",
        timestamp=NOW,
        content=content,
        relevance=1.0,
        provenance=Provenance(
            table="log_events", row_id="1", incident_id="INC-0001", retrieved_at=NOW
        ),
    )


class FakeLLM(LLMProvider):
    def __init__(self, *, response: str | None = None, raises: bool = False):
        self._response = response
        self._raises = raises

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        if self._raises:
            raise LLMUnavailableError("simulated failure")
        return self._response


def test_hypotheses_from_content_matches_known_patterns():
    evidence = [_evidence("[error] database connection timeout after 30000ms (pool exhausted)")]
    signals = hypotheses_from_content(evidence)
    texts = [s.hypothesis for s in signals]
    assert "Connection pool exhaustion" in texts
    assert "Database or downstream connectivity issue (connection timeouts)" in texts
    for signal in signals:
        assert signal.evidence_ids == ["LOG-1"]


def test_hypotheses_from_content_no_match_returns_empty():
    assert hypotheses_from_content([_evidence("[info] cache miss for cart:8391")]) == []


async def test_summarize_or_fallback_with_no_llm_returns_fallback():
    result = await summarize_or_fallback(
        None, prompt="p", system=None, fallback="the fallback text"
    )
    assert result == "the fallback text"


async def test_summarize_or_fallback_uses_llm_when_available():
    llm = FakeLLM(response="an LLM-generated summary")
    result = await summarize_or_fallback(llm, prompt="p", system=None, fallback="fallback")
    assert result == "an LLM-generated summary"


async def test_summarize_or_fallback_degrades_gracefully_on_llm_failure():
    llm = FakeLLM(raises=True)
    result = await summarize_or_fallback(llm, prompt="p", system=None, fallback="the fallback text")
    assert result == "the fallback text"
