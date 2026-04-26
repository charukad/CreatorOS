from pathlib import Path
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.core.config_validation import resolve_path_within_roots
from apps.api.models.approval import Approval
from apps.api.models.asset import Asset
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.models.user import User
from apps.api.schemas.enums import (
    ApprovalDecision,
    ApprovalStage,
    ApprovalTargetType,
    AssetStatus,
    AssetType,
    BackgroundJobState,
    ProjectStatus,
)
from apps.api.services.approvals import create_approval_record, get_latest_stage_approval
from apps.api.services.project_events import create_project_event

ACTIVE_JOB_STATES = {
    BackgroundJobState.QUEUED,
    BackgroundJobState.RUNNING,
    BackgroundJobState.WAITING_EXTERNAL,
}

VISUAL_ASSET_TYPES = {AssetType.SCENE_IMAGE, AssetType.SCENE_VIDEO}


def get_asset(db: Session, user: User, asset_id: UUID) -> Asset | None:
    statement = select(Asset).where(Asset.id == asset_id, Asset.user_id == user.id)
    return db.scalar(statement)


def list_script_assets(db: Session, script: ProjectScript) -> list[Asset]:
    statement = (
        select(Asset)
        .where(Asset.script_id == script.id)
        .order_by(desc(Asset.updated_at), desc(Asset.created_at))
    )
    return list(db.scalars(statement))


def approve_current_script_assets(
    db: Session,
    *,
    user: User,
    project: Project,
    script: ProjectScript,
    feedback_notes: str | None = None,
):
    if project.status != ProjectStatus.ASSET_PENDING_APPROVAL:
        raise ValueError("Assets can only be approved while the project is in asset review.")

    ready_assets = _get_ready_assets_for_script(db, script)
    if not ready_assets:
        raise ValueError("There are no ready assets to approve for the current script.")

    if not _has_required_asset_mix(ready_assets):
        raise ValueError(
            "Approve-ready assets must include narration and at least one scene visual."
        )

    approval = create_approval_record(
        db,
        user=user,
        project=project,
        target_type=ApprovalTargetType.SCRIPT,
        target_id=script.id,
        stage=ApprovalStage.ASSETS,
        decision=ApprovalDecision.APPROVED,
        feedback_notes=feedback_notes,
    )
    db.commit()
    db.refresh(approval)
    return approval


def approve_asset(
    db: Session,
    *,
    user: User,
    project: Project,
    asset: Asset,
    feedback_notes: str | None = None,
) -> Approval:
    _validate_asset_review_action(project, asset)

    if asset.status != AssetStatus.READY:
        raise ValueError("Only ready assets can be approved.")

    approval = create_approval_record(
        db,
        user=user,
        project=project,
        target_type=ApprovalTargetType.ASSET,
        target_id=asset.id,
        stage=ApprovalStage.ASSETS,
        decision=ApprovalDecision.APPROVED,
        feedback_notes=feedback_notes,
    )
    create_project_event(
        db,
        project,
        event_type="asset_approved",
        title="Asset approved",
        description=feedback_notes,
        metadata=_asset_event_metadata(asset),
    )
    db.commit()
    db.refresh(approval)
    return approval


def reject_current_script_assets(
    db: Session,
    *,
    user: User,
    project: Project,
    script: ProjectScript,
    feedback_notes: str | None = None,
):
    if project.status != ProjectStatus.ASSET_PENDING_APPROVAL:
        raise ValueError("Assets can only be rejected while the project is in asset review.")

    ready_assets = _get_ready_assets_for_script(db, script)
    if not ready_assets:
        raise ValueError("There are no ready assets to reject for the current script.")

    for asset in ready_assets:
        asset.status = AssetStatus.REJECTED
        db.add(asset)

    project.status = ProjectStatus.ASSET_GENERATION
    db.add(project)
    approval = create_approval_record(
        db,
        user=user,
        project=project,
        target_type=ApprovalTargetType.SCRIPT,
        target_id=script.id,
        stage=ApprovalStage.ASSETS,
        decision=ApprovalDecision.REJECTED,
        feedback_notes=feedback_notes,
    )
    db.commit()
    db.refresh(approval)
    return approval


def reject_asset(
    db: Session,
    *,
    user: User,
    project: Project,
    asset: Asset,
    feedback_notes: str | None = None,
) -> Approval:
    approval = stage_asset_rejection(
        db,
        user=user,
        project=project,
        asset=asset,
        feedback_notes=feedback_notes,
    )
    if approval is None:
        raise ValueError("This asset is already rejected.")

    db.commit()
    db.refresh(approval)
    return approval


