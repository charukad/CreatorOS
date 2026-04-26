import json
import logging
import shutil
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from apps.api.core.config_validation import resolve_path_within_roots
from apps.api.db.session import SessionLocal
from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.generation_attempt import GenerationAttempt
from apps.api.schemas.enums import AssetStatus, BackgroundJobState, BackgroundJobType
from apps.api.services.background_jobs import (
    claim_next_browser_job,
    create_job_log,
    get_attempt_assets,
    mark_attempt_completed,
    mark_attempt_running,
    mark_job_completed,
    mark_job_failed,
    mark_job_manual_intervention_required,
    mark_job_progress,
)
from apps.api.services.file_metadata import file_sha256
from apps.api.services.storage_paths import build_project_storage_path
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from workers.browser.config import BrowserWorkerSettings
from workers.browser.downloads import (
    TaggedDownload,
    is_managed_browser_download_path,
    stage_provider_downloads_for_attempt,
)
from workers.browser.providers import (
    BrowserProvider,
    ElevenLabsProvider,
    FlowProvider,
    ProviderJobPayload,
)
from workers.browser.providers.debug_artifacts import write_checkpoint_debug_artifacts
from workers.browser.selectors import SelectorBundle, load_selector_bundle, selector_bundle_summary
from workers.browser.sessions import (
    BrowserSessionDescriptor,
    build_session_descriptor,
    classify_manual_intervention_error,
    sanitize_browser_message,
    sanitize_browser_metadata,
)

logger = logging.getLogger(__name__)

BROWSER_PROVIDER_INLINE_RETRY_LIMIT = 1
BrowserDownloadInput = str | TaggedDownload


class _BrowserJobPausedForManualIntervention(RuntimeError):
    """Internal control-flow signal used when a job is moved to waiting_external."""


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
            except _BrowserJobPausedForManualIntervention:
                processed_jobs += 1
                continue
            except Exception as error:  # pragma: no cover - defensive logging path
                logger.exception("Browser job %s failed", job.id)
                failed_job = session.get(BackgroundJob, job.id)
                if failed_job is not None:
                    mark_job_failed(session, failed_job, sanitize_browser_message(str(error)))
                processed_jobs += 1
                continue

        processed_jobs += 1

    return processed_jobs


