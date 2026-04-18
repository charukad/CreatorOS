from datetime import UTC, datetime

from sqlalchemy import asc, select
from sqlalchemy.orm import Session, selectinload

from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.generation_attempt import GenerationAttempt
from apps.api.schemas.enums import AssetStatus, BackgroundJobState, BackgroundJobType

CLAIMABLE_BROWSER_JOB_TYPES = (
    BackgroundJobType.GENERATE_AUDIO_BROWSER,
    BackgroundJobType.GENERATE_VISUALS_BROWSER,
)


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
    db.commit()
    db.refresh(job)


def mark_job_failed(db: Session, job: BackgroundJob, error_message: str) -> None:
    now = datetime.now(UTC)
    job.state = BackgroundJobState.FAILED
    job.finished_at = now
    job.error_message = error_message
    db.add(job)

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
