from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalyticsWorkerSettings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    analytics_max_jobs_per_run: int = Field(default=10, ge=1, alias="ANALYTICS_MAX_JOBS_PER_RUN")

    model_config = SettingsConfigDict(
        env_file=("workers/analytics/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> AnalyticsWorkerSettings:
    return AnalyticsWorkerSettings()