def _process_job(session: Session, settings: BrowserWorkerSettings, job: BackgroundJob) -> None:
    selector_bundle = None
    session_descriptor = None
    if job.provider_name is not None:
        selector_bundle = load_selector_bundle(job.provider_name)
        session_descriptor = build_session_descriptor(settings, job.provider_name, selector_bundle)

    provider = _get_provider(
        settings,
        job,
        selector_bundle=selector_bundle,
        session_descriptor=session_descriptor,
    )
    selector_bundle, session_descriptor = _prepare_provider_session(
        session,
        settings,
        job,
        provider,
        selector_bundle=selector_bundle,
        session_descriptor=session_descriptor,
    )

    attempts = sorted(job.generation_attempts, key=lambda attempt: attempt.created_at)
    pending_attempts = [
        attempt for attempt in attempts if attempt.state != BackgroundJobState.COMPLETED
    ]
    total_attempts = len(pending_attempts)

    for index, attempt in enumerate(pending_attempts, start=1):
        mark_attempt_running(session, attempt)
        _refresh_job(session, job)

        provider_payload = _build_provider_payload(job, attempt)
        provider_job_id, download_paths = _run_provider_job_with_retry(
            session,
            provider,
            job,
            attempt,
            provider_payload,
        )
        _write_generation_attempt_metadata(
            session,
            job,
            attempt,
            provider_payload=provider_payload,
            provider_job_id=provider_job_id,
            selector_bundle=selector_bundle,
            session_descriptor=session_descriptor,
        )

        debug_artifact_paths = provider.capture_debug_artifacts(provider_job_id)
        if debug_artifact_paths:
            _log_browser_job_event(
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

        tagged_downloads = stage_provider_downloads_for_attempt(
            attempt,
            provider_job_id=provider_job_id,
            download_paths=download_paths,
        )
        _log_browser_job_event(
            session,
            job,
            event_type="browser_downloads_tagged",
            message="Provider downloads were staged and tagged for explicit ingest.",
            attempt=attempt,
            metadata={
                "provider_job_id": provider_job_id,
                "download_count": len(tagged_downloads),
                "staged_download_paths": [download.staged_path for download in tagged_downloads],
                "download_metadata_paths": [
                    download.metadata_path for download in tagged_downloads
                ],
            },
        )
        _refresh_attempt(session, attempt)
        output_registrations = _materialize_attempt_outputs(session, attempt, tagged_downloads)
        _write_output_registration_payload(
            session,
            attempt,
            provider_job_id=provider_job_id,
            output_registrations=output_registrations,
        )
        mark_attempt_completed(session, attempt)

        _refresh_job(session, job)
        progress = min(95, int((index / max(total_attempts, 1)) * 100))
        mark_job_progress(session, job, progress)

    _refresh_job(session, job)
    mark_job_completed(session, job)


def _get_provider(
    settings: BrowserWorkerSettings,
    job: BackgroundJob,
    *,
    selector_bundle: SelectorBundle | None,
    session_descriptor: BrowserSessionDescriptor | None,
) -> BrowserProvider:
    if job.job_type == BackgroundJobType.GENERATE_AUDIO_BROWSER:
        return ElevenLabsProvider(
            settings,
            selector_bundle=selector_bundle,
            session_descriptor=session_descriptor,
        )
    if job.job_type == BackgroundJobType.GENERATE_VISUALS_BROWSER:
        return FlowProvider(
            settings,
            selector_bundle=selector_bundle,
            session_descriptor=session_descriptor,
        )
    raise ValueError(f"Unsupported browser job type: {job.job_type.value}")


def _prepare_provider_session(
    session: Session,
    settings: BrowserWorkerSettings,
    job: BackgroundJob,
    provider: BrowserProvider,
    *,
    selector_bundle: SelectorBundle | None = None,
    session_descriptor: BrowserSessionDescriptor | None = None,
) -> tuple[SelectorBundle | None, BrowserSessionDescriptor | None]:
    if job.provider_name is None:
        return None, None

    resolved_selector_bundle = selector_bundle or load_selector_bundle(job.provider_name)
    resolved_session_descriptor = session_descriptor or build_session_descriptor(
        settings,
        job.provider_name,
        resolved_selector_bundle,
    )

    _log_browser_job_event(
        session,
        job,
        event_type="browser_selector_registry_loaded",
        message="Loaded the versioned selector registry for this browser provider.",
        metadata=selector_bundle_summary(resolved_selector_bundle),
    )
    _log_browser_job_event(
        session,
        job,
        event_type="browser_session_prepared",
        message="Prepared browser profile and debug roots for the provider session.",
        metadata={
            "provider_name": resolved_session_descriptor.provider_name.value,
            "profile_name": resolved_session_descriptor.profile_name,
            "profile_path": str(resolved_session_descriptor.profile_path),
            "debug_root": str(resolved_session_descriptor.debug_root),
            "workspace_label": resolved_session_descriptor.workspace_label,
            "selector_version": resolved_session_descriptor.selector_version,
        },
    )
    _capture_checkpoint_artifacts(
        session,
        job,
        resolved_session_descriptor,
        checkpoint_name="session_prepared",
        metadata={"workspace_label": resolved_session_descriptor.workspace_label},
    )

    try:
        provider.ensure_session()
        _log_browser_job_event(
            session,
            job,
            event_type="browser_session_validated",
            message="Browser provider session is available for the next automation step.",
            metadata={"profile_name": resolved_session_descriptor.profile_name},
        )
        _capture_checkpoint_artifacts(
            session,
            job,
            resolved_session_descriptor,
            checkpoint_name="session_validated",
            metadata={"profile_name": resolved_session_descriptor.profile_name},
        )
        provider.open_workspace()
        _log_browser_job_event(
            session,
            job,
            event_type="browser_workspace_opened",
            message="Browser provider workspace opened successfully.",
            metadata={"workspace_label": resolved_session_descriptor.workspace_label},
        )
        _capture_checkpoint_artifacts(
            session,
            job,
            resolved_session_descriptor,
            checkpoint_name="workspace_opened",
            metadata={"workspace_label": resolved_session_descriptor.workspace_label},
        )
    except Exception as error:
        _capture_failure_artifacts(session, provider, job, None, None, error)
        manual_intervention = classify_manual_intervention_error(error)
        if manual_intervention is not None:
            _pause_job_for_manual_intervention(
                session,
                job,
                reason=manual_intervention.reason,
                category=manual_intervention.category,
                session_descriptor=resolved_session_descriptor,
            )
            raise _BrowserJobPausedForManualIntervention from error
        raise

    return resolved_selector_bundle, resolved_session_descriptor


def _capture_failure_artifacts(
    session: Session,
    provider: BrowserProvider,
    job: BackgroundJob,
    attempt: GenerationAttempt | None,
    provider_job_id: str | None,
    error: Exception,
) -> None:
    sanitized_error_message = sanitize_browser_message(str(error))
    safe_error: Exception = error
    if sanitized_error_message != str(error):
        safe_error = RuntimeError(sanitized_error_message)

    try:
        failure_artifact_paths = provider.capture_failure_artifacts(provider_job_id, safe_error)
    except Exception as capture_error:  # pragma: no cover - defensive recovery logging
        _log_browser_job_event(
            session,
            job,
            event_type="browser_failure_artifact_capture_failed",
            message="Browser provider failure artifacts could not be captured.",
            level="warning",
            attempt=attempt,
            metadata={
                "provider_job_id": provider_job_id,
                "capture_error": sanitize_browser_message(str(capture_error)),
                "original_error": sanitized_error_message,
            },
        )
        return

    if not failure_artifact_paths:
        return

    _log_browser_job_event(
        session,
        job,
        event_type="browser_failure_artifacts_captured",
        message="Browser provider failure screenshot and HTML snapshot were captured.",
        level="warning",
        attempt=attempt,
        metadata={
            "provider_job_id": provider_job_id,
            "failure_artifact_paths": failure_artifact_paths,
            "error_message": sanitized_error_message,
        },
    )


def _run_provider_job_with_retry(
    session: Session,
    provider: BrowserProvider,
    job: BackgroundJob,
    attempt: GenerationAttempt,
    provider_payload: ProviderJobPayload,
) -> tuple[str, list[str]]:
    for retry_index in range(BROWSER_PROVIDER_INLINE_RETRY_LIMIT + 1):
        provider_job_id: str | None = None
        try:
            provider_job_id = provider.submit_job(provider_payload)
            provider.wait_for_completion(provider_job_id)
            return provider_job_id, provider.collect_downloads(provider_job_id)
        except Exception as error:
            _capture_failure_artifacts(session, provider, job, attempt, provider_job_id, error)
            manual_intervention = classify_manual_intervention_error(error)
            if manual_intervention is not None:
                _pause_job_for_manual_intervention(
                    session,
                    job,
                    attempt=attempt,
                    reason=manual_intervention.reason,
                    category=manual_intervention.category,
                    provider_job_id=provider_job_id,
                )
                raise _BrowserJobPausedForManualIntervention from error
            if (
                retry_index >= BROWSER_PROVIDER_INLINE_RETRY_LIMIT
                or not _is_retryable_browser_error(error)
            ):
                raise

            _log_browser_job_event(
                session,
                job,
                event_type="browser_provider_retry_scheduled",
                message=(
                    "Browser provider failed with a retryable timeout or selector error. "
                    "Retrying once before failing the job."
                ),
                level="warning",
                attempt=attempt,
                metadata={
                    "provider_job_id": provider_job_id,
                    "retry_number": retry_index + 1,
                    "max_inline_retries": BROWSER_PROVIDER_INLINE_RETRY_LIMIT,
                    "error_message": sanitize_browser_message(str(error)),
                },
            )

    raise RuntimeError("Browser provider retry loop exited unexpectedly.")


def _is_retryable_browser_error(error: Exception) -> bool:
    if isinstance(error, TimeoutError):
        return True

    message = str(error).lower()
    return any(pattern in message for pattern in ("timeout", "timed out", "selector"))


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
    download_inputs: list[BrowserDownloadInput],
) -> list[dict[str, object]]:
    assets = get_attempt_assets(attempt)
    if len(download_inputs) != len(assets):
        quarantined_paths = _quarantine_mismatched_downloads(
            session,
            attempt,
            download_inputs,
            expected_count=len(assets),
        )
        raise ValueError(
            "Download count did not match the number of planned assets for the generation attempt. "
            f"Quarantined {len(quarantined_paths)} file(s) for manual review."
        )

    output_registrations: list[dict[str, object]] = []
    for asset, download_input in zip(assets, download_inputs, strict=True):
        output_registrations.append(
            _materialize_asset_output(session, attempt, asset, download_input)
        )
        _log_duplicate_checksum_if_needed(session, attempt, asset)
    return output_registrations


