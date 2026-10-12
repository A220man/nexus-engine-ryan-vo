import os
from typing import Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    DEMO_MODE: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./nexus_engine.db"

    # Authentication / OIDC settings
    OIDC_ISSUER_URL: str = "http://127.0.0.1:8080/realms/nexus-realm"
    OIDC_CLIENT_ID: str = "nexus-engine-client"
    OIDC_AUDIENCE: str = "nexus-engine-api"
    OIDC_ENABLED: bool = False
    JWT_SECRET_KEY: str = "nexus-engine-local-development-secret-key-32b"

    # Optional Operator LLM Provider settings
    LLM_PROVIDER: Literal["openai-compatible", "anthropic", "gemini", "ollama"] = "openai-compatible"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""

    # Execution sandbox controls
    MAX_EXECUTION_TIMEOUT_SECONDS: int = 120
    MAX_CHUNK_SIZE_BYTES: int = 65536  # 64 KB chunk size cap prevents DB/WAL bloat
    OUTPUT_SANDBOX_THRESHOLD_BYTES: int = 512

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def get_settings() -> Settings:
    settings = Settings()
    # Enforce contract: startup strictly REFUSES demo mode in production
    if settings.ENVIRONMENT == "production" and settings.DEMO_MODE:
        raise RuntimeError("Startup refused: DEMO_MODE cannot be enabled in production environment.")
    return settings


settings = get_settings()
