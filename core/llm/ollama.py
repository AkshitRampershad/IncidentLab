import httpx

from core.llm.base import LLMProvider, LLMUnavailableError


class OllamaProvider(LLMProvider):
    """Talks to a local (or self-hosted) Ollama server's /api/generate."""

    def __init__(
        self, *, base_url: str, model: str, timeout: float, client: httpx.AsyncClient | None = None
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._client = client

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        payload = {"model": self._model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system

        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(f"{self._base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["response"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise LLMUnavailableError(f"Ollama request failed: {exc}") from exc
        finally:
            if self._client is None:
                await client.aclose()