def _materialize_asset_output(
    session: Session,
    attempt: GenerationAttempt,
    asset: Asset,
    download_input: BrowserDownloadInput,
) -> dict[str, object]:
    source_download_path = (
        download_input.staged_path if isinstance(download_input, TaggedDownload) else download_input
    )
    source_download_metadata_path = (
        download_input.metadata_path if isinstance(download_input, TaggedDownload) else None
    )
    source_path = Path(source_download_path)
    destination_path = _resolve_project_storage_path(
        Path(asset.file_path or source_download_path),
        path_name="Browser asset destination path",
    )
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    if not source_path.exists():
        raise FileNotFoundError(f"Expected provider download does not exist: {source_path}")

    if source_path.resolve() == destination_path.resolve():
        asset.file_path = str(destination_path)
        asset.checksum = file_sha256(destination_path)
        session.add(asset)
        return _build_output_registration_payload(
            asset,
            source_download_path=str(source_path),
            source_download_metadata_path=source_download_metadata_path,
        )

    if destination_path.exists():
        return _handle_existing_destination_path(
            session,
            attempt,
            asset,
            source_path=source_path,
            destination_path=destination_path,
            source_download_metadata_path=source_download_metadata_path,
        )

    _transfer_download_to_destination(source_path, destination_path)
    asset.file_path = str(destination_path)
    asset.checksum = file_sha256(destination_path)
    session.add(asset)
    return _build_output_registration_payload(
        asset,
        source_download_path=str(source_path),
        source_download_metadata_path=source_download_metadata_path,
    )


