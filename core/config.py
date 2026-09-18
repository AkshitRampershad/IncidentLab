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

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
