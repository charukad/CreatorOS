from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import asc, desc, or_, select
from sqlalchemy.orm import Session, selectinload

from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.generation_attempt import GenerationAttempt
from apps.api.models.job_log import JobLog
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.models.user import User
from apps.api.schemas.enums import (
    AssetStatus,
    AssetType,
    BackgroundJobState,
    BackgroundJobType,
    ProjectStatus,
)
from apps.api.services.assets import can_enter_asset_review, has_ready_rough_cut
from apps.api.services.queue_events import emit_background_job_event

CLAIMABLE_BROWSER_JOB_TYPES = (
    BackgroundJobType.GENERATE_AUDIO_BROWSER,
    BackgroundJobType.GENERATE_VISUALS_BROWSER,
)
CLAIMABLE_MEDIA_JOB_TYPES = (
    BackgroundJobType.COMPOSE_ROUGH_CUT,
    BackgroundJobType.FINAL_EXPORT,
)
CLAIMABLE_PUBLISH_JOB_TYPES = (BackgroundJobType.PUBLISH_CONTENT,)
CLAIMABLE_ANALYTICS_JOB_TYPES = (BackgroundJobType.SYNC_ANALYTICS,)
ACTIVE_JOB_STATES = {
    BackgroundJobState.QUEUED,
    BackgroundJobState.RUNNING,
    BackgroundJobState.WAITING_EXTERNAL,
}
CANCELLABLE_JOB_STATES = {
    BackgroundJobState.QUEUED,
    BackgroundJobState.WAITING_EXTERNAL,
}
RETRYABLE_JOB_STATES = {
    BackgroundJobState.FAILED,
    BackgroundJobState.CANCELLED,
}
RETRY_POLICY_MAX_ATTEMPTS = {
    BackgroundJobType.GENERATE_AUDIO_BROWSER: 4,
    BackgroundJobType.GENERATE_VISUALS_BROWSER: 4,
    BackgroundJobType.COMPOSE_ROUGH_CUT: 3,
    BackgroundJobType.FINAL_EXPORT: 3,
    BackgroundJobType.PUBLISH_CONTENT: 2,
    BackgroundJobType.SYNC_ANALYTICS: 2,
}
RESUMABLE_JOB_TYPES = {*CLAIMABLE_BROWSER_JOB_TYPES, *CLAIMABLE_MEDIA_JOB_TYPES}
RESETTABLE_ASSET_STATUSES = {
    AssetStatus.PLANNED,
    AssetStatus.GENERATING,
    AssetStatus.READY,
    AssetStatus.FAILED,
}


def claim_next_browser_job(db: Session) -> BackgroundJob | None:
    statement = (
        select(BackgroundJob)
        .options(
            selectinload(BackgroundJob.generation_attempts).selectinload(GenerationAttempt.assets),
            selectinload(BackgroundJob.job_logs),
        )
        .where(
            BackgroundJob.job_type.in_(CLAIMABLE_BROWSER_JOB_TYPES),
            BackgroundJob.state == BackgroundJobState.QUEUED,
        )
        .order_by(asc(BackgroundJob.created_at))
    )
    job = db.scalar(statement)
    if job is None:
        return None

    now = datetime.now(UTC)
    job.state = BackgroundJobState.RUNNING
    job.attempts += 1
    job.progress_percent = max(job.progress_percent, 5)
    job.started_at = now
    job.error_message = None
    db.add(job)
    create_job_log(
        db,
        job,
        event_type="job_claimed",
        message="Browser worker claimed the job.",
        metadata={"worker_type": "browser"},
    )
    db.commit()
    db.refresh(job)
    emit_background_job_event(job, event_type="job_claimed")
    return get_background_job(db, job.id)