def _handle_existing_destination_path(
    session: Session,
    attempt: GenerationAttempt,
    asset: Asset,
    *,
    source_path: Path,
    destination_path: Path,
    source_download_metadata_path: str | None,
) -> dict[str, object]:
    source_checksum = file_sha256(source_path)
    destination_checksum = file_sha256(destination_path)

    if source_checksum == destination_checksum:
        if not is_managed_browser_download_path(source_path):
            source_path.unlink()
        asset.file_path = str(destination_path)
        asset.checksum = destination_checksum
        session.add(asset)
        create_job_log(
            session,
            attempt.background_job,
            event_type="asset_ingestion_idempotent",
            message="Provider download matched an existing canonical asset file.",
            attempt=attempt,
            metadata={
                "asset_id": str(asset.id),
                "file_path": str(destination_path),
                "checksum": destination_checksum,
            },
        )
        return _build_output_registration_payload(
            asset,
            source_download_path=str(source_path),
            source_download_metadata_path=source_download_metadata_path,
        )

    quarantine_path = _quarantine_conflicting_download(session, attempt, source_path)
    create_job_log(
        session,
        attempt.background_job,
        event_type="asset_ingestion_conflict",
        message=(
            "Provider download was quarantined because the canonical asset path exists "
            "with different contents."
        ),
        level="warning",
        attempt=attempt,
        metadata={
            "asset_id": str(asset.id),
            "existing_file_path": str(destination_path),
            "existing_checksum": destination_checksum,
            "incoming_checksum": source_checksum,
            "quarantine_path": quarantine_path,
            "source_download_metadata_path": source_download_metadata_path,
        },
    )
    raise ValueError(
        "Canonical asset path already exists with different contents. "
        "The incoming download was quarantined for manual review."
    )