def stage_asset_rejection(
    db: Session,
    *,
    user: User,
    project: Project,
    asset: Asset,
    feedback_notes: str | None = None,
    allow_already_rejected: bool = False,
) -> Approval | None:
    _validate_asset_project(project, asset)

    if project.status not in {
        ProjectStatus.ASSET_PENDING_APPROVAL,
        ProjectStatus.ASSET_GENERATION,
    }:
        raise ValueError(
            "Assets can only be rejected or regenerated while the project is in asset review "
            "or asset generation."
        )

    if asset.status == AssetStatus.REJECTED:
        if allow_already_rejected:
            project.status = ProjectStatus.ASSET_GENERATION
            db.add(project)
            return None
        raise ValueError("This asset is already rejected.")

    if asset.status != AssetStatus.READY:
        raise ValueError("Only ready assets can be rejected or regenerated.")

    asset.status = AssetStatus.REJECTED
    project.status = ProjectStatus.ASSET_GENERATION
    db.add(asset)
    db.add(project)
    create_project_event(
        db,
        project,
        event_type="asset_rejected",
        title="Asset rejected",
        description=feedback_notes,
        level="warning",
        metadata=_asset_event_metadata(asset),
    )
    return create_approval_record(
        db,
        user=user,
        project=project,
        target_type=ApprovalTargetType.ASSET,
        target_id=asset.id,
        stage=ApprovalStage.ASSETS,
        decision=ApprovalDecision.REJECTED,
        feedback_notes=feedback_notes,
    )


def resolve_asset_file_path(asset: Asset, storage_root: Path) -> Path:
    if asset.file_path is None:
        raise ValueError("The requested asset does not have a stored file yet.")

    return resolve_path_within_roots(
        Path(asset.file_path),
        allowed_roots=(storage_root,),
        path_name="The requested asset path",
        must_exist=True,
    )


def has_approved_asset_review(db: Session, project: Project, script: ProjectScript) -> bool:
    latest_approval = get_latest_stage_approval(
        db,
        project,
        stage=ApprovalStage.ASSETS,
        target_id=script.id,
    )
    return latest_approval is not None and latest_approval.decision == ApprovalDecision.APPROVED


def has_ready_rough_cut(db: Session, script: ProjectScript) -> bool:
    statement = select(Asset).where(
        Asset.script_id == script.id,
        Asset.asset_type == AssetType.ROUGH_CUT,
        Asset.status == AssetStatus.READY,
    )
    return db.scalar(statement) is not None


def can_enter_asset_review(db: Session, project: Project, script: ProjectScript) -> bool:
    ready_assets = _get_ready_assets_for_script(db, script)
    if not _has_required_asset_mix(ready_assets):
        return False

    from apps.api.models.background_job import BackgroundJob

    active_jobs_statement = select(BackgroundJob).where(
        BackgroundJob.project_id == project.id,
        BackgroundJob.script_id == script.id,
        BackgroundJob.state.in_(ACTIVE_JOB_STATES),
    )
    return db.scalar(active_jobs_statement) is None


def _get_ready_assets_for_script(db: Session, script: ProjectScript) -> list[Asset]:
    statement = select(Asset).where(
        Asset.script_id == script.id,
        Asset.status == AssetStatus.READY,
    )
    return list(db.scalars(statement))


def _has_required_asset_mix(assets: list[Asset]) -> bool:
    has_narration = any(asset.asset_type == AssetType.NARRATION_AUDIO for asset in assets)
    has_visual = any(asset.asset_type in VISUAL_ASSET_TYPES for asset in assets)
    return has_narration and has_visual


def _validate_asset_review_action(project: Project, asset: Asset) -> None:
    _validate_asset_project(project, asset)

    if project.status != ProjectStatus.ASSET_PENDING_APPROVAL:
        raise ValueError("Assets can only be approved while the project is in asset review.")


def _validate_asset_project(project: Project, asset: Asset) -> None:
    if asset.project_id != project.id:
        raise ValueError("The selected asset does not belong to this project.")


def _asset_event_metadata(asset: Asset) -> dict[str, object]:
    return {
        "asset_id": str(asset.id),
        "asset_type": asset.asset_type.value,
        "scene_id": str(asset.scene_id) if asset.scene_id is not None else None,
        "generation_attempt_id": (
            str(asset.generation_attempt_id) if asset.generation_attempt_id is not None else None
        ),
    }
