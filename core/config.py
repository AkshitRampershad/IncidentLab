from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Shared configuration, sourced from environment variables / .env.

    Lives in `core` (not `apps/api`) because it's consumed by more than the
    web API: the simulator (Phase 2) and, later, the evidence/tool layer
    all need the same database settings without depending on the API layer.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "incidentlab"
    postgres_password: str = "incidentlab"
    postgres_db: str = "incidentlab"

    # spec §44: local Ollama is the default, never a hard requirement on a
    # proprietary API. "openai" and "anthropic" here mean OpenAI/Anthropic
    # *-compatible HTTP APIs (base_url is swappable), not a vendor lock-in.
    llm_provider: str = "ollama"
    llm_model: str = "llama3.1"
    llm_base_url: str = "http://localhost:11434"
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 30.0

    # spec §19's confidence gate: >= strong -> confident conclusion;
    # >= review (but < strong) -> conclusion + human review; below review
    # -> insufficient evidence. "Initial configuration, not universal
    # truths" per the spec's own words — hence configurable, not hardcoded.
    confidence_strong_threshold: float = 0.90
    confidence_review_threshold: float = 0.70

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