def _write_generation_attempt_metadata(
    session: Session,
    job: BackgroundJob,
    attempt: GenerationAttempt,
    *,
    provider_payload: ProviderJobPayload,
    provider_job_id: str,
    selector_bundle: SelectorBundle | None,
    session_descriptor: BrowserSessionDescriptor | None,
) -> str:
    metadata_path = _resolve_project_storage_path(
        Path(
            build_project_storage_path(
                attempt.project_id,
                "metadata",
                "browser-jobs",
                f"job-{attempt.background_job_id}",
                f"attempt-{attempt.id}-request.json",
            )
        ),
        path_name="Browser attempt metadata path",
    )
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "metadata_type": "generation_attempt_request",
                "background_job_id": str(job.id),
                "generation_attempt_id": str(attempt.id),
                "project_id": str(attempt.project_id),
                "script_id": str(attempt.script_id),
                "scene_id": str(attempt.scene_id) if attempt.scene_id is not None else None,
                "job_type": job.job_type.value,
                "provider_name": attempt.provider_name.value,
                "provider_job_id": provider_job_id,
                "attempt_state": attempt.state.value,
                "input_payload_json": attempt.input_payload_json,
                "provider_payload": {
                    "project_id": provider_payload.project_id,
                    "scene_id": provider_payload.scene_id,
                    "prompt": provider_payload.prompt,
                    "metadata": provider_payload.metadata,
                },
                "selector_registry": (
                    selector_bundle_summary(selector_bundle)
                    if selector_bundle is not None
                    else None
                ),
                "browser_session": (
                    {
                        "profile_name": session_descriptor.profile_name,
                        "profile_path": str(session_descriptor.profile_path),
                        "debug_root": str(session_descriptor.debug_root),
                        "workspace_label": session_descriptor.workspace_label,
                        "selector_version": session_descriptor.selector_version,
                    }
                    if session_descriptor is not None
                    else None
                ),
                "planned_assets": [
                    {
                        "asset_id": str(asset.id),
                        "asset_type": asset.asset_type.value,
                        "planned_file_path": asset.file_path,
                        "scene_id": str(asset.scene_id) if asset.scene_id is not None else None,
                        "provider_name": (
                            asset.provider_name.value if asset.provider_name is not None else None
                        ),
                    }
                    for asset in get_attempt_assets(attempt)
                ],
                "created_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    create_job_log(
        session,
        job,
        event_type="generation_attempt_metadata_written",
        message="Generation attempt request metadata was written to project storage.",
        attempt=attempt,
        metadata={"metadata_path": str(metadata_path), "provider_job_id": provider_job_id},
    )
    session.commit()
    return str(metadata_path)


