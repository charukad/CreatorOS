from __future__ import annotations

import json
import mimetypes
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from apps.api.models.generation_attempt import GenerationAttempt
from apps.api.services.file_metadata import file_sha256
from apps.api.services.storage_paths import build_project_storage_path


@dataclass(frozen=True, slots=True)
class TaggedDownload:
    ordinal: int
    provider_job_id: str
    original_source_path: str
    original_file_name: str
    staged_path: str
    metadata_path: str
    checksum: str
    file_size_bytes: int
    mime_type: str | None


def stage_provider_downloads_for_attempt(
    attempt: GenerationAttempt,
    *,
    provider_job_id: str,
    download_paths: list[str],
) -> list[TaggedDownload]:
    ingest_root = Path(
        build_project_storage_path(
            attempt.project_id,
            "metadata",
            "browser-downloads",
            f"job-{attempt.background_job_id}",
            f"attempt-{attempt.id}",
        )
    )
    ingest_root.mkdir(parents=True, exist_ok=True)

    tagged_downloads: list[TaggedDownload] = []
    for ordinal, download_path in enumerate(download_paths, start=1):
        source_path = Path(download_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Expected provider download does not exist: {source_path}")

        staged_name = f"download-{ordinal:02d}-{_sanitize_filename(source_path.name)}"
        staged_path = _stage_download(source_path, ingest_root / staged_name)
        metadata_path = staged_path.with_name(f"{staged_path.name}.json")
        checksum = file_sha256(staged_path)
        mime_type, _ = mimetypes.guess_type(staged_path.name)

        metadata_path.write_text(
            json.dumps(
                {
                    "metadata_type": "browser_download_intercept",
                    "background_job_id": str(attempt.background_job_id),
                    "generation_attempt_id": str(attempt.id),
                    "project_id": str(attempt.project_id),
                    "script_id": str(attempt.script_id),
                    "scene_id": str(attempt.scene_id) if attempt.scene_id is not None else None,
                    "provider_name": attempt.provider_name.value,
                    "provider_job_id": provider_job_id,
                    "ordinal": ordinal,
                    "original_source_path": str(source_path),
                    "original_file_name": source_path.name,
                    "staged_path": str(staged_path),
                    "checksum": checksum,
                    "file_size_bytes": staged_path.stat().st_size,
                    "mime_type": mime_type,
                    "created_at": datetime.now(UTC).isoformat(),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        tagged_downloads.append(
            TaggedDownload(
                ordinal=ordinal,
                provider_job_id=provider_job_id,
                original_source_path=str(source_path),
                original_file_name=source_path.name,
                staged_path=str(staged_path),
                metadata_path=str(metadata_path),
                checksum=checksum,
                file_size_bytes=staged_path.stat().st_size,
                mime_type=mime_type,
            )
        )

    return tagged_downloads


def is_managed_browser_download_path(path: Path) -> bool:
    parts = path.parts
    for index, part in enumerate(parts[:-1]):
        if part == "metadata" and parts[index + 1] == "browser-downloads":
            return True
    return False


def _stage_download(source_path: Path, destination_path: Path) -> Path:
    if source_path.resolve() == destination_path.resolve():
        return source_path

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path = _unique_destination_path(destination_path)
    shutil.move(str(source_path), staged_path)
    return staged_path


def _unique_destination_path(destination_path: Path) -> Path:
    if not destination_path.exists():
        return destination_path

    for index in range(1, 1000):
        candidate = destination_path.with_name(
            f"{destination_path.stem}-{index}{destination_path.suffix}"
        )
        if not candidate.exists():
            return candidate

    raise ValueError(f"Unable to find a unique managed download path for {destination_path}.")


def _sanitize_filename(value: str) -> str:
    safe_value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-")
    return safe_value or "download"
