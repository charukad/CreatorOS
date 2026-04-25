from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.models.user import User
from apps.api.schemas.enums import (
    AssetStatus,
    AssetType,
    BackgroundJobState,
    BackgroundJobType,
    ProjectStatus,
    ProviderName,
)
from apps.api.services.assets import has_approved_asset_review
from apps.api.services.background_jobs import create_job_log
from apps.api.services.queue_events import emit_background_job_event
from apps.api.services.storage_paths import build_project_storage_path

ACTIVE_JOB_STATES = {
    BackgroundJobState.QUEUED,
    BackgroundJobState.RUNNING,
    BackgroundJobState.WAITING_EXTERNAL,
}

VISUAL_ASSET_TYPES = {AssetType.SCENE_IMAGE, AssetType.SCENE_VIDEO}


def queue_rough_cut_job(
    db: Session,
    *,
    user: User,
    project: Project,
    script: ProjectScript,
) -> BackgroundJob:
    _validate_rough_cut_queue(db, project, script)
    _ensure_no_active_rough_cut_job(db, project, script)

    duration_seconds = sum(scene.estimated_duration_seconds for scene in script.scenes)
    correlation_id = str(uuid4())
    job = BackgroundJob(
        user_id=user.id,
        project_id=project.id,
        script_id=script.id,
        job_type=BackgroundJobType.COMPOSE_ROUGH_CUT,
        provider_name=ProviderName.LOCAL_MEDIA,
        state=BackgroundJobState.QUEUED,
        payload_json={
            "script_id": str(script.id),
            "script_version": script.version_number,
            "scene_count": len(script.scenes),
            "export_profile": "rough_cut_preview_v1",
            "duration_seconds": duration_seconds,
            "correlation_id": correlation_id,
        },
    )
    db.add(job)
    db.flush()
    create_job_log(
        db,
        job,
        event_type="job_queued",
        message="Rough-cut media composition job was queued.",
        metadata={
            "duration_seconds": duration_seconds,
            "scene_count": len(script.scenes),
            "correlation_id": correlation_id,
        },
    )

    short_job_id = str(job.id).split("-")[0]
    preview_path = build_project_storage_path(
        project.id,
        "rough-cuts",
        f"script-v{script.version_number}-rough-cut-{short_job_id}.html",
    )
    manifest_path = build_project_storage_path(
        project.id,
        "rough-cuts",
        f"script-v{script.version_number}-rough-cut-{short_job_id}-manifest.json",
    )
    subtitle_path = build_project_storage_path(
        project.id,
        "subtitles",
        f"script-v{script.version_number}-rough-cut-{short_job_id}.srt",
    )
    video_path = build_project_storage_path(
        project.id,
        "rough-cuts",
        f"script-v{script.version_number}-rough-cut-{short_job_id}.mp4",
    )
    ffmpeg_command_path = build_project_storage_path(
        project.id,
        "rough-cuts",
        f"script-v{script.version_number}-rough-cut-{short_job_id}-ffmpeg-command.json",
    )

    output_asset = Asset(
        user_id=user.id,
        project_id=project.id,
        script_id=script.id,
        scene_id=None,
        generation_attempt_id=None,
        asset_type=AssetType.ROUGH_CUT,
        status=AssetStatus.PLANNED,
        provider_name=ProviderName.LOCAL_MEDIA,
        file_path=preview_path,
        mime_type="text/html",
        duration_seconds=duration_seconds,
        width=1080,
        height=1920,
    )
    db.add(output_asset)
    db.flush()

    subtitle_asset = Asset(
        user_id=user.id,
        project_id=project.id,
        script_id=script.id,
        scene_id=None,
        generation_attempt_id=None,
        asset_type=AssetType.SUBTITLE_FILE,
        status=AssetStatus.PLANNED,
        provider_name=ProviderName.LOCAL_MEDIA,
        file_path=subtitle_path,
        mime_type="application/x-subrip",
        duration_seconds=duration_seconds,
    )
    db.add(subtitle_asset)
    db.flush()

    job.payload_json = {
        **job.payload_json,
        "output_asset_id": str(output_asset.id),
        "subtitle_asset_id": str(subtitle_asset.id),
        "preview_path": preview_path,
        "manifest_path": manifest_path,
        "subtitle_path": subtitle_path,
        "video_path": video_path,
        "ffmpeg_command_path": ffmpeg_command_path,
    }
    db.add(job)
    db.commit()
    db.refresh(job)
    emit_background_job_event(
        job,
        event_type="job_queued",
        publish_to_worker_queue=True,
        metadata={"queue_reason": "rough_cut"},
    )
    return job


