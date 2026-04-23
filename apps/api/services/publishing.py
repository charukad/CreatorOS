from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.models.publish_job import PublishJob
from apps.api.models.user import User
from apps.api.schemas.content_workflow import (
    ManualPublishCompleteRequest,
    PublishJobMetadataUpdateRequest,
    PublishJobPrepareRequest,
    PublishJobScheduleRequest,
)
from apps.api.schemas.enums import (
    ApprovalDecision,
    ApprovalStage,
    ApprovalTargetType,
    AssetStatus,
    AssetType,
    BackgroundJobState,
    BackgroundJobType,
    ProjectStatus,
    PublishJobStatus,
)
from apps.api.services.approvals import create_approval_record, get_latest_stage_approval
from apps.api.services.background_jobs import create_job_log
from apps.api.services.project_events import create_project_event
from apps.api.services.storage_paths import build_project_storage_path

ACTIVE_PUBLISH_JOB_STATUSES = {
    PublishJobStatus.PENDING_APPROVAL,
    PublishJobStatus.APPROVED,
    PublishJobStatus.SCHEDULED,
}

EDITABLE_PUBLISH_JOB_STATUSES = {
    PublishJobStatus.PENDING_APPROVAL,
    PublishJobStatus.APPROVED,
}

PUBLISH_THUMBNAIL_ASSET_TYPES = {
    AssetType.THUMBNAIL,
    AssetType.SCENE_IMAGE,
}

ACTIVE_PUBLISH_EXECUTION_STATES = {
    BackgroundJobState.QUEUED,
    BackgroundJobState.RUNNING,
    BackgroundJobState.WAITING_EXTERNAL,
}


def list_project_publish_jobs(db: Session, project: Project) -> list[PublishJob]:
    statement = (
        select(PublishJob)
        .where(PublishJob.project_id == project.id)
        .order_by(desc(PublishJob.updated_at), desc(PublishJob.created_at))
    )
    return list(db.scalars(statement))


def get_owned_publish_job(db: Session, user: User, publish_job_id: UUID) -> PublishJob | None:
    statement = select(PublishJob).where(
        PublishJob.id == publish_job_id,
        PublishJob.user_id == user.id,
    )
    return db.scalar(statement)


def approve_final_video(
    db: Session,
    *,
    user: User,
    project: Project,
    script: ProjectScript,
    feedback_notes: str | None = None,
):
    final_asset = get_latest_ready_final_review_asset(db, script)
    _validate_final_approval_state(project, script, final_asset)

    approval = create_approval_record(
        db,
        user=user,
        project=project,
        target_type=ApprovalTargetType.ASSET,
        target_id=final_asset.id,
        stage=ApprovalStage.FINAL_VIDEO,
        decision=ApprovalDecision.APPROVED,
        feedback_notes=feedback_notes,
    )
    project.status = ProjectStatus.READY_TO_PUBLISH
    db.add(project)
    db.commit()
    db.refresh(approval)
    return approval


def reject_final_video(
    db: Session,
    *,
    user: User,
    project: Project,
    script: ProjectScript,
    feedback_notes: str | None = None,
):
    final_asset = get_latest_ready_final_review_asset(db, script)
    _validate_final_approval_state(project, script, final_asset)

    approval = create_approval_record(
        db,
        user=user,
        project=project,
        target_type=ApprovalTargetType.ASSET,
        target_id=final_asset.id,
        stage=ApprovalStage.FINAL_VIDEO,
        decision=ApprovalDecision.REJECTED,
        feedback_notes=feedback_notes,
    )
    project.status = ProjectStatus.ROUGH_CUT_READY
    db.add(project)
    db.commit()
    db.refresh(approval)
    return approval


