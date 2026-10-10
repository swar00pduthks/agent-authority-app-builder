from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Every value comes from the environment (APP_ prefix)."""

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    # dev | test | staging | prod; passed to Agent Authority so untested-in-prod works
    environment: str = "dev"

    authority_url: str = "http://localhost:8080"
    # Control-plane service principal's ingest key. The sandbox never gets this.
    authority_ingest_key: str = ""
    authority_timeout_s: float = 5.0

    litellm_url: str = "http://localhost:4000"

    # Postgres for the LangGraph checkpointer; empty means in-memory (tests and local dev)
    database_url: str = ""

    entra_tenant_id: str = ""
    entra_audience: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