def claim_next_media_job(db: Session) -> BackgroundJob | None:
    statement = (
        select(BackgroundJob)
        .where(
            BackgroundJob.job_type.in_(CLAIMABLE_MEDIA_JOB_TYPES),
            BackgroundJob.state == BackgroundJobState.QUEUED,
        )
        .order_by(asc(BackgroundJob.created_at))
    )
    job = db.scalar(statement)
    if job is None:
        return None

    now = datetime.now(UTC)
    job.state = BackgroundJobState.RUNNING
    job.attempts += 1
    job.progress_percent = max(job.progress_percent, 5)
    job.started_at = now
    job.error_message = None
    db.add(job)
    create_job_log(
        db,
        job,
        event_type="job_claimed",
        message="Media worker claimed the job.",
        metadata={"worker_type": "media"},
    )
    db.commit()
    db.refresh(job)
    emit_background_job_event(job, event_type="job_claimed")
    return get_background_job(db, job.id)


def claim_next_publish_job(db: Session) -> BackgroundJob | None:
    statement = (
        select(BackgroundJob)
        .where(
            BackgroundJob.job_type.in_(CLAIMABLE_PUBLISH_JOB_TYPES),
            BackgroundJob.state == BackgroundJobState.QUEUED,
        )
        .order_by(asc(BackgroundJob.created_at))
    )
    job = db.scalar(statement)
    if job is None:
        return None

    now = datetime.now(UTC)
    job.state = BackgroundJobState.RUNNING
    job.attempts += 1
    job.progress_percent = max(job.progress_percent, 10)
    job.started_at = now
    job.error_message = None
    db.add(job)
    create_job_log(
        db,
        job,
        event_type="job_claimed",
        message="Publisher worker claimed the job.",
        metadata={"worker_type": "publisher"},
    )
    db.commit()
    db.refresh(job)
    emit_background_job_event(job, event_type="job_claimed")
    return get_background_job(db, job.id)


def claim_next_analytics_job(db: Session) -> BackgroundJob | None:
    statement = (
        select(BackgroundJob)
        .where(
            BackgroundJob.job_type.in_(CLAIMABLE_ANALYTICS_JOB_TYPES),
            BackgroundJob.state == BackgroundJobState.QUEUED,
        )
        .order_by(asc(BackgroundJob.created_at))
    )
    job = db.scalar(statement)
    if job is None:
        return None

    now = datetime.now(UTC)
    job.state = BackgroundJobState.RUNNING
    job.attempts += 1
    job.progress_percent = max(job.progress_percent, 10)
    job.started_at = now
    job.error_message = None
    db.add(job)
    create_job_log(
        db,
        job,
        event_type="job_claimed",
        message="Analytics worker claimed the job.",
        metadata={"worker_type": "analytics"},
    )
    db.commit()
    db.refresh(job)
    emit_background_job_event(job, event_type="job_claimed")
    return get_background_job(db, job.id)


def get_background_job(db: Session, job_id: object) -> BackgroundJob | None:
    statement = (
        select(BackgroundJob)
        .options(
            selectinload(BackgroundJob.generation_attempts).selectinload(GenerationAttempt.assets),
            selectinload(BackgroundJob.job_logs),
        )
        .where(BackgroundJob.id == job_id)
    )
    return db.scalar(statement)


def get_owned_background_job(db: Session, user: User, job_id: UUID) -> BackgroundJob | None:
    statement = (
        select(BackgroundJob)
        .options(
            selectinload(BackgroundJob.generation_attempts).selectinload(GenerationAttempt.assets),
            selectinload(BackgroundJob.job_logs),
        )
        .where(BackgroundJob.id == job_id, BackgroundJob.user_id == user.id)
    )
    return db.scalar(statement)


def list_job_related_assets(db: Session, job: BackgroundJob) -> list[Asset]:
    attempt_ids = [attempt.id for attempt in job.generation_attempts]
    payload_asset_ids = _extract_payload_asset_ids(job.payload_json)
    filters = []

    if attempt_ids:
        filters.append(Asset.generation_attempt_id.in_(attempt_ids))
    if payload_asset_ids:
        filters.append(Asset.id.in_(payload_asset_ids))

    if not filters:
        return []

    statement = select(Asset).where(or_(*filters)).order_by(asc(Asset.created_at), asc(Asset.id))
    return list(db.scalars(statement))