def _write_output_registration_payload(
    session: Session,
    attempt: GenerationAttempt,
    *,
    provider_job_id: str,
    output_registrations: list[dict[str, object]],
) -> str:
    registration_path = _resolve_project_storage_path(
        Path(
            build_project_storage_path(
                attempt.project_id,
                "metadata",
                "browser-jobs",
                f"job-{attempt.background_job_id}",
                f"attempt-{attempt.id}-outputs.json",
            )
        ),
        path_name="Browser output registration path",
    )
    registration_path.parent.mkdir(parents=True, exist_ok=True)
    registration_path.write_text(
        json.dumps(
            {
                "metadata_type": "generation_attempt_output_registration",
                "background_job_id": str(attempt.background_job_id),
                "generation_attempt_id": str(attempt.id),
                "project_id": str(attempt.project_id),
                "script_id": str(attempt.script_id),
                "scene_id": str(attempt.scene_id) if attempt.scene_id is not None else None,
                "provider_name": attempt.provider_name.value,
                "provider_job_id": provider_job_id,
                "outputs": output_registrations,
                "created_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    create_job_log(
        session,
        attempt.background_job,
        event_type="attempt_output_registration_written",
        message="Output asset registration payload was written to project storage.",
        attempt=attempt,
        metadata={
            "registration_payload_path": str(registration_path),
            "provider_job_id": provider_job_id,
        },
    )
    session.commit()
    return str(registration_path)


def _build_output_registration_payload(
    asset: Asset,
    *,
    source_download_path: str,
    source_download_metadata_path: str | None = None,
) -> dict[str, object]:
    return {
        "asset_id": str(asset.id),
        "asset_type": asset.asset_type.value,
        "project_id": str(asset.project_id),
        "script_id": str(asset.script_id),
        "scene_id": str(asset.scene_id) if asset.scene_id is not None else None,
        "generation_attempt_id": (
            str(asset.generation_attempt_id) if asset.generation_attempt_id is not None else None
        ),
        "provider_name": asset.provider_name.value if asset.provider_name is not None else None,
        "source_download_path": source_download_path,
        "source_download_metadata_path": source_download_metadata_path,
        "registered_file_path": asset.file_path,
        "checksum": asset.checksum,
        "mime_type": asset.mime_type,
        "duration_seconds": asset.duration_seconds,
        "width": asset.width,
        "height": asset.height,
    }


def _quarantine_mismatched_downloads(
    session: Session,
    attempt: GenerationAttempt,
    download_inputs: list[BrowserDownloadInput],
    *,
    expected_count: int,
) -> list[str]:
    quarantine_dir = _resolve_project_storage_path(
        Path(
            build_project_storage_path(
                attempt.project_id,
                "quarantine",
                f"job-{attempt.background_job_id}",
                f"attempt-{attempt.id}",
            )
        ),
        path_name="Browser quarantine path",
    )
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    quarantined_paths: list[str] = []
    for download_input in download_inputs:
        source_path = Path(
            download_input.staged_path
            if isinstance(download_input, TaggedDownload)
            else download_input
        )
        if not source_path.exists():
            continue

        destination_path = _unique_destination_path(quarantine_dir / source_path.name)
        _transfer_download_to_quarantine(source_path, destination_path)
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
            "actual_count": len(download_inputs),
            "quarantine_paths": quarantined_paths,
        },
    )
    return quarantined_paths


def _quarantine_conflicting_download(
    session: Session,
    attempt: GenerationAttempt,
    source_path: Path,
) -> str:
    quarantine_dir = _resolve_project_storage_path(
        Path(
            build_project_storage_path(
                attempt.project_id,
                "quarantine",
                f"job-{attempt.background_job_id}",
                f"attempt-{attempt.id}",
                "conflicts",
            )
        ),
        path_name="Browser conflicting-download quarantine path",
    )
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    destination_path = _unique_destination_path(quarantine_dir / source_path.name)
    _transfer_download_to_quarantine(source_path, destination_path)
    return str(destination_path)


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


def _transfer_download_to_destination(source_path: Path, destination_path: Path) -> None:
    if is_managed_browser_download_path(source_path):
        shutil.copy2(source_path, destination_path)
        return
    shutil.move(str(source_path), destination_path)


def _transfer_download_to_quarantine(source_path: Path, destination_path: Path) -> None:
    if is_managed_browser_download_path(source_path):
        shutil.copy2(source_path, destination_path)
        return
    shutil.move(str(source_path), destination_path)


def _pause_job_for_manual_intervention(
    session: Session,
    job: BackgroundJob,
    *,
    reason: str,
    category: str,
    attempt: GenerationAttempt | None = None,
    provider_job_id: str | None = None,
    session_descriptor: BrowserSessionDescriptor | None = None,
) -> None:
    safe_reason = sanitize_browser_message(reason)

    if attempt is not None and attempt.state != BackgroundJobState.COMPLETED:
        attempt.state = BackgroundJobState.WAITING_EXTERNAL
        attempt.error_message = safe_reason
        session.add(attempt)
        for asset in attempt.assets:
            if asset.status != AssetStatus.READY:
                asset.status = AssetStatus.PLANNED
                session.add(asset)

    _log_browser_job_event(
        session,
        job,
        event_type="browser_manual_intervention_detected",
        message="Browser automation requires manual intervention before it can continue.",
        level="warning",
        attempt=attempt,
        metadata={
            "provider_job_id": provider_job_id,
            "category": category,
            "reason": safe_reason,
            "recovery_hint": _manual_intervention_hint(category),
            "profile_name": (
                session_descriptor.profile_name if session_descriptor is not None else None
            ),
            "profile_path": (
                str(session_descriptor.profile_path) if session_descriptor is not None else None
            ),
        },
        commit=False,
    )
    mark_job_manual_intervention_required(session, job, reason=safe_reason)


