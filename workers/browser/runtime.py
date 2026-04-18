import logging
import shutil
from pathlib import Path

from apps.api.db.session import SessionLocal
from apps.api.models.background_job import BackgroundJob
from apps.api.models.generation_attempt import GenerationAttempt
from apps.api.schemas.enums import BackgroundJobType
from apps.api.services.background_jobs import (
    claim_next_browser_job,
    get_attempt_assets,
    mark_attempt_completed,
    mark_attempt_running,
    mark_job_completed,
    mark_job_failed,
    mark_job_progress,
)
from sqlalchemy.orm import Session, sessionmaker

from workers.browser.config import BrowserWorkerSettings
from workers.browser.providers import (
    DryRunElevenLabsProvider,
    DryRunFlowProvider,
    ProviderJobPayload,
)

logger = logging.getLogger(__name__)


def run_pending_jobs(
    *,
    settings: BrowserWorkerSettings,
    session_factory: sessionmaker[Session] = SessionLocal,
    max_jobs: int | None = None,
) -> int:
    processed_jobs = 0

    while max_jobs is None or processed_jobs < max_jobs:
        with session_factory() as session:
            job = claim_next_browser_job(session)
            if job is None:
                return processed_jobs

            logger.info("Processing browser job %s (%s)", job.id, job.job_type.value)

            try:
                _process_job(session, settings, job)
            except Exception as error:  # pragma: no cover - defensive logging path
                logger.exception("Browser job %s failed", job.id)
                failed_job = session.get(BackgroundJob, job.id)
                if failed_job is not None:
                    mark_job_failed(session, failed_job, str(error))
                processed_jobs += 1
                continue

        processed_jobs += 1

    return processed_jobs


def _process_job(session: Session, settings: BrowserWorkerSettings, job: BackgroundJob) -> None:
    provider = _get_provider(settings, job.job_type)
    provider.ensure_session()
    provider.open_workspace()

    attempts = sorted(job.generation_attempts, key=lambda attempt: attempt.created_at)
    total_attempts = len(attempts)

    for index, attempt in enumerate(attempts, start=1):
        mark_attempt_running(session, attempt)
        _refresh_job(session, job)

        provider_payload = _build_provider_payload(job, attempt)
        provider_job_id = provider.submit_job(provider_payload)
        provider.wait_for_completion(provider_job_id)
        provider.capture_debug_artifacts(provider_job_id)
        download_paths = provider.collect_downloads(provider_job_id)

        _refresh_attempt(session, attempt)
        _materialize_attempt_outputs(attempt, download_paths)
        mark_attempt_completed(session, attempt)

        _refresh_job(session, job)
        progress = min(95, int((index / max(total_attempts, 1)) * 100))
        mark_job_progress(session, job, progress)

    _refresh_job(session, job)
    mark_job_completed(session, job)


def _get_provider(settings: BrowserWorkerSettings, job_type: BackgroundJobType):
    if settings.browser_provider_mode != "dry_run":
        raise ValueError(
            "Only the 'dry_run' browser provider mode is implemented in this environment."
        )
    if job_type == BackgroundJobType.GENERATE_AUDIO_BROWSER:
        return DryRunElevenLabsProvider(settings.playwright_download_root)
    if job_type == BackgroundJobType.GENERATE_VISUALS_BROWSER:
        return DryRunFlowProvider(settings.playwright_download_root)
    raise ValueError(f"Unsupported browser job type: {job_type.value}")


def _build_provider_payload(job: BackgroundJob, attempt: GenerationAttempt) -> ProviderJobPayload:
    if job.job_type == BackgroundJobType.GENERATE_AUDIO_BROWSER:
        return ProviderJobPayload(
            project_id=str(job.project_id),
            prompt=str(attempt.input_payload_json.get("full_script", "")),
            metadata={
                "duration_seconds": attempt.assets[0].duration_seconds if attempt.assets else 4,
                "voice_label": job.payload_json.get("voice_label"),
            },
        )

    scene_order = attempt.input_payload_json.get("scene_order")
    return ProviderJobPayload(
        project_id=str(job.project_id),
        scene_id=str(attempt.scene_id) if attempt.scene_id is not None else None,
        prompt=str(attempt.input_payload_json.get("image_generation_prompt", "")),
        metadata={
            "title": attempt.input_payload_json.get("title", "Scene visual"),
            "scene_label": f"Scene {scene_order}" if scene_order is not None else "Scene",
            "channel_name": "CreatorOS",
        },
    )


def _materialize_attempt_outputs(attempt: GenerationAttempt, download_paths: list[str]) -> None:
    assets = get_attempt_assets(attempt)
    if len(download_paths) != len(assets):
        raise ValueError(
            "Download count did not match the number of planned assets for the generation attempt."
        )

    for asset, download_path in zip(assets, download_paths, strict=True):
        destination_path = Path(asset.file_path or download_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(download_path, destination_path)
        asset.file_path = str(destination_path)


def _refresh_job(session: Session, job: BackgroundJob) -> None:
    session.refresh(job, attribute_names=["generation_attempts"])


def _refresh_attempt(session: Session, attempt: GenerationAttempt) -> None:
    session.refresh(attempt, attribute_names=["assets"])
