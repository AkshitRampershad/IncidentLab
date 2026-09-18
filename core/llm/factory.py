from core.config import Settings, get_settings
from core.llm.anthropic_compatible import AnthropicCompatibleProvider
from core.llm.base import LLMProvider
from core.llm.ollama import OllamaProvider
from core.llm.openai_compatible import OpenAICompatibleProvider

_PROVIDERS = {
    "ollama": OllamaProvider,
    "openai": OpenAICompatibleProvider,
    "anthropic": AnthropicCompatibleProvider,
}


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    provider_name = settings.llm_provider.lower()

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
    if provider_name in ("openai", "anthropic"):
        provider_cls = _PROVIDERS[provider_name]
        return provider_cls(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_seconds,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{settings.llm_provider}'. Supported: {', '.join(_PROVIDERS)}"
    )
