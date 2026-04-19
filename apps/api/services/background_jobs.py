from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import asc, select
from sqlalchemy.orm import Session, selectinload

from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.generation_attempt import GenerationAttempt
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.schemas.enums import AssetStatus, BackgroundJobState, BackgroundJobType, ProjectStatus
from apps.api.services.assets import can_enter_asset_review, has_ready_rough_cut

CLAIMABLE_BROWSER_JOB_TYPES = (
    BackgroundJobType.GENERATE_AUDIO_BROWSER,
    BackgroundJobType.GENERATE_VISUALS_BROWSER,
)
CLAIMABLE_MEDIA_JOB_TYPES = (BackgroundJobType.COMPOSE_ROUGH_CUT,)


def claim_next_browser_job(db: Session) -> BackgroundJob | None:
    statement = (
        select(BackgroundJob)
        .options(
            selectinload(BackgroundJob.generation_attempts).selectinload(GenerationAttempt.assets),
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
    db.commit()
    db.refresh(job)
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
    db.commit()
    db.refresh(job)
    return get_background_job(db, job.id)


def get_background_job(db: Session, job_id: object) -> BackgroundJob | None:
    statement = (
        select(BackgroundJob)
        .options(
            selectinload(BackgroundJob.generation_attempts).selectinload(GenerationAttempt.assets),
        )
        .where(BackgroundJob.id == job_id)
    )
    return db.scalar(statement)


def mark_job_progress(db: Session, job: BackgroundJob, progress_percent: int) -> None:
    job.progress_percent = progress_percent
    db.add(job)
    db.commit()
    db.refresh(job)


def mark_job_completed(db: Session, job: BackgroundJob) -> None:
    job.state = BackgroundJobState.COMPLETED
    job.progress_percent = 100
    job.finished_at = datetime.now(UTC)
    job.error_message = None
    db.add(job)
    _promote_project_after_completed_job(db, job)
    db.commit()
    db.refresh(job)


def mark_job_failed(db: Session, job: BackgroundJob, error_message: str) -> None:
    now = datetime.now(UTC)
    job.state = BackgroundJobState.FAILED
    job.finished_at = now
    job.error_message = error_message
    db.add(job)

    if job.job_type == BackgroundJobType.COMPOSE_ROUGH_CUT:
        output_asset_id = job.payload_json.get("output_asset_id")
        if output_asset_id is not None:
            asset = db.get(Asset, UUID(str(output_asset_id)))
            if asset is not None and asset.status != AssetStatus.READY:
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


def mark_attempt_running(db: Session, attempt: GenerationAttempt) -> None:
    now = datetime.now(UTC)
    attempt.state = BackgroundJobState.RUNNING
    attempt.started_at = now
    attempt.error_message = None
    db.add(attempt)
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
