import logging
import shutil
from pathlib import Path

from apps.api.db.session import SessionLocal
from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.generation_attempt import GenerationAttempt
from apps.api.schemas.enums import BackgroundJobType
from apps.api.services.background_jobs import (
    claim_next_browser_job,
    create_job_log,
    get_attempt_assets,
    mark_attempt_completed,
    mark_attempt_running,
    mark_job_completed,
    mark_job_failed,
    mark_job_progress,
)
from apps.api.services.file_metadata import file_sha256
from apps.api.services.storage_paths import build_project_storage_path
from sqlalchemy import select
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
        debug_artifact_paths = provider.capture_debug_artifacts(provider_job_id)
        if debug_artifact_paths:
            create_job_log(
                session,
                job,
                event_type="debug_artifacts_captured",
                message="Browser provider debug artifacts were captured.",
                attempt=attempt,
                metadata={
                    "provider_job_id": provider_job_id,
                    "debug_artifact_paths": debug_artifact_paths,
                },
            )
            session.commit()
        download_paths = provider.collect_downloads(provider_job_id)

        _refresh_attempt(session, attempt)
        _materialize_attempt_outputs(session, attempt, download_paths)
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


def _materialize_attempt_outputs(
    session: Session,
    attempt: GenerationAttempt,
    download_paths: list[str],
) -> None:
    assets = get_attempt_assets(attempt)
    if len(download_paths) != len(assets):
        quarantined_paths = _quarantine_mismatched_downloads(
            session,
            attempt,
            download_paths,
            expected_count=len(assets),
        )
        raise ValueError(
            "Download count did not match the number of planned assets for the generation attempt. "
            f"Quarantined {len(quarantined_paths)} file(s) for manual review."
        )

    for asset, download_path in zip(assets, download_paths, strict=True):
        destination_path = Path(asset.file_path or download_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(download_path, destination_path)
        asset.file_path = str(destination_path)
        asset.checksum = file_sha256(destination_path)
        session.add(asset)
        _log_duplicate_checksum_if_needed(session, attempt, asset)


def _quarantine_mismatched_downloads(
    session: Session,
    attempt: GenerationAttempt,
    download_paths: list[str],
    *,
    expected_count: int,
) -> list[str]:
    quarantine_dir = Path(
        build_project_storage_path(
            attempt.project_id,
            "quarantine",
            f"job-{attempt.background_job_id}",
            f"attempt-{attempt.id}",
        )
    )
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    quarantined_paths: list[str] = []
    for download_path in download_paths:
        source_path = Path(download_path)
        if not source_path.exists():
            continue

        destination_path = _unique_destination_path(quarantine_dir / source_path.name)
        shutil.move(str(source_path), destination_path)
        quarantined_paths.append(str(destination_path))

    create_job_log(
        session,
        attempt.background_job,
        event_type="downloads_quarantined",
        message="Download count mismatch; files were moved to quarantine for manual review.",
        level="warning",
        attempt=attempt,
        metadata={
            "expected_count": expected_count,
            "actual_count": len(download_paths),
            "quarantine_paths": quarantined_paths,
        },
    )
    return quarantined_paths


def _log_duplicate_checksum_if_needed(
    session: Session,
    attempt: GenerationAttempt,
    asset: Asset,
) -> None:
    if asset.checksum is None:
        return

    duplicate_statement = (
        select(Asset)
        .where(
            Asset.user_id == asset.user_id,
            Asset.checksum == asset.checksum,
            Asset.id != asset.id,
        )
        .limit(10)
    )
    duplicate_assets = list(session.scalars(duplicate_statement))
    if not duplicate_assets:
        return

    create_job_log(
        session,
        attempt.background_job,
        event_type="duplicate_asset_detected",
        message="Generated asset checksum matches an existing asset.",
        level="warning",
        attempt=attempt,
        metadata={
            "asset_id": str(asset.id),
            "checksum": asset.checksum,
            "duplicate_asset_ids": [str(duplicate.id) for duplicate in duplicate_assets],
        },
    )


def _unique_destination_path(destination_path: Path) -> Path:
    if not destination_path.exists():
        return destination_path

    for index in range(1, 1000):
        candidate = destination_path.with_name(
            f"{destination_path.stem}-{index}{destination_path.suffix}"
        )
        if not candidate.exists():
            return candidate

    raise ValueError(f"Unable to find a unique quarantine path for {destination_path}.")


def _refresh_job(session: Session, job: BackgroundJob) -> None:
    session.refresh(job, attribute_names=["generation_attempts"])


def _refresh_attempt(session: Session, attempt: GenerationAttempt) -> None:
    session.refresh(attempt, attribute_names=["assets"])