def queue_final_export_job(
    db: Session,
    *,
    user: User,
    project: Project,
    script: ProjectScript,
) -> BackgroundJob:
    _validate_final_export_queue(db, project, script)
    _ensure_no_active_final_export_job(db, project, script)

    rough_cut_asset = _get_latest_ready_rough_cut_asset(db, script)
    if rough_cut_asset is None:
        raise ValueError("A ready rough-cut asset is required before final export.")

    rough_cut_job = _get_latest_completed_rough_cut_job(db, project, script)
    if rough_cut_job is None:
        raise ValueError("A completed rough-cut composition job is required before final export.")

    manifest_path = str(rough_cut_job.payload_json.get("manifest_path", "")).strip()
    subtitle_path = str(rough_cut_job.payload_json.get("subtitle_path", "")).strip()
    if not manifest_path or not subtitle_path:
        raise ValueError(
            "The latest rough-cut job is missing manifest or subtitle outputs for final export."
        )

    source_video_asset = _get_latest_ready_rough_cut_video_asset(db, script)
    duration_seconds = rough_cut_asset.duration_seconds or sum(
        scene.estimated_duration_seconds for scene in script.scenes
    )
    correlation_id = str(uuid4())
    job = BackgroundJob(
        user_id=user.id,
        project_id=project.id,
        script_id=script.id,
        job_type=BackgroundJobType.FINAL_EXPORT,
        provider_name=ProviderName.LOCAL_MEDIA,
        state=BackgroundJobState.QUEUED,
        payload_json={
            "script_id": str(script.id),
            "script_version": script.version_number,
            "scene_count": len(script.scenes),
            "rough_cut_asset_id": str(rough_cut_asset.id),
            "source_video_asset_id": (
                str(source_video_asset.id) if source_video_asset is not None else None
            ),
            "source_video_path": source_video_asset.file_path if source_video_asset else None,
            "manifest_path": manifest_path,
            "subtitle_path": subtitle_path,
            "export_profile": "final_cut_v1",
            "correlation_id": correlation_id,
        },
    )
    db.add(job)
    db.flush()
    create_job_log(
        db,
        job,
        event_type="job_queued",
        message="Final-export media job was queued.",
        metadata={
            "scene_count": len(script.scenes),
            "rough_cut_asset_id": str(rough_cut_asset.id),
            "source_video_asset_id": (
                str(source_video_asset.id) if source_video_asset is not None else None
            ),
            "correlation_id": correlation_id,
        },
    )

    short_job_id = str(job.id).split("-")[0]
    video_path = build_project_storage_path(
        project.id,
        "final-exports",
        f"script-v{script.version_number}-final-export-{short_job_id}.mp4",
    )
    ffmpeg_command_path = build_project_storage_path(
        project.id,
        "final-exports",
        f"script-v{script.version_number}-final-export-{short_job_id}-ffmpeg-command.json",
    )

    output_asset = Asset(
        user_id=user.id,
        project_id=project.id,
        script_id=script.id,
        scene_id=None,
        generation_attempt_id=None,
        asset_type=AssetType.FINAL_VIDEO,
        status=AssetStatus.PLANNED,
        provider_name=ProviderName.LOCAL_MEDIA,
        file_path=video_path,
        mime_type="video/mp4",
        duration_seconds=duration_seconds,
        width=1080,
        height=1920,
    )
    db.add(output_asset)
    db.flush()

    job.payload_json = {
        **job.payload_json,
        "output_asset_id": str(output_asset.id),
        "video_path": video_path,
        "ffmpeg_command_path": ffmpeg_command_path,
        "rough_cut_job_id": str(rough_cut_job.id),
    }
    db.add(job)
    db.commit()
    db.refresh(job)
    emit_background_job_event(
        job,
        event_type="job_queued",
        publish_to_worker_queue=True,
        metadata={"queue_reason": "final_export"},
    )
    return job


