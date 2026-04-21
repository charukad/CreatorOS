from pathlib import Path

import pytest
from apps.api.core.config import Settings
from pydantic import ValidationError
from workers.browser.config import BrowserWorkerSettings
from workers.media.config import MediaWorkerSettings


def test_api_settings_reject_default_secret_in_production() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(APP_ENV="production", SECRET_KEY="dev-secret-key")


def test_api_settings_allow_local_default_secret() -> None:
    settings = Settings(APP_ENV="development", SECRET_KEY="dev-secret-key")

    assert settings.app_env == "development"
    assert settings.secret_key == "dev-secret-key"


def test_browser_settings_validate_provider_mode_and_paths() -> None:
    with pytest.raises(ValidationError, match="BROWSER_PROVIDER_MODE"):
        BrowserWorkerSettings(BROWSER_PROVIDER_MODE="live")

    with pytest.raises(ValidationError, match="must be different"):
        BrowserWorkerSettings(
            PLAYWRIGHT_PROFILE_ROOT=Path("storage/downloads"),
            PLAYWRIGHT_DOWNLOAD_ROOT=Path("storage/downloads"),
        )


def test_media_settings_validate_required_paths_and_ffmpeg_binary() -> None:
    with pytest.raises(ValidationError, match="FFMPEG_BINARY"):
        MediaWorkerSettings(FFMPEG_BINARY="")

    settings = MediaWorkerSettings(
        STORAGE_ROOT=Path("storage"),
        DOWNLOADS_ROOT=Path("storage/downloads"),
        FFMPEG_BINARY="ffmpeg",
    )

    assert settings.ffmpeg_binary == "ffmpeg"
