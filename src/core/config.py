"""
SCOSINT_AI Configuration

WHY: Bütün konfiqurasiya bir yerdə, environment variable-lardan oxunur.
Pydantic Settings istifadə edirik çünki:
1. Type validation — port string olaraq gəlsə belə int-ə çevrilir
2. .env fayl dəstəyi — production-da env var, development-də .env
3. Nested config — DB, Redis, Browser ayrı-ayrı qruplanır
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    url: str = "postgresql+asyncpg://scosint:scosint_secret@localhost:5432/scosint_db"


class RedisSettings(BaseSettings):
    """Redis connection settings — broker, cache, rate limiter üçün."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    url: str = "redis://localhost:6379/0"


class CelerySettings(BaseSettings):
    """Celery task queue settings."""

    model_config = SettingsConfigDict(env_prefix="CELERY_")

    broker_url: str = "redis://localhost:6379/1"
    result_backend: str = "redis://localhost:6379/2"


class SearXNGSettings(BaseSettings):
    """SearXNG meta-search engine settings."""

    model_config = SettingsConfigDict(env_prefix="SEARXNG_")

    base_url: str = "http://localhost:8888"


class OllamaSettings(BaseSettings):
    """Ollama local LLM settings."""

    model_config = SettingsConfigDict(env_prefix="OLLAMA_")

    base_url: str = "http://localhost:11434"
    model: str = "llama3:8b"


class BrowserSettings(BaseSettings):
    """Playwright browser pool settings."""

    model_config = SettingsConfigDict(env_prefix="BROWSER_")

    headless: bool = True
    max_instances: int = Field(default=3, ge=1, le=10)
    timeout_ms: int = Field(default=30000, ge=5000)


class Settings(BaseSettings):
    """Root settings — bütün alt-settings-ləri birləşdirir."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_debug: bool = False

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "console"

    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    searxng: SearXNGSettings = Field(default_factory=SearXNGSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    browser: BrowserSettings = Field(default_factory=BrowserSettings)


# Singleton pattern — bütün modul-lar eyni settings instance-ını paylaşır
_settings: Settings | None = None


def get_settings() -> Settings:
    """Tək Settings instance-ı qaytarır (lazy initialization)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