def prepare_publish_job(
    db: Session,
    *,
    user: User,
    project: Project,
    script: ProjectScript,
    payload: PublishJobPrepareRequest,
) -> PublishJob:
    if project.status != ProjectStatus.READY_TO_PUBLISH:
        raise ValueError("Publish jobs can only be prepared after final video approval.")

    final_asset = get_latest_ready_final_review_asset(db, script)
    if final_asset is None:
        raise ValueError("A ready final or rough-cut asset is required before publish prep.")

    if not has_final_video_approval(db, project, final_asset):
        raise ValueError("Publish prep requires an approved final-video review.")

    if payload.idempotency_key:
        existing_job = _get_publish_job_by_idempotency_key(
            db,
            user,
            project,
            payload.idempotency_key,
        )
        if existing_job is not None:
            return existing_job

    active_job = _get_active_publish_job(db, project, script)
    if active_job is not None:
        raise ValueError("An active publish job already exists for the current script.")

    publish_job = PublishJob(
        user_id=user.id,
        project_id=project.id,
        script_id=script.id,
        final_asset_id=final_asset.id,
        platform=payload.platform,
        title=payload.title,
        description=payload.description,
        hashtags_json=payload.hashtags,
        scheduled_for=payload.scheduled_for,
        status=PublishJobStatus.PENDING_APPROVAL,
        idempotency_key=payload.idempotency_key,
        metadata_json={
            "source": "manual_publish_prep",
            "prepared_at": datetime.now(UTC).isoformat(),
        },
    )
    db.add(publish_job)
    db.flush()
    create_project_event(
        db,
        project,
        event_type="publish_job_prepared",
        title="Publish job prepared",
        description=payload.title,
        metadata={
            "publish_job_id": str(publish_job.id),
            "platform": payload.platform,
            "scheduled_for": payload.scheduled_for.isoformat()
            if payload.scheduled_for is not None
            else None,
        },
    )
    db.commit()
    db.refresh(publish_job)
    return publish_job


def approve_publish_job(
    db: Session,
    *,
    user: User,
    project: Project,
    publish_job: PublishJob,
    feedback_notes: str | None = None,
) -> PublishJob:
    if publish_job.project_id != project.id:
        raise ValueError("The selected publish job does not belong to this project.")

    if publish_job.status != PublishJobStatus.PENDING_APPROVAL:
        raise ValueError("Only pending publish jobs can be approved.")

    create_approval_record(
        db,
        user=user,
        project=project,
        target_type=ApprovalTargetType.PUBLISH_JOB,
        target_id=publish_job.id,
        stage=ApprovalStage.PUBLISH,
        decision=ApprovalDecision.APPROVED,
        feedback_notes=feedback_notes,
    )
    publish_job.status = PublishJobStatus.APPROVED
    db.add(publish_job)
    create_project_event(
        db,
        project,
        event_type="publish_job_approved",
        title="Publish job approved",
        description=feedback_notes,
        metadata={"publish_job_id": str(publish_job.id), "platform": publish_job.platform},
    )
    db.commit()
    db.refresh(publish_job)
    return publish_job