def _manual_intervention_hint(category: str) -> str:
    if category == "authentication":
        return "Refresh the provider login in the saved browser profile, then retry or resume."
    if category == "captcha":
        return "Complete the human-verification challenge in the saved browser profile."
    if category == "verification":
        return "Complete the MFA or verification prompt in the provider session."
    return "Check the provider workspace manually before re-running the job."


def _capture_checkpoint_artifacts(
    session: Session,
    job: BackgroundJob,
    session_descriptor: BrowserSessionDescriptor,
    *,
    checkpoint_name: str,
    provider_job_id: str | None = None,
    attempt: GenerationAttempt | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    sanitized_metadata = sanitize_browser_metadata(metadata)
    artifact_paths = write_checkpoint_debug_artifacts(
        session_descriptor.debug_root,
        checkpoint_name=checkpoint_name,
        provider_job_id=provider_job_id,
        snapshot_html=_build_checkpoint_snapshot_html(
            session_descriptor,
            checkpoint_name=checkpoint_name,
            provider_job_id=provider_job_id,
            metadata=sanitized_metadata,
        ),
    )
    _log_browser_job_event(
        session,
        job,
        event_type="browser_checkpoint_artifacts_captured",
        message=f"Browser checkpoint artifacts were captured for {checkpoint_name}.",
        attempt=attempt,
        metadata={
            "checkpoint_name": checkpoint_name,
            "provider_job_id": provider_job_id,
            "artifact_paths": artifact_paths,
            **sanitized_metadata,
        },
    )


def _build_checkpoint_snapshot_html(
    session_descriptor: BrowserSessionDescriptor,
    *,
    checkpoint_name: str,
    provider_job_id: str | None,
    metadata: dict[str, object],
) -> str:
    snapshot_payload = {
        "provider_name": session_descriptor.provider_name.value,
        "provider_label": session_descriptor.provider_label,
        "checkpoint_name": checkpoint_name,
        "provider_job_id": provider_job_id,
        "workspace_label": session_descriptor.workspace_label,
        "profile_name": session_descriptor.profile_name,
        "profile_path": str(session_descriptor.profile_path),
        "selector_version": session_descriptor.selector_version,
        "metadata": metadata,
    }
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8" />',
            "  <title>CreatorOS Browser Checkpoint</title>",
            "</head>",
            "<body>",
            f"  <h1>{escape(session_descriptor.provider_label)} checkpoint</h1>",
            f"  <p>{escape(checkpoint_name)}</p>",
            "  <pre>",
            escape(json.dumps(snapshot_payload, indent=2, sort_keys=True)),
            "  </pre>",
            "</body>",
            "</html>",
        ]
    )


def _log_browser_job_event(
    session: Session,
    job: BackgroundJob,
    *,
    event_type: str,
    message: str,
    level: str = "info",
    attempt: GenerationAttempt | None = None,
    metadata: dict[str, object] | None = None,
    commit: bool = True,
) -> None:
    create_job_log(
        session,
        job,
        event_type=event_type,
        message=sanitize_browser_message(message),
        level=level,
        attempt=attempt,
        metadata=sanitize_browser_metadata(metadata),
    )
    if commit:
        session.commit()


def _refresh_job(session: Session, job: BackgroundJob) -> None:
    session.refresh(job, attribute_names=["generation_attempts"])


def _refresh_attempt(session: Session, attempt: GenerationAttempt) -> None:
    session.refresh(attempt, attribute_names=["assets"])


def _resolve_project_storage_path(value: Path, *, path_name: str) -> Path:
    return resolve_path_within_roots(
        value,
        allowed_roots=(Path("storage"),),
        path_name=path_name,
    )
