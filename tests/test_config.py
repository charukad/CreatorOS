from pathlib import Path

import pytest
from apps.api.core.config import Settings
from apps.api.core.config_validation import normalize_app_env, resolve_path_within_roots
from apps.api.core.env_files import build_settings_env_files
from pydantic import ValidationError
from workers.analytics.config import AnalyticsWorkerSettings
from workers.browser.config import BrowserWorkerSettings
from workers.media.config import MediaWorkerSettings
from workers.publisher.config import PublisherWorkerSettings


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

    settings = BrowserWorkerSettings(BROWSER_PROVIDER_MODE="playwright")
    assert settings.browser_provider_mode == "playwright"
    assert settings.redis_url == "redis://localhost:6379/0"

    with pytest.raises(ValidationError, match="ELEVENLABS_WORKSPACE_URL"):
        BrowserWorkerSettings(
            BROWSER_PROVIDER_MODE="playwright",
            ELEVENLABS_WORKSPACE_URL="",
        )

    with pytest.raises(ValidationError, match="FLOW_WORKSPACE_URL"):
        BrowserWorkerSettings(
            BROWSER_PROVIDER_MODE="playwright",
            FLOW_WORKSPACE_URL="",
        )


def test_env_file_builder_supports_local_secret_patterns_by_environment() -> None:
    files = build_settings_env_files("workers/browser", app_env="localprod")

    assert files[0] == "workers/browser/.env"
    assert "workers/browser/.env.local" in files
    assert "workers/browser/.env.localprod" in files
    assert "workers/browser/.env.localprod.local" in files
    assert "workers/browser/.env.secrets.local" in files
    assert "workers/browser/.env.localprod.secrets.local" in files
    assert ".env.localprod" in files
    assert ".env.localprod.secrets.local" in files
    assert normalize_app_env("test") == "testing"
    assert normalize_app_env("localprod") == "localprod"


def test_resolve_path_within_roots_blocks_paths_outside_allowed_root(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    inside_path = storage_root / "projects" / "demo.txt"
    outside_path = tmp_path / "outside.txt"

    resolved_inside = resolve_path_within_roots(
        inside_path,
        allowed_roots=(storage_root,),
        path_name="Artifact path",
    )
    assert resolved_inside == inside_path.resolve()

    with pytest.raises(ValueError, match="Artifact path must stay within configured roots"):
        resolve_path_within_roots(
            outside_path,
            allowed_roots=(storage_root,),
            path_name="Artifact path",
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
    assert settings.redis_url == "redis://localhost:6379/0"


def test_publisher_and_analytics_settings_include_redis_url() -> None:
    publisher_settings = PublisherWorkerSettings()
    analytics_settings = AnalyticsWorkerSettings()

    assert publisher_settings.redis_url == "redis://localhost:6379/0"
    assert analytics_settings.redis_url == "redis://localhost:6379/0"