def list_job_logs(db: Session, job: BackgroundJob) -> list[JobLog]:
    statement = (
        select(JobLog)
        .where(JobLog.background_job_id == job.id)
        .order_by(asc(JobLog.created_at), asc(JobLog.id))
    )
    return list(db.scalars(statement))


def list_project_job_logs(db: Session, project: Project, *, limit: int = 50) -> list[JobLog]:
    statement = (
        select(JobLog)
        .where(JobLog.project_id == project.id)
        .order_by(desc(JobLog.created_at), desc(JobLog.id))
        .limit(limit)
    )
    return list(db.scalars(statement))


def create_job_log(
    db: Session,
    job: BackgroundJob,
    *,
    event_type: str,
    message: str,
    level: str = "info",
    attempt: GenerationAttempt | None = None,
    metadata: dict[str, object] | None = None,
) -> JobLog:
    now = datetime.now(UTC)
    log = JobLog(
        user_id=job.user_id,
        project_id=job.project_id,
        script_id=job.script_id,
        background_job_id=job.id,
        generation_attempt_id=attempt.id if attempt is not None else None,
        level=level,
        event_type=event_type,
        message=message,
        metadata_json=metadata or {},
        created_at=now,
        updated_at=now,
    )
    db.add(log)
    return log


def cancel_background_job(
    db: Session,
    job: BackgroundJob,
    *,
    reason: str = "Cancelled by user.",
) -> BackgroundJob:
    if job.state not in CANCELLABLE_JOB_STATES:
        raise ValueError(
            "Only queued or waiting-external jobs can be cancelled safely. "
            "Running or completed jobs need worker-aware recovery."
        )

    now = datetime.now(UTC)
    job.state = BackgroundJobState.CANCELLED
    job.finished_at = now
    job.error_message = reason
    db.add(job)
    create_job_log(
        db,
        job,
        event_type="job_cancelled",
        message=reason,
        level="warning",
    )

    for attempt in job.generation_attempts:
        if attempt.state == BackgroundJobState.COMPLETED:
            continue
        attempt.state = BackgroundJobState.CANCELLED
        attempt.finished_at = now
        attempt.error_message = reason
        db.add(attempt)
        for asset in attempt.assets:
            _mark_unfinished_asset_failed(db, asset)

    for asset in _list_payload_assets(db, job):
        _mark_unfinished_asset_failed(db, asset)

    db.commit()
    refreshed_job = get_background_job(db, job.id) or job
    emit_background_job_event(refreshed_job, event_type="job_cancelled")
    return refreshed_job


def retry_background_job(db: Session, job: BackgroundJob) -> BackgroundJob:
    if job.state not in RETRYABLE_JOB_STATES:
        raise ValueError("Only failed or cancelled jobs can be retried.")

    _ensure_job_type_supports_manual_retry(job)
    _ensure_retry_budget_available(job)
    _ensure_no_other_active_job(db, job)
    previous_state = job.state.value

    job.state = BackgroundJobState.QUEUED
    job.progress_percent = 0
    job.error_message = None
    job.started_at = None
    job.finished_at = None
    db.add(job)
    max_attempts = RETRY_POLICY_MAX_ATTEMPTS[job.job_type]
    create_job_log(
        db,
        job,
        event_type="job_retried",
        message="Job was reset to queued for another attempt.",
        metadata={
            "previous_state": previous_state,
            "attempts_used": job.attempts,
            "max_attempts": max_attempts,
            "remaining_attempts": max(max_attempts - job.attempts, 0),
        },
    )

    for attempt in job.generation_attempts:
        attempt.state = BackgroundJobState.QUEUED
        attempt.error_message = None
        attempt.started_at = None
        attempt.finished_at = None
        db.add(attempt)
        for asset in attempt.assets:
            _reset_asset_for_retry(db, asset)

    for asset in _list_payload_assets(db, job):
        _reset_asset_for_retry(db, asset)

    db.commit()
    refreshed_job = get_background_job(db, job.id) or job
    emit_background_job_event(
        refreshed_job,
        event_type="job_retried",
        publish_to_worker_queue=True,
    )
    return refreshed_job