def update_publish_job_metadata(
    db: Session,
    *,
    user: User,
    project: Project,
    publish_job: PublishJob,
    payload: PublishJobMetadataUpdateRequest,
) -> PublishJob:
    if publish_job.project_id != project.id:
        raise ValueError("The selected publish job does not belong to this project.")

    if publish_job.status not in EDITABLE_PUBLISH_JOB_STATUSES:
        raise ValueError("Publish metadata can only be edited before scheduling or publishing.")

    update_fields = payload.model_dump(exclude_unset=True)
    if not update_fields:
        return publish_job

    changed_fields: list[str] = []
    metadata = dict(publish_job.metadata_json or {})
    previous_status = publish_job.status

    if "title" in update_fields and payload.title != publish_job.title:
        publish_job.title = _require_text(payload.title, "Title")
        changed_fields.append("title")

    if "description" in update_fields and payload.description != publish_job.description:
        publish_job.description = _require_text(payload.description, "Description")
        changed_fields.append("description")

    if "hashtags" in update_fields:
        normalized_hashtags = _normalize_hashtags(payload.hashtags or [])
        if normalized_hashtags != publish_job.hashtags_json:
            publish_job.hashtags_json = normalized_hashtags
            changed_fields.append("hashtags")

    if "scheduled_for" in update_fields and payload.scheduled_for != publish_job.scheduled_for:
        publish_job.scheduled_for = payload.scheduled_for
        changed_fields.append("scheduled_for")

    if "thumbnail_asset_id" in update_fields:
        thumbnail_asset_id = _validate_thumbnail_asset(
            db,
            user=user,
            project=project,
            publish_job=publish_job,
            thumbnail_asset_id=payload.thumbnail_asset_id,
        )
        if thumbnail_asset_id != metadata.get("thumbnail_asset_id"):
            if thumbnail_asset_id is None:
                metadata.pop("thumbnail_asset_id", None)
            else:
                metadata["thumbnail_asset_id"] = thumbnail_asset_id
            changed_fields.append("thumbnail_asset_id")

    if "platform_settings" in update_fields:
        if payload.platform_settings is None:
            if "platform_settings" in metadata:
                metadata.pop("platform_settings", None)
                changed_fields.append("platform_settings")
        elif payload.platform_settings != metadata.get("platform_settings"):
            metadata["platform_settings"] = payload.platform_settings
            changed_fields.append("platform_settings")

    change_notes = payload.change_notes.strip() if payload.change_notes else None
    if change_notes is not None:
        changed_fields.append("change_notes")

    if not changed_fields:
        return publish_job

    metadata_revision = {
        "changed_at": datetime.now(UTC).isoformat(),
        "changed_fields": changed_fields,
        "change_notes": change_notes,
        "previous_status": previous_status.value,
    }
    metadata["last_metadata_update"] = metadata_revision
    metadata["metadata_revision_history"] = [
        *list(metadata.get("metadata_revision_history", []))[-19:],
        metadata_revision,
    ]

    requires_reapproval = previous_status == PublishJobStatus.APPROVED and any(
        field != "change_notes" for field in changed_fields
    )
    if requires_reapproval:
        publish_job.status = PublishJobStatus.PENDING_APPROVAL

    publish_job.metadata_json = metadata
    db.add(publish_job)
    create_project_event(
        db,
        project,
        event_type="publish_metadata_updated",
        title="Publish metadata updated",
        description=change_notes,
        level="warning" if requires_reapproval else "info",
        metadata={
            "publish_job_id": str(publish_job.id),
            "platform": publish_job.platform,
            "changed_fields": changed_fields,
            "previous_status": previous_status.value,
            "requires_reapproval": requires_reapproval,
        },
    )
    db.commit()
    db.refresh(publish_job)
    return publish_job


def schedule_publish_job(
    db: Session,
    *,
    project: Project,
    publish_job: PublishJob,
    payload: PublishJobScheduleRequest,
) -> PublishJob:
    if publish_job.project_id != project.id:
        raise ValueError("The selected publish job does not belong to this project.")

    if publish_job.status == PublishJobStatus.SCHEDULED:
        if _same_datetime(publish_job.scheduled_for, payload.scheduled_for):
            return publish_job
        raise ValueError("Scheduled publish jobs cannot be rescheduled without manual review.")

    if publish_job.status != PublishJobStatus.APPROVED:
        raise ValueError("Only approved publish jobs can be scheduled.")

    publish_job.scheduled_for = payload.scheduled_for
    publish_job.status = PublishJobStatus.SCHEDULED
    project.status = ProjectStatus.SCHEDULED
    db.add(publish_job)
    db.add(project)
    create_project_event(
        db,
        project,
        event_type="publish_job_scheduled",
        title="Publish job scheduled",
        metadata={
            "publish_job_id": str(publish_job.id),
            "platform": publish_job.platform,
            "scheduled_for": payload.scheduled_for.isoformat(),
        },
    )
    db.commit()
    db.refresh(publish_job)
    return publish_job


