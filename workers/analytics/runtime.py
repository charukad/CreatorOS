import logging
from uuid import UUID

from apps.api.db.session import SessionLocal
from apps.api.models.background_job import BackgroundJob
from apps.api.models.publish_job import PublishJob
from apps.api.schemas.content_workflow import AnalyticsSnapshotRequest
from apps.api.schemas.enums import BackgroundJobType
from apps.api.services.analytics import sync_publish_job_analytics
from apps.api.services.background_jobs import (
    claim_next_analytics_job,
    create_job_log,
    mark_job_completed,
    mark_job_failed,
    mark_job_progress,
)
from apps.api.services.project_events import create_project_event
from sqlalchemy.orm import Session, sessionmaker

from workers.analytics.config import AnalyticsWorkerSettings

logger = logging.getLogger(__name__)


def run_pending_jobs(
    *,
    settings: AnalyticsWorkerSettings,
    session_factory: sessionmaker[Session] = SessionLocal,
    max_jobs: int | None = None,
) -> int:
    processed_jobs = 0
    job_limit = max_jobs if max_jobs is not None else settings.analytics_max_jobs_per_run

    while processed_jobs < job_limit:
        with session_factory() as session:
            job = claim_next_analytics_job(session)
            if job is None:
                return processed_jobs

            logger.info("Processing analytics job %s (%s)", job.id, job.job_type.value)

            try:
                _process_job(session, job)
            except Exception as error:  # pragma: no cover - defensive logging path
                logger.exception("Analytics job %s failed", job.id)
                session.rollback()
                failed_job = session.get(BackgroundJob, job.id)
                if failed_job is not None:
                    mark_job_failed(session, failed_job, str(error))
                processed_jobs += 1
                continue

        processed_jobs += 1

    return processed_jobs


def _process_job(session: Session, job: BackgroundJob) -> None:
    if job.job_type != BackgroundJobType.SYNC_ANALYTICS:
        raise ValueError(f"Unsupported analytics job type: {job.job_type.value}")

    publish_job = _get_publish_job(session, job)
    payload = _build_snapshot_request(job)

    mark_job_progress(session, job, 40)
    snapshot = sync_publish_job_analytics(
        session,
        publish_job=publish_job,
        payload=payload,
        commit=False,
    )

    session.refresh(job)
    job.payload_json = {
        **job.payload_json,
        "analytics_snapshot_id": str(snapshot.id),
        "synced_at": snapshot.fetched_at.isoformat(),
    }
    session.add(job)
    create_job_log(
        session,
        job,
        event_type="analytics_snapshot_synced",
        message="Analytics snapshot and insights were persisted.",
        metadata={
            "publish_job_id": str(publish_job.id),
            "analytics_snapshot_id": str(snapshot.id),
            "platform": publish_job.platform,
            "views": snapshot.views,
        },
    )
    create_project_event(
        session,
        publish_job.project,
        event_type="analytics_snapshot_synced",
        title="Analytics synced",
        description=publish_job.title,
        metadata={
            "background_job_id": str(job.id),
            "publish_job_id": str(publish_job.id),
            "analytics_snapshot_id": str(snapshot.id),
            "platform": publish_job.platform,
        },
    )
    mark_job_completed(session, job)


def _get_publish_job(session: Session, job: BackgroundJob) -> PublishJob:
    publish_job_id = job.payload_json.get("publish_job_id")
    if publish_job_id is None:
        raise ValueError("Analytics sync job payload is missing publish_job_id.")

    publish_job = session.get(PublishJob, UUID(str(publish_job_id)))
    if publish_job is None:
        raise ValueError("Publish job not found for analytics sync.")

    return publish_job


def _build_snapshot_request(job: BackgroundJob) -> AnalyticsSnapshotRequest:
    metrics_payload = job.payload_json.get("metrics")
    if not isinstance(metrics_payload, dict):
        raise ValueError("Analytics sync job payload is missing metrics.")

    return AnalyticsSnapshotRequest.model_validate(metrics_payload)
