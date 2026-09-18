import httpx

from core.llm.base import LLMProvider, LLMUnavailableError


class OpenAICompatibleProvider(LLMProvider):
    """Any OpenAI Chat Completions-shaped endpoint — the real OpenAI API,
    or a self-hosted server that mimics it (vLLM, LM Studio, etc.).
    `base_url` is swappable specifically so this never locks the project
    into OpenAI itself."""

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
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json={"model": self._model, "messages": messages},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LLMUnavailableError(f"OpenAI-compatible request failed: {exc}") from exc
        finally:
            if self._client is None:
                await client.aclose()
