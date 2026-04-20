from functools import lru_cache
from pathlib import Path
from typing import Self

from apps.api.core.config_validation import validate_distinct_paths, validate_non_empty_path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BrowserWorkerSettings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    browser_provider_mode: str = Field(default="dry_run", alias="BROWSER_PROVIDER_MODE")
    browser_max_jobs_per_run: int = Field(default=10, ge=1, alias="BROWSER_MAX_JOBS_PER_RUN")
    playwright_headless: bool = Field(default=True, alias="PLAYWRIGHT_HEADLESS")
    playwright_profile_root: Path = Field(
        default=Path("browser-profiles"),
        alias="PLAYWRIGHT_PROFILE_ROOT",
    )
    playwright_download_root: Path = Field(
        default=Path("storage/downloads"),
        alias="PLAYWRIGHT_DOWNLOAD_ROOT",
    )
    elevenlabs_profile_name: str = Field(
        default="elevenlabs-default",
        alias="ELEVENLABS_PROFILE_NAME",
    )
    flow_profile_name: str = Field(default="flow-default", alias="FLOW_PROFILE_NAME")

    model_config = SettingsConfigDict(
        env_file=("workers/browser/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_runtime_settings(self) -> Self:
        if self.browser_provider_mode != "dry_run":
            raise ValueError(
                "BROWSER_PROVIDER_MODE must be dry_run until live providers are implemented."
            )
        validate_non_empty_path(self.playwright_profile_root, "PLAYWRIGHT_PROFILE_ROOT")
        validate_non_empty_path(self.playwright_download_root, "PLAYWRIGHT_DOWNLOAD_ROOT")
        validate_distinct_paths(
            self.playwright_profile_root,
            "PLAYWRIGHT_PROFILE_ROOT",
            self.playwright_download_root,
            "PLAYWRIGHT_DOWNLOAD_ROOT",
        )
        return self


@lru_cache
def get_settings() -> BrowserWorkerSettings:
    return BrowserWorkerSettings()
