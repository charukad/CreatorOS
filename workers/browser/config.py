from functools import lru_cache
from pathlib import Path
from typing import Self

from apps.api.core.config_validation import validate_distinct_paths, validate_non_empty_path
from apps.api.core.env_files import build_settings_env_files
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SUPPORTED_BROWSER_PROVIDER_MODES = {"dry_run", "playwright"}


class BrowserWorkerSettings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    browser_provider_mode: str = Field(default="dry_run", alias="BROWSER_PROVIDER_MODE")
    browser_max_jobs_per_run: int = Field(default=10, ge=1, alias="BROWSER_MAX_JOBS_PER_RUN")
    playwright_headless: bool = Field(default=True, alias="PLAYWRIGHT_HEADLESS")
    playwright_action_timeout_ms: int = Field(
        default=10_000,
        ge=1_000,
        alias="PLAYWRIGHT_ACTION_TIMEOUT_MS",
    )
    playwright_navigation_timeout_ms: int = Field(
        default=20_000,
        ge=1_000,
        alias="PLAYWRIGHT_NAVIGATION_TIMEOUT_MS",
    )
    playwright_download_timeout_ms: int = Field(
        default=30_000,
        ge=1_000,
        alias="PLAYWRIGHT_DOWNLOAD_TIMEOUT_MS",
    )
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
    elevenlabs_workspace_url: str | None = Field(
        default="https://elevenlabs.io/app",
        alias="ELEVENLABS_WORKSPACE_URL",
    )
    flow_workspace_url: str | None = Field(
        default="https://labs.google/fx/tools/flow",
        alias="FLOW_WORKSPACE_URL",
    )

    model_config = SettingsConfigDict(
        env_file=build_settings_env_files("workers/browser"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_runtime_settings(self) -> Self:
        if self.browser_provider_mode not in SUPPORTED_BROWSER_PROVIDER_MODES:
            raise ValueError(
                "BROWSER_PROVIDER_MODE must be one of: "
                f"{', '.join(sorted(SUPPORTED_BROWSER_PROVIDER_MODES))}."
            )
        validate_non_empty_path(self.playwright_profile_root, "PLAYWRIGHT_PROFILE_ROOT")
        validate_non_empty_path(self.playwright_download_root, "PLAYWRIGHT_DOWNLOAD_ROOT")
        validate_distinct_paths(
            self.playwright_profile_root,
            "PLAYWRIGHT_PROFILE_ROOT",
            self.playwright_download_root,
            "PLAYWRIGHT_DOWNLOAD_ROOT",
        )
        if self.browser_provider_mode == "playwright":
            if not (self.elevenlabs_workspace_url or "").strip():
                raise ValueError("ELEVENLABS_WORKSPACE_URL is required in playwright mode.")
            if not (self.flow_workspace_url or "").strip():
                raise ValueError("FLOW_WORKSPACE_URL is required in playwright mode.")
        return self


@lru_cache
def get_settings() -> BrowserWorkerSettings:
    return BrowserWorkerSettings()
