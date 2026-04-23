from pathlib import Path

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from apps.api.models.asset import Asset
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.models.user import User
from apps.api.schemas.content_workflow import (
    ArtifactRetentionCandidateResponse,
    ArtifactRetentionPlanResponse,
    ArtifactRetentionSummaryResponse,
)
from apps.api.schemas.enums import AssetStatus, ScriptStatus
from apps.api.services.storage_paths import build_project_storage_path

RETENTION_READY_STATUSES = {AssetStatus.FAILED, AssetStatus.REJECTED}


def build_artifact_retention_plan(
    db: Session,
    user: User,
    *,
    storage_root: Path,
    limit: int = 50,
) -> ArtifactRetentionPlanResponse:
    statement = (
        select(Asset, Project, ProjectScript)
        .join(Project, Project.id == Asset.project_id)
        .join(ProjectScript, ProjectScript.id == Asset.script_id)
        .where(
            Asset.user_id == user.id,
            Asset.file_path.is_not(None),
            or_(
                Asset.status.in_(RETENTION_READY_STATUSES),
                ProjectScript.status == ScriptStatus.SUPERSEDED,
            ),
        )
        .order_by(desc(Asset.updated_at), desc(Asset.created_at))
        .limit(limit)
    )

    candidates = [
        _build_candidate(asset, project, script, storage_root=storage_root)
        for asset, project, script in db.execute(statement).all()
        if asset.file_path is not None
    ]
    total_reclaimable_bytes = sum(
        candidate.size_bytes or 0 for candidate in candidates if candidate.safe_to_cleanup
    )

    return ArtifactRetentionPlanResponse(
        candidates=candidates,
        summary=ArtifactRetentionSummaryResponse(
            candidate_count=len(candidates),
            safe_candidate_count=sum(1 for candidate in candidates if candidate.safe_to_cleanup),
            total_reclaimable_bytes=total_reclaimable_bytes,
        ),
    )


def _build_candidate(
    asset: Asset,
    project: Project,
    script: ProjectScript,
    *,
    storage_root: Path,
) -> ArtifactRetentionCandidateResponse:
    file_path = asset.file_path or ""
    path_state = _inspect_asset_path(file_path, storage_root)
    reason, recommended_action, safe_to_cleanup = _retention_decision(
        asset,
        script,
        file_exists=path_state.file_exists,
        is_inside_storage=path_state.is_inside_storage,
    )
    retention_manifest_path = (
        build_project_storage_path(
            project.id,
            "retention",
            f"asset-{str(asset.id)[:8]}-retention.json",
        )
        if safe_to_cleanup
        else None
    )

    return ArtifactRetentionCandidateResponse(
        asset_id=asset.id,
        project_id=project.id,
        project_title=project.title,
        script_id=asset.script_id,
        asset_type=asset.asset_type,
        status=asset.status,
        file_path=file_path,
        file_exists=path_state.file_exists,
        size_bytes=path_state.size_bytes,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        reason=reason,
        recommended_action=recommended_action,
        safe_to_cleanup=safe_to_cleanup,
        retention_manifest_path=retention_manifest_path,
    )


class _PathState:
    def __init__(
        self,
        *,
        file_exists: bool,
        is_inside_storage: bool,
        size_bytes: int | None,
    ) -> None:
        self.file_exists = file_exists
        self.is_inside_storage = is_inside_storage
        self.size_bytes = size_bytes


def _inspect_asset_path(file_path: str, storage_root: Path) -> _PathState:
    root_path = storage_root.resolve()
    candidate_path = Path(file_path).resolve()
    is_inside_storage = candidate_path.is_relative_to(root_path)
    if not is_inside_storage:
        return _PathState(
            file_exists=candidate_path.exists(), is_inside_storage=False, size_bytes=None
        )

    if not candidate_path.exists():
        return _PathState(file_exists=False, is_inside_storage=True, size_bytes=None)

    return _PathState(
        file_exists=True,
        is_inside_storage=True,
        size_bytes=candidate_path.stat().st_size if candidate_path.is_file() else None,
    )


def _retention_decision(
    asset: Asset,
    script: ProjectScript,
    *,
    file_exists: bool,
    is_inside_storage: bool,
) -> tuple[str, str, bool]:
    if not is_inside_storage:
        return (
            "Asset file path is outside the configured storage root and needs manual review.",
            "manual_review",
            False,
        )

    if not file_exists:
        return (
            "Asset metadata points to a missing file; repair metadata before any cleanup action.",
            "repair_missing_file",
            False,
        )

    if asset.status in RETENTION_READY_STATUSES:
        return (
            f"Asset is {asset.status.value} and can be moved to retention with a manifest.",
            "move_to_retention",
            True,
        )

    if script.status == ScriptStatus.SUPERSEDED:
        return (
            "Asset belongs to a superseded script version; manual review is required "
            "before cleanup.",
            "manual_review",
            False,
        )

    return (
        "Asset matched retention planning rules but does not have an automatic cleanup decision.",
        "manual_review",
        False,
    )
