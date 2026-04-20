from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.background_job import BackgroundJob
from apps.api.models.job_log import JobLog
from apps.api.models.project import Project
from apps.api.models.user import User
from apps.api.schemas.content_workflow import (
    BackgroundJobResponse,
    OperationsRecoveryResponse,
    RecoveryJobResponse,
    RecoveryLogResponse,
)
from apps.api.schemas.enums import BackgroundJobState

RECOVERY_LOG_EVENT_TYPES = {
    "downloads_quarantined",
    "duplicate_asset_detected",
}


def get_operations_recovery_snapshot(
    db: Session,
    user: User,
    *,
    stale_after_minutes: int = 30,
    limit: int = 20,
) -> OperationsRecoveryResponse:
    failed_jobs = _list_recovery_jobs(
        db,
        user,
        states={BackgroundJobState.FAILED},
        limit=limit,
    )
    waiting_jobs = _list_recovery_jobs(
        db,
        user,
        states={BackgroundJobState.WAITING_EXTERNAL},
        limit=limit,
    )
    stale_running_jobs = _list_recovery_jobs(
        db,
        user,
        states={BackgroundJobState.RUNNING},
        limit=limit,
        updated_before=datetime.now(UTC) - timedelta(minutes=stale_after_minutes),
    )
    quarantined_downloads = _list_recovery_logs(
        db,
        user,
        event_type="downloads_quarantined",
        limit=limit,
    )
    duplicate_asset_warnings = _list_recovery_logs(
        db,
        user,
        event_type="duplicate_asset_detected",
        limit=limit,
    )

    return OperationsRecoveryResponse(
        failed_jobs=failed_jobs,
        waiting_jobs=waiting_jobs,
        stale_running_jobs=stale_running_jobs,
        quarantined_downloads=quarantined_downloads,
        duplicate_asset_warnings=duplicate_asset_warnings,
        summary={
            "failed_jobs": len(failed_jobs),
            "waiting_jobs": len(waiting_jobs),
            "stale_running_jobs": len(stale_running_jobs),
            "quarantined_downloads": len(quarantined_downloads),
            "duplicate_asset_warnings": len(duplicate_asset_warnings),
            "total_attention_items": (
                len(failed_jobs)
                + len(waiting_jobs)
                + len(stale_running_jobs)
                + len(quarantined_downloads)
                + len(duplicate_asset_warnings)
            ),
        },
    )


def _list_recovery_jobs(
    db: Session,
    user: User,
    *,
    states: set[BackgroundJobState],
    limit: int,
    updated_before: datetime | None = None,
) -> list[RecoveryJobResponse]:
    statement = (
        select(BackgroundJob, Project)
        .join(Project, Project.id == BackgroundJob.project_id)
        .where(
            BackgroundJob.user_id == user.id,
            BackgroundJob.state.in_(states),
        )
        .order_by(desc(BackgroundJob.updated_at), desc(BackgroundJob.created_at))
        .limit(limit)
    )
    if updated_before is not None:
        statement = statement.where(BackgroundJob.updated_at <= updated_before)

    return [
        _recovery_job_response(db, job, project)
        for job, project in db.execute(statement).all()
    ]


def _recovery_job_response(
    db: Session,
    job: BackgroundJob,
    project: Project,
) -> RecoveryJobResponse:
    latest_log = _get_latest_job_log(db, job)
    return RecoveryJobResponse(
        job=BackgroundJobResponse.model_validate(job),
        project_title=project.title,
        project_status=project.status,
        latest_log_event_type=latest_log.event_type if latest_log is not None else None,
        latest_log_message=latest_log.message if latest_log is not None else None,
        latest_log_created_at=latest_log.created_at if latest_log is not None else None,
    )


def _get_latest_job_log(db: Session, job: BackgroundJob) -> JobLog | None:
    statement = (
        select(JobLog)
        .where(JobLog.background_job_id == job.id)
        .order_by(desc(JobLog.created_at), desc(JobLog.id))
        .limit(1)
    )
    return db.scalar(statement)


def _list_recovery_logs(
    db: Session,
    user: User,
    *,
    event_type: str,
    limit: int,
) -> list[RecoveryLogResponse]:
    if event_type not in RECOVERY_LOG_EVENT_TYPES:
        raise ValueError(f"Unsupported recovery log event type: {event_type}")

    statement = (
        select(JobLog, Project)
        .join(Project, Project.id == JobLog.project_id)
        .where(
            JobLog.user_id == user.id,
            JobLog.event_type == event_type,
        )
        .order_by(desc(JobLog.created_at), desc(JobLog.id))
        .limit(limit)
    )

    return [
        RecoveryLogResponse(
            id=job_log.id,
            project_id=job_log.project_id,
            project_title=project.title,
            background_job_id=job_log.background_job_id,
            generation_attempt_id=job_log.generation_attempt_id,
            event_type=job_log.event_type,
            level=job_log.level,
            message=job_log.message,
            metadata_json=job_log.metadata_json,
            created_at=job_log.created_at,
        )
        for job_log, project in db.execute(statement).all()
    ]