def _validate_rough_cut_queue(
    db: Session,
    project: Project,
    script: ProjectScript,
) -> None:
    if project.status != ProjectStatus.ASSET_PENDING_APPROVAL:
        raise ValueError(
            "Rough cuts can only be queued after generated assets are ready for review."
        )

    if script.project_id != project.id:
        raise ValueError("The selected script does not belong to this project.")

    if not has_approved_asset_review(db, project, script):
        raise ValueError("Approve the current asset set before queueing a rough cut.")

    ready_assets = _list_ready_script_assets(db, script)
    if not any(asset.asset_type == AssetType.NARRATION_AUDIO for asset in ready_assets):
        raise ValueError("A ready narration asset is required before composing a rough cut.")

    visual_scene_ids = {
        asset.scene_id for asset in ready_assets if asset.asset_type in VISUAL_ASSET_TYPES
    }
    missing_scene_orders = [
        scene.scene_order for scene in script.scenes if scene.id not in visual_scene_ids
    ]
    if missing_scene_orders:
        missing = ", ".join(str(scene_order) for scene_order in missing_scene_orders)
        raise ValueError(
            f"Every scene needs a ready visual before rough-cut composition. Missing: {missing}."
        )


def _validate_final_export_queue(
    db: Session,
    project: Project,
    script: ProjectScript,
) -> None:
    if project.status not in {
        ProjectStatus.ROUGH_CUT_READY,
        ProjectStatus.FINAL_PENDING_APPROVAL,
    }:
        raise ValueError(
            "Final exports can only be queued after a rough cut is ready for final review."
        )

    if script.project_id != project.id:
        raise ValueError("The selected script does not belong to this project.")

    if _get_latest_ready_rough_cut_asset(db, script) is None:
        raise ValueError("A ready rough-cut asset is required before final export.")

    if _get_latest_completed_rough_cut_job(db, project, script) is None:
        raise ValueError("A completed rough-cut composition job is required before final export.")


def _ensure_no_active_rough_cut_job(
    db: Session,
    project: Project,
    script: ProjectScript,
) -> None:
    statement = select(BackgroundJob).where(
        BackgroundJob.project_id == project.id,
        BackgroundJob.script_id == script.id,
        BackgroundJob.job_type == BackgroundJobType.COMPOSE_ROUGH_CUT,
        BackgroundJob.state.in_(ACTIVE_JOB_STATES),
    )
    existing_job = db.scalar(statement)
    if existing_job is not None:
        raise ValueError("An active rough-cut composition job already exists for this script.")


def _ensure_no_active_final_export_job(
    db: Session,
    project: Project,
    script: ProjectScript,
) -> None:
    statement = select(BackgroundJob).where(
        BackgroundJob.project_id == project.id,
        BackgroundJob.script_id == script.id,
        BackgroundJob.job_type == BackgroundJobType.FINAL_EXPORT,
        BackgroundJob.state.in_(ACTIVE_JOB_STATES),
    )
    existing_job = db.scalar(statement)
    if existing_job is not None:
        raise ValueError("An active final-export job already exists for this script.")


def _list_ready_script_assets(db: Session, script: ProjectScript) -> list[Asset]:
    statement = (
        select(Asset)
        .where(
            Asset.script_id == script.id,
            Asset.status == AssetStatus.READY,
        )
        .order_by(desc(Asset.updated_at), desc(Asset.created_at))
    )
    return list(db.scalars(statement))


def _get_latest_ready_rough_cut_asset(db: Session, script: ProjectScript) -> Asset | None:
    statement = (
        select(Asset)
        .where(
            Asset.script_id == script.id,
            Asset.asset_type == AssetType.ROUGH_CUT,
            Asset.status == AssetStatus.READY,
        )
        .order_by(desc(Asset.updated_at), desc(Asset.created_at))
    )
    return db.scalar(statement)


def _get_latest_ready_rough_cut_video_asset(db: Session, script: ProjectScript) -> Asset | None:
    statement = (
        select(Asset)
        .where(
            Asset.script_id == script.id,
            Asset.asset_type == AssetType.ROUGH_CUT,
            Asset.status == AssetStatus.READY,
            Asset.mime_type == "video/mp4",
        )
        .order_by(desc(Asset.updated_at), desc(Asset.created_at))
    )
    return db.scalar(statement)


def _get_latest_completed_rough_cut_job(
    db: Session,
    project: Project,
    script: ProjectScript,
) -> BackgroundJob | None:
    statement = (
        select(BackgroundJob)
        .where(
            BackgroundJob.project_id == project.id,
            BackgroundJob.script_id == script.id,
            BackgroundJob.job_type == BackgroundJobType.COMPOSE_ROUGH_CUT,
            BackgroundJob.state == BackgroundJobState.COMPLETED,
        )
        .order_by(desc(BackgroundJob.updated_at), desc(BackgroundJob.created_at))
    )
    return db.scalar(statement)
