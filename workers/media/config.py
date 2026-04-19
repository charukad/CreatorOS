from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MediaWorkerSettings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    storage_root: Path = Field(default=Path("storage"), alias="STORAGE_ROOT")
    downloads_root: Path = Field(default=Path("storage/downloads"), alias="DOWNLOADS_ROOT")
    ffmpeg_binary: str = Field(default="ffmpeg", alias="FFMPEG_BINARY")
    media_enable_ffmpeg_render: bool = Field(default=False, alias="MEDIA_ENABLE_FFMPEG_RENDER")

    model_config = SettingsConfigDict(
        env_file=("workers/media/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> MediaWorkerSettings:
    return MediaWorkerSettings()