def resume_stale_running_job(
    db: Session,
    job: BackgroundJob,
    *,
    stale_after_minutes: int = 30,
) -> BackgroundJob:
    if job.job_type not in RESUMABLE_JOB_TYPES:
        raise ValueError("Only browser and media jobs can be manually resumed.")

    if job.state != BackgroundJobState.RUNNING:
        raise ValueError("Only running jobs can be resumed.")

    _ensure_job_is_stale(job, stale_after_minutes=stale_after_minutes)
    _ensure_no_other_active_job(db, job)
    previous_updated_at = _as_aware_datetime(job.updated_at)

    job.state = BackgroundJobState.QUEUED
    job.progress_percent = 0
    job.error_message = None
    job.started_at = None
    job.finished_at = None
    db.add(job)
    create_job_log(
        db,
        job,
        event_type="job_resumed",
        message="Stale running job was reset to queued for worker resume.",
        level="warning",
        metadata={
            "previous_state": BackgroundJobState.RUNNING.value,
            "previous_updated_at": previous_updated_at.isoformat(),
            "stale_after_minutes": stale_after_minutes,
        },
    )

    for attempt in job.generation_attempts:
        if attempt.state == BackgroundJobState.COMPLETED:
            continue
        attempt.state = BackgroundJobState.QUEUED
        attempt.error_message = None
        attempt.started_at = None
        attempt.finished_at = None
        db.add(attempt)
        for asset in attempt.assets:
            _reset_unfinished_asset_for_resume(db, asset)

    for asset in _list_payload_assets(db, job):
        _reset_unfinished_asset_for_resume(db, asset)

    db.commit()
    refreshed_job = get_background_job(db, job.id) or job
    emit_background_job_event(
        refreshed_job,
        event_type="job_resumed",
        publish_to_worker_queue=True,
    )
    return refreshed_job


def mark_job_manual_intervention_required(
    db: Session,
    job: BackgroundJob,
    *,
    reason: str,
) -> BackgroundJob:
    if job.state == BackgroundJobState.COMPLETED:
        raise ValueError("Completed jobs cannot be moved back to manual intervention.")

    previous_state = job.state.value
    job.state = BackgroundJobState.WAITING_EXTERNAL
    job.error_message = reason
    db.add(job)
    create_job_log(
        db,
        job,
        event_type="manual_intervention_required",
        message=reason,
        level="warning",
        metadata={"previous_state": previous_state},
    )
    db.commit()
    refreshed_job = get_background_job(db, job.id) or job
    emit_background_job_event(refreshed_job, event_type="manual_intervention_required")
    return refreshed_job


def mark_job_progress(db: Session, job: BackgroundJob, progress_percent: int) -> None:
    job.progress_percent = progress_percent
    db.add(job)
    create_job_log(
        db,
        job,
        event_type="job_progress_updated",
        message=f"Job progress updated to {progress_percent}%.",
        metadata={"progress_percent": progress_percent},
    )
    db.commit()
    db.refresh(job)
    emit_background_job_event(
        job,
        event_type="job_progress_updated",
        metadata={"progress_percent": progress_percent},
    )


def mark_job_completed(db: Session, job: BackgroundJob) -> None:
    job.state = BackgroundJobState.COMPLETED
    job.progress_percent = 100
    job.finished_at = datetime.now(UTC)
    job.error_message = None
    db.add(job)
    create_job_log(
        db,
        job,
        event_type="job_completed",
        message="Job completed successfully.",
        metadata={"progress_percent": 100},
    )
    _promote_project_after_completed_job(db, job)
    db.commit()
    db.refresh(job)
    emit_background_job_event(job, event_type="job_completed")