def queue_publish_content_job(
    db: Session,
    *,
    project: Project,
    publish_job: PublishJob,
) -> BackgroundJob:
    if publish_job.project_id != project.id:
        raise ValueError("The selected publish job does not belong to this project.")

    if publish_job.status not in {PublishJobStatus.APPROVED, PublishJobStatus.SCHEDULED}:
        raise ValueError("Only approved or scheduled publish jobs can be queued for publishing.")

    final_asset = db.get(Asset, publish_job.final_asset_id)
    if final_asset is None or final_asset.project_id != project.id:
        raise ValueError("Publish handoff requires the linked final asset.")

    if final_asset.status != AssetStatus.READY:
        raise ValueError("Publish handoff requires the linked final asset to be ready.")

    _ensure_no_active_publish_content_job(db, publish_job)

    short_publish_job_id = str(publish_job.id).split("-")[0]
    correlation_id = str(uuid4())
    handoff_path = build_project_storage_path(
        project.id,
        "publish",
        f"{publish_job.platform}-handoff-{short_publish_job_id}.json",
    )
    job = BackgroundJob(
        user_id=publish_job.user_id,
        project_id=publish_job.project_id,
        script_id=publish_job.script_id,
        job_type=BackgroundJobType.PUBLISH_CONTENT,
        provider_name=None,
        state=BackgroundJobState.QUEUED,
        payload_json={
            "job_type": BackgroundJobType.PUBLISH_CONTENT.value,
            "adapter_name": "manual_publish_handoff",
            "publish_job_id": str(publish_job.id),
            "approved_publish_job_state": publish_job.status.value,
            "platform": publish_job.platform,
            "final_asset_id": str(publish_job.final_asset_id),
            "scheduled_for": (
                publish_job.scheduled_for.isoformat()
                if publish_job.scheduled_for is not None
                else None
            ),
            "handoff_path": handoff_path,
            "correlation_id": correlation_id,
        },
    )
    db.add(job)
    db.flush()
    create_job_log(
        db,
        job,
        event_type="job_queued",
        message="Manual publish handoff job was queued.",
        metadata={
            "adapter_name": "manual_publish_handoff",
            "publish_job_id": str(publish_job.id),
            "platform": publish_job.platform,
            "handoff_path": handoff_path,
            "correlation_id": correlation_id,
        },
    )
    create_project_event(
        db,
        project,
        event_type="publish_handoff_queued",
        title="Publish handoff queued",
        description=publish_job.title,
        metadata={
            "background_job_id": str(job.id),
            "publish_job_id": str(publish_job.id),
            "platform": publish_job.platform,
            "handoff_path": handoff_path,
        },
    )
    db.commit()
    db.refresh(job)
    return job


def mark_publish_job_published(
    db: Session,
    *,
    project: Project,
    publish_job: PublishJob,
    payload: ManualPublishCompleteRequest,
) -> PublishJob:
    if publish_job.project_id != project.id:
        raise ValueError("The selected publish job does not belong to this project.")

    if publish_job.status not in {PublishJobStatus.APPROVED, PublishJobStatus.SCHEDULED}:
        raise ValueError("Only approved or scheduled publish jobs can be marked as published.")

    publish_job.status = PublishJobStatus.PUBLISHED
    publish_job.external_post_id = payload.external_post_id
    publish_job.manual_publish_notes = payload.manual_publish_notes
    project.status = ProjectStatus.PUBLISHED
    db.add(publish_job)
    db.add(project)
    create_project_event(
        db,
        project,
        event_type="publish_job_marked_published",
        title="Publish job marked published",
        description=payload.manual_publish_notes,
        metadata={
            "publish_job_id": str(publish_job.id),
            "platform": publish_job.platform,
            "external_post_id": payload.external_post_id,
        },
    )
    _complete_publish_content_jobs(db, publish_job)
    db.commit()
    db.refresh(publish_job)
    return publish_job


def has_final_video_approval(db: Session, project: Project, final_asset: Asset) -> bool:
    approval = get_latest_stage_approval(
        db,
        project,
        stage=ApprovalStage.FINAL_VIDEO,
        target_id=final_asset.id,
    )
    return approval is not None and approval.decision == ApprovalDecision.APPROVED


def has_scheduled_publish_job(db: Session, project: Project) -> bool:
    statement = select(PublishJob).where(
        PublishJob.project_id == project.id,
        PublishJob.status == PublishJobStatus.SCHEDULED,
    )
    return db.scalar(statement) is not None


def _same_datetime(left: datetime | None, right: datetime | None) -> bool:
    if left is None or right is None:
        return left is right
    return _as_aware_datetime(left) == _as_aware_datetime(right)


def _as_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def has_published_publish_job(db: Session, project: Project) -> bool:
    statement = select(PublishJob).where(
        PublishJob.project_id == project.id,
        PublishJob.status == PublishJobStatus.PUBLISHED,
    )
    return db.scalar(statement) is not None


