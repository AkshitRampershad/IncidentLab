import structlog

from core.llm import LLMProvider, LLMUnavailableError
from evidence.models import Evidence

logger = structlog.get_logger()

# Deterministic keyword -> hypothesis-text pattern matching (spec §16: the
# LLM must not be the sole/arbitrary source of a hypothesis). Intentionally
# small and specific to what the simulator's scenarios actually produce —
# extend this list as simulator/failure_injector/ grows more scenarios,
# rather than trying to anticipate every future one now.
_HYPOTHESIS_PATTERNS: list[tuple[str, str]] = [
    ("pool exhausted", "Connection pool exhaustion"),
    ("connection timeout", "Database or downstream connectivity issue (connection timeouts)"),
    ("redis", "Cache layer (Redis) involvement"),
    ("out of memory", "Memory exhaustion"),
    ("permission denied", "Authorization/credentials issue"),
]


def hypotheses_from_content(evidence: list[Evidence]) -> list[str]:
    """Deterministic keyword-pattern matching over evidence content, in
    registration order, each hypothesis at most once."""
    lowered = [e.content.lower() for e in evidence]
    return [
        hypothesis
        for keyword, hypothesis in _HYPOTHESIS_PATTERNS
        if any(keyword in content for content in lowered)
    ]


async def summarize_or_fallback(
    llm: LLMProvider | None, *, prompt: str, system: str | None, fallback: str
) -> str:
    """Try an LLM-generated summary; always return something usable.

    Never raises: an absent or unreachable LLM degrades to `fallback`
    (deterministic, built from the same structured findings) rather than
    blocking the agent. The LLM is a narration enhancement on top of
    findings that are already fully computed without it — not a
    dependency the agent's core output relies on.
    """
    if llm is None:
        return fallback
    try:
        return await llm.generate(prompt, system=system)
    except LLMUnavailableError as exc:
        logger.warning("llm_summary_unavailable", error=str(exc))
        return fallback
