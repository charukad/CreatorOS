import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from apps.api.db.session import SessionLocal
from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.project import Project
from apps.api.models.publish_job import PublishJob
from apps.api.schemas.enums import (
    AssetStatus,
    BackgroundJobState,
    BackgroundJobType,
    PublishJobStatus,
)
from apps.api.services.background_jobs import (
    claim_next_publish_job,
    create_job_log,
    mark_job_failed,
    mark_job_progress,
)
from apps.api.services.project_events import create_project_event
from sqlalchemy.orm import Session, sessionmaker

from workers.publisher.adapters import ManualPublishHandoffAdapter
from workers.publisher.config import PublisherWorkerSettings

logger = logging.getLogger(__name__)


def run_pending_jobs(
    *,
    settings: PublisherWorkerSettings,
    session_factory: sessionmaker[Session] = SessionLocal,
    max_jobs: int | None = None,
) -> int:
    processed_jobs = 0
    job_limit = max_jobs if max_jobs is not None else settings.publisher_max_jobs_per_run

    while processed_jobs < job_limit:
        with session_factory() as session:
            job = claim_next_publish_job(session)
            if job is None:
                return processed_jobs

            logger.info("Processing publisher job %s (%s)", job.id, job.job_type.value)

            try:
                _process_job(session, job)
            except Exception as error:  # pragma: no cover - defensive logging path
                logger.exception("Publisher job %s failed", job.id)
                failed_job = session.get(BackgroundJob, job.id)
                if failed_job is not None:
                    mark_job_failed(session, failed_job, str(error))
                processed_jobs += 1
                continue

        processed_jobs += 1

    return processed_jobs


def _process_job(session: Session, job: BackgroundJob) -> None:
    if job.job_type != BackgroundJobType.PUBLISH_CONTENT:
        raise ValueError(f"Unsupported publisher job type: {job.job_type.value}")

    publish_job = _get_publish_job(session, job)
    project = _get_project(session, publish_job)
    final_asset = _get_ready_final_asset(session, publish_job)
    thumbnail_asset = _get_thumbnail_asset(session, publish_job)

    if publish_job.status not in {PublishJobStatus.APPROVED, PublishJobStatus.SCHEDULED}:
        raise ValueError("Publish handoff requires an approved or scheduled publish job.")

    adapter = ManualPublishHandoffAdapter()
    handoff_package = adapter.build_handoff_package(
        project=project,
        publish_job=publish_job,
        final_asset=final_asset,
        thumbnail_asset=thumbnail_asset,
    )
    handoff_path = Path(str(job.payload_json["handoff_path"]))
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(json.dumps(handoff_package, indent=2, sort_keys=True), encoding="utf-8")
    mark_job_progress(session, job, 70)

    _refresh_job(session, job)
    job.payload_json = {
        **job.payload_json,
        "adapter_name": adapter.name,
        "handoff_path": str(handoff_path),
        "handoff_ready_at": datetime.now(UTC).isoformat(),
        "final_asset_path": final_asset.file_path,
        "thumbnail_asset_path": thumbnail_asset.file_path if thumbnail_asset else None,
    }
    job.state = BackgroundJobState.WAITING_EXTERNAL
    job.progress_percent = 90
    job.error_message = (
        "Manual publish handoff is ready. Upload on the platform, then mark the publish job "
        "as published in CreatorOS."
    )
    session.add(job)
    create_job_log(
        session,
        job,
        event_type="manual_publish_handoff_ready",
        message="Manual publish handoff package was generated.",
        level="warning",
        metadata={
            "publish_job_id": str(publish_job.id),
            "platform": publish_job.platform,
            "handoff_path": str(handoff_path),
            "adapter_name": adapter.name,
        },
    )
    create_project_event(
        session,
        project,
        event_type="manual_publish_handoff_ready",
        title="Manual publish handoff ready",
        description=publish_job.title,
        level="warning",
        metadata={
            "background_job_id": str(job.id),
            "publish_job_id": str(publish_job.id),
            "platform": publish_job.platform,
            "handoff_path": str(handoff_path),
        },
    )
    session.commit()
    session.refresh(job)


def _get_publish_job(session: Session, job: BackgroundJob) -> PublishJob:
    publish_job_id = job.payload_json.get("publish_job_id")
    if publish_job_id is None:
        raise ValueError("Publish handoff job payload is missing publish_job_id.")

    publish_job = session.get(PublishJob, UUID(str(publish_job_id)))
    if publish_job is None:
        raise ValueError("Publish job not found for publish handoff.")

    return publish_job


def _get_project(session: Session, publish_job: PublishJob) -> Project:
    project = session.get(Project, publish_job.project_id)
    if project is None:
        raise ValueError("Project not found for publish handoff.")

    return project


def _get_ready_final_asset(session: Session, publish_job: PublishJob) -> Asset:
    final_asset = session.get(Asset, publish_job.final_asset_id)
    if final_asset is None or final_asset.project_id != publish_job.project_id:
        raise ValueError("Final asset not found for publish handoff.")

    if final_asset.status != AssetStatus.READY:
        raise ValueError("Final asset must be ready before publish handoff.")

    return final_asset


def _get_thumbnail_asset(session: Session, publish_job: PublishJob) -> Asset | None:
    thumbnail_asset_id = publish_job.metadata_json.get("thumbnail_asset_id")
    if thumbnail_asset_id is None:
        return None

    thumbnail_asset = session.get(Asset, UUID(str(thumbnail_asset_id)))
    if thumbnail_asset is None or thumbnail_asset.project_id != publish_job.project_id:
        raise ValueError("Thumbnail asset not found for publish handoff.")

    if thumbnail_asset.script_id != publish_job.script_id:
        raise ValueError("Thumbnail asset must belong to the publish job script.")

    if thumbnail_asset.status != AssetStatus.READY:
        raise ValueError("Thumbnail asset must be ready before publish handoff.")

    return thumbnail_asset


def _refresh_job(session: Session, job: BackgroundJob) -> None:
    session.refresh(job)
