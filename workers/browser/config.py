from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BrowserWorkerSettings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
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


@lru_cache
def get_settings() -> BrowserWorkerSettings:
    return BrowserWorkerSettings()
