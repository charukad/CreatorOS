import base64
import re
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from apps.api.core.redaction import redact_sensitive_value

_PLACEHOLDER_SCREENSHOT = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def write_failure_debug_artifacts(
    debug_root: Path,
    *,
    provider_job_id: str | None,
    error: Exception,
    snapshot_html: str | None = None,
    screenshot_bytes: bytes | None = None,
) -> list[str]:
    failure_root = debug_root / "failures"
    failure_root.mkdir(parents=True, exist_ok=True)

    prefix = _artifact_prefix(provider_job_id)
    screenshot_path = failure_root / f"{prefix}-screenshot.png"
    html_path = failure_root / f"{prefix}-snapshot.html"

    screenshot_path.write_bytes(screenshot_bytes or _PLACEHOLDER_SCREENSHOT)
    html_path.write_text(
        _redact_artifact_text(
            snapshot_html or _fallback_snapshot_html(error=error, provider_job_id=provider_job_id)
        ),
        encoding="utf-8",
    )

    return [str(screenshot_path), str(html_path)]


def write_checkpoint_debug_artifacts(
    debug_root: Path,
    *,
    checkpoint_name: str,
    provider_job_id: str | None,
    snapshot_html: str | None = None,
    screenshot_bytes: bytes | None = None,
) -> list[str]:
    checkpoint_root = debug_root / "checkpoints"
    checkpoint_root.mkdir(parents=True, exist_ok=True)

    prefix = _artifact_prefix(provider_job_id)
    safe_checkpoint_name = _safe_filename(checkpoint_name)
    screenshot_path = checkpoint_root / f"{prefix}-{safe_checkpoint_name}-screenshot.png"
    html_path = checkpoint_root / f"{prefix}-{safe_checkpoint_name}-snapshot.html"

    screenshot_path.write_bytes(screenshot_bytes or _PLACEHOLDER_SCREENSHOT)
    html_path.write_text(
        _redact_artifact_text(
            snapshot_html or _fallback_checkpoint_html(checkpoint_name=checkpoint_name)
        ),
        encoding="utf-8",
    )

    return [str(screenshot_path), str(html_path)]


def capture_playwright_failure_artifacts(
    page: Any,
    debug_root: Path,
    *,
    provider_job_id: str | None,
    error: Exception,
) -> list[str]:
    screenshot_bytes = page.screenshot(full_page=True)
    snapshot_html = page.content()
    return write_failure_debug_artifacts(
        debug_root,
        provider_job_id=provider_job_id,
        error=error,
        snapshot_html=snapshot_html,
        screenshot_bytes=screenshot_bytes,
    )


def capture_playwright_checkpoint_artifacts(
    page: Any,
    debug_root: Path,
    *,
    checkpoint_name: str,
    provider_job_id: str | None,
) -> list[str]:
    screenshot_bytes = page.screenshot(full_page=True)
    snapshot_html = page.content()
    return write_checkpoint_debug_artifacts(
        debug_root,
        checkpoint_name=checkpoint_name,
        provider_job_id=provider_job_id,
        snapshot_html=snapshot_html,
        screenshot_bytes=screenshot_bytes,
    )


def _artifact_prefix(provider_job_id: str | None) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    safe_job_id = _safe_filename(provider_job_id or "unknown-provider-job")
    return f"{safe_job_id}-{timestamp}"


def _safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-") or "artifact"


def _fallback_snapshot_html(*, error: Exception, provider_job_id: str | None) -> str:
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8" />',
            "  <title>CreatorOS Browser Failure Snapshot</title>",
            "</head>",
            "<body>",
            "  <h1>Browser failure snapshot unavailable</h1>",
            f"  <p>Provider job: {escape(provider_job_id or 'unknown')}</p>",
            f"  <p>Error: {escape(str(error))}</p>",
            "</body>",
            "</html>",
        ]
    )


def _fallback_checkpoint_html(*, checkpoint_name: str) -> str:
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8" />',
            "  <title>CreatorOS Browser Checkpoint Snapshot</title>",
            "</head>",
            "<body>",
            f"  <h1>{escape(checkpoint_name)}</h1>",
            "  <p>Checkpoint snapshot captured without a live browser page.</p>",
            "</body>",
            "</html>",
        ]
    )


def _redact_artifact_text(value: str) -> str:
    return redact_sensitive_value(value)
