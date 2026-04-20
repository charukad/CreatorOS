from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.asset import Asset
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.models.publish_job import PublishJob
from apps.api.models.user import User
from apps.api.schemas.content_workflow import (
    ManualPublishCompleteRequest,
    PublishJobPrepareRequest,
    PublishJobScheduleRequest,
)
from apps.api.schemas.enums import (
    ApprovalDecision,
    ApprovalStage,
    ApprovalTargetType,
    AssetStatus,
    AssetType,
    ProjectStatus,
    PublishJobStatus,
)
from apps.api.services.approvals import create_approval_record, get_latest_stage_approval
from apps.api.services.project_events import create_project_event

ACTIVE_PUBLISH_JOB_STATUSES = {
    PublishJobStatus.PENDING_APPROVAL,
    PublishJobStatus.APPROVED,
    PublishJobStatus.SCHEDULED,
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


def schedule_publish_job(
    db: Session,
    *,
    project: Project,
    publish_job: PublishJob,
    payload: PublishJobScheduleRequest,
) -> PublishJob:
    if publish_job.project_id != project.id:
        raise ValueError("The selected publish job does not belong to this project.")

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
