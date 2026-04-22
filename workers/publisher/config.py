from functools import lru_cache
from pathlib import Path
from typing import Self

from apps.api.core.config_validation import validate_non_empty_path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PublisherWorkerSettings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    publisher_max_jobs_per_run: int = Field(default=10, ge=1, alias="PUBLISHER_MAX_JOBS_PER_RUN")
    storage_root: Path = Field(default=Path("storage"), alias="STORAGE_ROOT")

    model_config = SettingsConfigDict(
        env_file=("workers/publisher/.env", ".env"),
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