def mark_job_failed(db: Session, job: BackgroundJob, error_message: str) -> None:
    now = datetime.now(UTC)
    job.state = BackgroundJobState.FAILED
    job.finished_at = now
    job.error_message = error_message
    db.add(job)
    create_job_log(
        db,
        job,
        event_type="job_failed",
        message=error_message,
        level="error",
    )

    if job.job_type in {BackgroundJobType.COMPOSE_ROUGH_CUT, BackgroundJobType.FINAL_EXPORT}:
        for asset in _list_payload_assets(db, job):
            if asset.status != AssetStatus.READY:
                asset.status = AssetStatus.FAILED
                db.add(asset)

    for attempt in job.generation_attempts:
        if attempt.state in {BackgroundJobState.COMPLETED, BackgroundJobState.FAILED}:
            continue
        attempt.state = BackgroundJobState.FAILED
        attempt.finished_at = now
        attempt.error_message = error_message
        db.add(attempt)
        for asset in attempt.assets:
            if asset.status == AssetStatus.READY:
                continue
            asset.status = AssetStatus.FAILED
            db.add(asset)

    db.commit()
    db.refresh(job)
    emit_background_job_event(job, event_type="job_failed")


def mark_attempt_running(db: Session, attempt: GenerationAttempt) -> None:
    now = datetime.now(UTC)
    attempt.state = BackgroundJobState.RUNNING
    attempt.started_at = now
    attempt.error_message = None
    db.add(attempt)
    create_job_log(
        db,
        attempt.background_job,
        event_type="attempt_started",
        message="Generation attempt started.",
        attempt=attempt,
        metadata={"scene_id": str(attempt.scene_id) if attempt.scene_id is not None else None},
    )
    for asset in attempt.assets:
        asset.status = AssetStatus.GENERATING
        db.add(asset)
    db.commit()
    db.refresh(attempt)


def mark_attempt_completed(db: Session, attempt: GenerationAttempt) -> None:
    attempt.state = BackgroundJobState.COMPLETED
    attempt.finished_at = datetime.now(UTC)
    attempt.error_message = None
    db.add(attempt)
    create_job_log(
        db,
        attempt.background_job,
        event_type="attempt_completed",
        message="Generation attempt completed.",
        attempt=attempt,
        metadata={"scene_id": str(attempt.scene_id) if attempt.scene_id is not None else None},
    )
    for asset in attempt.assets:
        asset.status = AssetStatus.READY
        db.add(asset)
    db.commit()
    db.refresh(attempt)


def get_attempt_assets(attempt: GenerationAttempt) -> list[Asset]:
    return list(attempt.assets)


def _promote_project_after_completed_job(db: Session, job: BackgroundJob) -> None:
    if job.job_type == BackgroundJobType.COMPOSE_ROUGH_CUT:
        _promote_project_to_rough_cut_ready(db, job)
        return

    if job.job_type == BackgroundJobType.FINAL_EXPORT:
        _promote_project_to_final_review(db, job)
        return

    if job.job_type in {BackgroundJobType.PUBLISH_CONTENT, BackgroundJobType.SYNC_ANALYTICS}:
        return

    _promote_project_to_asset_review(db, job)


def _promote_project_to_asset_review(db: Session, job: BackgroundJob) -> None:
    db.flush()

    project = db.get(Project, job.project_id)
    if project is None or project.status != ProjectStatus.ASSET_GENERATION:
        return

    script = db.get(ProjectScript, job.script_id)
    if script is None:
        return

    if can_enter_asset_review(db, project, script):
        project.status = ProjectStatus.ASSET_PENDING_APPROVAL
        db.add(project)


def _promote_project_to_rough_cut_ready(db: Session, job: BackgroundJob) -> None:
    db.flush()

    project = db.get(Project, job.project_id)
    if project is None or project.status != ProjectStatus.ASSET_PENDING_APPROVAL:
        return

    script = db.get(ProjectScript, job.script_id)
    if script is None:
        return

    if has_ready_rough_cut(db, script):
        project.status = ProjectStatus.ROUGH_CUT_READY
        db.add(project)


