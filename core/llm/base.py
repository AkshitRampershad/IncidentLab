from abc import ABC, abstractmethod


class LLMUnavailableError(Exception):
    """Raised by every provider implementation for any failure to get a
    completion — connection refused, timeout, non-2xx response, malformed
    body. Callers catch this one type regardless of which provider is
    configured; they never need to know which HTTP client or API shape
    failed underneath."""


class LLMProvider(ABC):
    """spec §44's model abstraction. Local Ollama is the default
    (core.config.Settings.llm_provider), never a hard dependency on a
    proprietary API — see core/llm/factory.py.
    """

    @abstractmethod
    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        """Return a completion for `prompt`. Raises LLMUnavailableError on
        any failure — never returns a fabricated or partial result."""
