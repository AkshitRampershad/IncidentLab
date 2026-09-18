import httpx

from core.llm.base import LLMProvider, LLMUnavailableError

_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicCompatibleProvider(LLMProvider):
    """Any Anthropic Messages API-shaped endpoint. `base_url` is swappable
    for the same reason as OpenAICompatibleProvider — this is a shape, not
    a vendor lock-in."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout: float,
        client: httpx.AsyncClient | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._client = client

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        payload = {
            "model": self._model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        headers = {"anthropic-version": _ANTHROPIC_VERSION}
        if self._api_key:
            headers["x-api-key"] = self._api_key

        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(
                f"{self._base_url}/v1/messages", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LLMUnavailableError(f"Anthropic-compatible request failed: {exc}") from exc
        finally:
            if self._client is None:
                await client.aclose()
