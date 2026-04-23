from typing import Literal
from uuid import UUID

ProjectStorageSection = Literal[
    "script",
    "audio",
    "scenes",
    "rough-cuts",
    "quarantine",
    "final",
    "subtitles",
    "metadata",
    "publish",
    "retention",
]


def _trim_slashes(value: str) -> str:
    return value.strip("/")


def build_project_storage_path(
    project_id: UUID | str,
    section: ProjectStorageSection,
    *segments: str,
) -> str:
    safe_segments = [_trim_slashes(segment) for segment in segments if _trim_slashes(segment)]
    return "/".join(
        ["storage", "projects", _trim_slashes(str(project_id)), section, *safe_segments]
    )