def _validate_final_approval_state(
    project: Project,
    script: ProjectScript,
    final_asset: Asset | None,
) -> None:
    if project.status != ProjectStatus.FINAL_PENDING_APPROVAL:
        raise ValueError("Final video review is only available in final approval.")

    if script.project_id != project.id:
        raise ValueError("The selected script does not belong to this project.")

    if final_asset is None:
        raise ValueError("A ready rough-cut or final video asset is required for final review.")


def get_latest_ready_final_review_asset(db: Session, script: ProjectScript) -> Asset | None:
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


def _get_publish_job_by_idempotency_key(
    db: Session,
    user: User,
    project: Project,
    idempotency_key: str,
) -> PublishJob | None:
    statement = select(PublishJob).where(
        PublishJob.user_id == user.id,
        PublishJob.project_id == project.id,
        PublishJob.idempotency_key == idempotency_key,
    )
    return db.scalar(statement)


def _get_active_publish_job(
    db: Session,
    project: Project,
    script: ProjectScript,
) -> PublishJob | None:
    statement = select(PublishJob).where(
        PublishJob.project_id == project.id,
        PublishJob.script_id == script.id,
        PublishJob.status.in_(ACTIVE_PUBLISH_JOB_STATUSES),
    )
    return db.scalar(statement)


def _ensure_no_active_publish_content_job(db: Session, publish_job: PublishJob) -> None:
    statement = select(BackgroundJob).where(
        BackgroundJob.project_id == publish_job.project_id,
        BackgroundJob.script_id == publish_job.script_id,
        BackgroundJob.job_type == BackgroundJobType.PUBLISH_CONTENT,
        BackgroundJob.state.in_(ACTIVE_PUBLISH_EXECUTION_STATES),
        BackgroundJob.payload_json["publish_job_id"].as_string() == str(publish_job.id),
    )
    existing_job = db.scalar(statement)
    if existing_job is not None:
        raise ValueError("An active publish handoff job already exists for this publish job.")


def _complete_publish_content_jobs(db: Session, publish_job: PublishJob) -> None:
    statement = select(BackgroundJob).where(
        BackgroundJob.project_id == publish_job.project_id,
        BackgroundJob.script_id == publish_job.script_id,
        BackgroundJob.job_type == BackgroundJobType.PUBLISH_CONTENT,
        BackgroundJob.state.in_(ACTIVE_PUBLISH_EXECUTION_STATES),
        BackgroundJob.payload_json["publish_job_id"].as_string() == str(publish_job.id),
    )
    now = datetime.now(UTC)
    for job in db.scalars(statement):
        job.state = BackgroundJobState.COMPLETED
        job.progress_percent = 100
        job.finished_at = now
        job.error_message = None
        db.add(job)
        create_job_log(
            db,
            job,
            event_type="publish_handoff_completed",
            message="Manual publish was confirmed; publish handoff job is complete.",
            metadata={
                "publish_job_id": str(publish_job.id),
                "external_post_id": publish_job.external_post_id,
            },
        )


def _require_text(value: str | None, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} cannot be cleared.")

    return value


def _normalize_hashtags(hashtags: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw_hashtag in hashtags:
        hashtag = raw_hashtag.strip()
        if not hashtag:
            continue
        if not hashtag.startswith("#"):
            hashtag = f"#{hashtag}"
        if hashtag not in normalized:
            normalized.append(hashtag)

    return normalized


def _validate_thumbnail_asset(
    db: Session,
    *,
    user: User,
    project: Project,
    publish_job: PublishJob,
    thumbnail_asset_id: UUID | None,
) -> str | None:
    if thumbnail_asset_id is None:
        return None

    statement = select(Asset).where(
        Asset.id == thumbnail_asset_id,
        Asset.user_id == user.id,
        Asset.project_id == project.id,
    )
    thumbnail_asset = db.scalar(statement)
    if thumbnail_asset is None:
        raise ValueError("Thumbnail asset not found for this project.")

    if thumbnail_asset.asset_type not in PUBLISH_THUMBNAIL_ASSET_TYPES:
        raise ValueError("Publish thumbnails must be ready thumbnail or scene image assets.")

    if thumbnail_asset.script_id != publish_job.script_id:
        raise ValueError("Publish thumbnails must belong to the publish job script.")

    if thumbnail_asset.status != AssetStatus.READY:
        raise ValueError("Publish thumbnails must be ready before they can be selected.")

    return str(thumbnail_asset.id)
