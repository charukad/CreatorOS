from functools import lru_cache

from apps.api.core.env_files import build_settings_env_files
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalyticsWorkerSettings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    worker_enable_redis_listener: bool = Field(
        default=True,
        alias="WORKER_ENABLE_REDIS_LISTENER",
    )
    worker_listen_timeout_seconds: float = Field(
        default=15.0,
        gt=0,
        alias="WORKER_LISTEN_TIMEOUT_SECONDS",
    )
    worker_poll_interval_seconds: float = Field(
        default=5.0,
        gt=0,
        alias="WORKER_POLL_INTERVAL_SECONDS",
    )
    worker_idle_shutdown_seconds: float = Field(
        default=0.0,
        ge=0,
        alias="WORKER_IDLE_SHUTDOWN_SECONDS",
    )
    analytics_max_jobs_per_run: int = Field(default=10, ge=1, alias="ANALYTICS_MAX_JOBS_PER_RUN")

    model_config = SettingsConfigDict(
        env_file=build_settings_env_files("workers/analytics"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> AnalyticsWorkerSettings:
    return AnalyticsWorkerSettings()
