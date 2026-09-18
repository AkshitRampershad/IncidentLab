import httpx
import pytest

from core.config import Settings
from core.llm.anthropic_compatible import AnthropicCompatibleProvider
from core.llm.base import LLMUnavailableError
from core.llm.factory import get_llm_provider
from core.llm.ollama import OllamaProvider
from core.llm.openai_compatible import OpenAICompatibleProvider


def _client_with(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_ollama_generate_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        body = request.read()
        assert b'"model":"llama3.1"' in body or b"llama3.1" in body
        return httpx.Response(200, json={"response": "the root cause is..."})

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="llama3.1", timeout=5, client=_client_with(handler)
    )
    result = await provider.generate("what happened?")
    assert result == "the root cause is..."


async def test_ollama_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="llama3.1", timeout=5, client=_client_with(handler)
    )
    with pytest.raises(LLMUnavailableError):
        await provider.generate("prompt")


async def test_ollama_raises_on_connection_error():
    def handler(request: httpx.Request):
        raise httpx.ConnectError("connection refused", request=request)

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="llama3.1", timeout=5, client=_client_with(handler)
    )
    with pytest.raises(LLMUnavailableError):
        await provider.generate("prompt")


async def test_openai_compatible_generate_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers.get("authorization") == "Bearer test-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": "an answer"}}]})

    provider = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1",
        model="gpt-4",
        api_key="test-key",
        timeout=5,
        client=_client_with(handler),
    )
    result = await provider.generate("prompt", system="be terse")
    assert result == "an answer"


async def test_openai_compatible_raises_on_malformed_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    provider = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1",
        model="gpt-4",
        api_key=None,
        timeout=5,
        client=_client_with(handler),
    )
    with pytest.raises(LLMUnavailableError):
        await provider.generate("prompt")


async def test_anthropic_compatible_generate_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        assert request.headers.get("x-api-key") == "test-key"
        return httpx.Response(200, json={"content": [{"type": "text", "text": "an answer"}]})

    provider = AnthropicCompatibleProvider(
        base_url="https://api.anthropic.com",
        model="claude-sonnet-5",
        api_key="test-key",
        timeout=5,
        client=_client_with(handler),
    )
    result = await provider.generate("prompt")
    assert result == "an answer"


def test_factory_returns_ollama_by_default():
    provider = get_llm_provider(Settings(llm_provider="ollama"))
    assert isinstance(provider, OllamaProvider)


def test_factory_returns_openai_compatible():
    provider = get_llm_provider(Settings(llm_provider="openai", llm_api_key="k"))
    assert isinstance(provider, OpenAICompatibleProvider)


def test_factory_returns_anthropic_compatible():
    provider = get_llm_provider(Settings(llm_provider="anthropic", llm_api_key="k"))
    assert isinstance(provider, AnthropicCompatibleProvider)


def test_factory_raises_for_unknown_provider():
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_llm_provider(Settings(llm_provider="made-up"))
