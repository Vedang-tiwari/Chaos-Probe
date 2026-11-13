from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General Application
    APP_NAME: str = "Chaos Probe"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security
    ADMIN_API_KEY: str = "chaos-probe-admin-secret-key-change-in-production"
    CORS_ORIGINS: List[str] = ["*"]

    # Database
    DATABASE_URL: str = "sqlite:///./chaos_probe.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # Redis & Background Tasks
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    USE_CELERY: bool = False  # Set to True when Celery & Redis are available, otherwise use async background executor

    # Safety System Defaults
    MAX_EXPERIMENT_DURATION_SECONDS: int = 120
    DEFAULT_BASELINE_DURATION_SECONDS: int = 30
    DEFAULT_RECOVERY_WINDOW_SECONDS: int = 30
    DEFAULT_MAX_CPU_PERCENT: float = 90.0
    DEFAULT_MAX_MEMORY_PERCENT: float = 90.0
    DEFAULT_MAX_ERROR_RATE: float = 0.25
    DEFAULT_MAX_LATENCY_MS: float = 3000.0
    DEFAULT_MIN_AVAILABILITY: float = 0.70

    # Monitoring & Observability
    PROMETHEUS_METRICS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090
    OTEL_SERVICE_NAME: str = "chaos-probe"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    ENABLE_TELEMETRY: bool = False

    # Docker Integration
    DOCKER_HOST_URL: str | None = None
    DOCKER_TIMEOUT_SECONDS: int = 60


@lru_cache
def get_settings() -> Settings:
    """Returns cached application settings."""
    return Settings()