def _promote_project_to_final_review(db: Session, job: BackgroundJob) -> None:
    db.flush()

    project = db.get(Project, job.project_id)
    if project is None or project.status not in {
        ProjectStatus.ROUGH_CUT_READY,
        ProjectStatus.FINAL_PENDING_APPROVAL,
    }:
        return

    script = db.get(ProjectScript, job.script_id)
    if script is None:
        return

    statement = select(Asset).where(
        Asset.script_id == script.id,
        Asset.asset_type == AssetType.FINAL_VIDEO,
        Asset.status == AssetStatus.READY,
    )
    if db.scalar(statement) is None:
        return

    project.status = ProjectStatus.FINAL_PENDING_APPROVAL
    db.add(project)


def _extract_payload_asset_ids(payload_json: dict[str, object]) -> list[UUID]:
    asset_ids: list[UUID] = []
    for key in ("output_asset_id", "subtitle_asset_id", "video_asset_id"):
        raw_value = payload_json.get(key)
        if raw_value is None:
            continue
        try:
            asset_ids.append(UUID(str(raw_value)))
        except ValueError:
            continue
    return asset_ids


def _list_payload_assets(db: Session, job: BackgroundJob) -> list[Asset]:
    asset_ids = _extract_payload_asset_ids(job.payload_json)
    if not asset_ids:
        return []

    statement = select(Asset).where(Asset.id.in_(asset_ids))
    return list(db.scalars(statement))


def _mark_unfinished_asset_failed(db: Session, asset: Asset) -> None:
    if asset.status in {AssetStatus.READY, AssetStatus.REJECTED}:
        return

    asset.status = AssetStatus.FAILED
    db.add(asset)


def _reset_asset_for_retry(db: Session, asset: Asset) -> None:
    if asset.status not in RESETTABLE_ASSET_STATUSES:
        return

    asset.status = AssetStatus.PLANNED
    asset.checksum = None
    db.add(asset)


def _reset_unfinished_asset_for_resume(db: Session, asset: Asset) -> None:
    if asset.status in {AssetStatus.READY, AssetStatus.REJECTED}:
        return

    asset.status = AssetStatus.PLANNED
    asset.checksum = None
    db.add(asset)


def _ensure_job_type_supports_manual_retry(job: BackgroundJob) -> None:
    if job.job_type in RETRY_POLICY_MAX_ATTEMPTS:
        return

    raise ValueError(
        "This job type does not support manual retry. Re-run the project action "
        "that created the job instead."
    )


def _ensure_retry_budget_available(job: BackgroundJob) -> None:
    max_attempts = RETRY_POLICY_MAX_ATTEMPTS[job.job_type]
    if job.attempts < max_attempts:
        return

    raise ValueError(
        f"Retry limit exceeded for {job.job_type.value}. This job has used "
        f"{job.attempts} of {max_attempts} allowed execution attempt(s)."
    )


def _ensure_job_is_stale(job: BackgroundJob, *, stale_after_minutes: int) -> None:
    stale_cutoff = datetime.now(UTC) - timedelta(minutes=stale_after_minutes)
    updated_at = _as_aware_datetime(job.updated_at)
    if updated_at > stale_cutoff:
        raise ValueError(
            "Running job is not stale enough to resume safely. "
            f"Wait until it has no updates for at least {stale_after_minutes} minute(s)."
        )


def _as_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _ensure_no_other_active_job(db: Session, job: BackgroundJob) -> None:
    statement = select(BackgroundJob).where(
        BackgroundJob.id != job.id,
        BackgroundJob.project_id == job.project_id,
        BackgroundJob.script_id == job.script_id,
        BackgroundJob.job_type == job.job_type,
        BackgroundJob.state.in_(ACTIVE_JOB_STATES),
    )
    active_job = db.scalar(statement)
    if active_job is not None:
        raise ValueError(
            "Cannot retry this job while another active job of the same type exists "
            "for the current script."
        )
