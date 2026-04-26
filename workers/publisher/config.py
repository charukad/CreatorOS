from functools import lru_cache
from pathlib import Path
from typing import Self

from apps.api.core.config_validation import validate_non_empty_path
from apps.api.core.env_files import build_settings_env_files
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PublisherWorkerSettings(BaseSettings):
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
    publisher_max_jobs_per_run: int = Field(default=10, ge=1, alias="PUBLISHER_MAX_JOBS_PER_RUN")
    storage_root: Path = Field(default=Path("storage"), alias="STORAGE_ROOT")

    model_config = SettingsConfigDict(
        env_file=build_settings_env_files("workers/publisher"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_runtime_settings(self) -> Self:
        validate_non_empty_path(self.storage_root, "STORAGE_ROOT")
        return self


@lru_cache
def get_settings() -> PublisherWorkerSettings:
    return PublisherWorkerSettings()
