import json
from collections.abc import Generator
from pathlib import Path
from uuid import UUID

import apps.api.models  # noqa: F401
import pytest
from apps.api.db.base import Base
from apps.api.db.session import get_db
from apps.api.main import app
from apps.api.models.job_log import JobLog
from apps.api.services.background_jobs import get_background_job
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from workers.browser.config import BrowserWorkerSettings
from workers.browser.providers import DryRunElevenLabsProvider, ProviderJobPayload
from workers.browser.providers.debug_artifacts import write_failure_debug_artifacts
from workers.browser.runtime import _materialize_attempt_outputs, run_pending_jobs


def _create_test_session() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _override_get_db(test_session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = test_session_factory()
    try:
        yield session
    finally:
        session.close()


def _make_test_client(
    test_session_factory: sessionmaker[Session],
) -> TestClient:
    def override_get_db() -> Generator[Session, None, None]:
        yield from _override_get_db(test_session_factory)

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _error_message(response) -> str:
    payload = response.json()
    if "error" in payload:
        return str(payload["error"]["message"])
    return str(payload["detail"])


def _create_brand_profile_for_tests(client: TestClient) -> str:
    response = client.post(
        "/api/brand-profiles",
        json={
            "channel_name": "Creator Lab",
            "niche": "AI productivity",
            "target_audience": "Solo founders",
            "tone": "Direct",
            "hook_style": "Question first",
            "cta_style": "Ask for comments",
            "visual_style": "Screen recordings",
            "posting_preferences_json": {"platforms": ["youtube_shorts"]},
        },
    )
    return response.json()["id"]


def _create_project_for_tests(
    client: TestClient,
    brand_profile_id: str,
    *,
    title: str,
    objective: str,
    notes: str | None,
) -> str:
    response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": title,
            "target_platform": "youtube_shorts",
            "objective": objective,
            "notes": notes,
        },
    )
    return response.json()["id"]


def _create_approved_script_for_tests(client: TestClient, project_id: str) -> dict[str, object]:
    ideas_response = client.post(f"/api/projects/{project_id}/ideas/generate")
    approved_idea_id = ideas_response.json()[0]["id"]
    client.post(f"/api/ideas/{approved_idea_id}/approve", json={})

    script_response = client.post(f"/api/projects/{project_id}/scripts/generate", json={})
    script = script_response.json()
    client.post(f"/api/scripts/{script['id']}/approve", json={})
    return script


def _queue_asset_jobs(client: TestClient, project_id: str) -> None:
    audio_queue_response = client.post(
        f"/api/projects/{project_id}/generate/audio",
        json={"voice_label": "Warm guide"},
    )
    visuals_queue_response = client.post(f"/api/projects/{project_id}/generate/visuals", json={})

    assert audio_queue_response.status_code == 201
    assert visuals_queue_response.status_code == 201


def _run_browser_worker(
    *,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> int:
    return run_pending_jobs(
        settings=BrowserWorkerSettings(
            browser_provider_mode="dry_run",
            browser_max_jobs_per_run=10,
            playwright_download_root=tmp_path / "downloads",
        ),
        session_factory=session_factory,
    )


def test_browser_worker_processes_queued_generation_jobs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Process queued assets locally",
        objective="Validate the browser worker dry-run execution path",
        notes=None,
    )
    script = _create_approved_script_for_tests(client, project_id)

    _queue_asset_jobs(client, project_id)

    processed_jobs = _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory)

    assert processed_jobs == 2

    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs_response.status_code == 200
    jobs = [
        job
        for job in jobs_response.json()
        if job["job_type"] in {"generate_audio_browser", "generate_visuals_browser"}
    ]
    assert len(jobs) == 2
    assert all(job["state"] == "completed" for job in jobs)
    assert all(job["progress_percent"] == 100 for job in jobs)
    for job in jobs:
        detail_response = client.get(f"/api/jobs/{job['id']}")
        assert detail_response.status_code == 200
        event_types = {log["event_type"] for log in detail_response.json()["job_logs"]}
        assert "browser_selector_registry_loaded" in event_types
        assert "browser_session_prepared" in event_types
        assert "browser_session_validated" in event_types
        assert "browser_workspace_opened" in event_types
        assert "browser_checkpoint_artifacts_captured" in event_types
        assert "browser_downloads_tagged" in event_types
        assert "job_claimed" in event_types
        assert "job_completed" in event_types
        assert "debug_artifacts_captured" in event_types
        assert "generation_attempt_metadata_written" in event_types
        assert "attempt_output_registration_written" in event_types
        assert "job_progress_updated" in event_types
        selector_logs = [
            log
            for log in detail_response.json()["job_logs"]
            if log["event_type"] == "browser_selector_registry_loaded"
        ]
        debug_logs = [
            log
            for log in detail_response.json()["job_logs"]
            if log["event_type"] == "debug_artifacts_captured"
        ]
        checkpoint_logs = [
            log
            for log in detail_response.json()["job_logs"]
            if log["event_type"] == "browser_checkpoint_artifacts_captured"
        ]
        download_logs = [
            log
            for log in detail_response.json()["job_logs"]
            if log["event_type"] == "browser_downloads_tagged"
        ]
        metadata_logs = [
            log
            for log in detail_response.json()["job_logs"]
            if log["event_type"] == "generation_attempt_metadata_written"
        ]
        registration_logs = [
            log
            for log in detail_response.json()["job_logs"]
            if log["event_type"] == "attempt_output_registration_written"
        ]
        assert selector_logs
        assert debug_logs
        assert checkpoint_logs
        assert download_logs
        assert metadata_logs
        assert registration_logs
        assert selector_logs[0]["metadata_json"]["version"] == "v1"
        assert selector_logs[0]["metadata_json"]["selector_keys"]
        for debug_path in debug_logs[0]["metadata_json"]["debug_artifact_paths"]:
            assert (tmp_path / debug_path).exists()
        for checkpoint_log in checkpoint_logs:
            assert checkpoint_log["metadata_json"]["checkpoint_name"]
            for artifact_path in checkpoint_log["metadata_json"]["artifact_paths"]:
                assert (tmp_path / artifact_path).exists()
        for download_log in download_logs:
            assert download_log["metadata_json"]["download_count"] >= 1
            for staged_path in download_log["metadata_json"]["staged_download_paths"]:
                assert (tmp_path / staged_path).exists()
            for metadata_path in download_log["metadata_json"]["download_metadata_paths"]:
                download_metadata_path = tmp_path / metadata_path
                assert download_metadata_path.exists()
                download_metadata = json.loads(download_metadata_path.read_text(encoding="utf-8"))
                assert download_metadata["provider_job_id"]
                assert download_metadata["staged_path"]
        for metadata_log in metadata_logs:
            metadata_path = tmp_path / metadata_log["metadata_json"]["metadata_path"]
            assert metadata_path.exists()
            metadata_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            assert metadata_payload["provider_job_id"]
            assert (
                metadata_payload["generation_attempt_id"] == metadata_log["generation_attempt_id"]
            )
            assert metadata_payload["planned_assets"]
            assert metadata_payload["selector_registry"]["version"] == "v1"
            assert metadata_payload["browser_session"]["profile_path"]
        for registration_log in registration_logs:
            registration_path = (
                tmp_path / registration_log["metadata_json"]["registration_payload_path"]
            )
            assert registration_path.exists()
            registration_payload = json.loads(registration_path.read_text(encoding="utf-8"))
            assert registration_payload["provider_job_id"]
            assert (
                registration_payload["generation_attempt_id"]
                == registration_log["generation_attempt_id"]
            )
            assert registration_payload["outputs"]
            assert registration_payload["outputs"][0]["source_download_metadata_path"]

    assets_response = client.get(f"/api/projects/{project_id}/assets")
    assert assets_response.status_code == 200
    assets = assets_response.json()
    assert len(assets) == len(script["scenes"]) + 1
    assert all(asset["status"] == "ready" for asset in assets)
    assert all(asset["checksum"] for asset in assets)

    narration_assets = [asset for asset in assets if asset["asset_type"] == "narration_audio"]
    visual_assets = [asset for asset in assets if asset["asset_type"] == "scene_image"]

    assert len(narration_assets) == 1
    assert len(visual_assets) == len(script["scenes"])

    narration_path = tmp_path / narration_assets[0]["file_path"]
    assert narration_path.exists()
    assert narration_path.suffix == ".wav"
    assert narration_path.stat().st_size > 0

    for asset in visual_assets:
        visual_path = tmp_path / asset["file_path"]
        assert visual_path.exists()
        assert visual_path.suffix == ".svg"
        assert asset["width"] == 1080
        assert asset["height"] == 1920
        assert "Dry-run visual artifact" in visual_path.read_text(encoding="utf-8")

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "asset_pending_approval"

    app.dependency_overrides.clear()


class FailingBrowserProvider:
    def __init__(self, debug_root: Path) -> None:
        self._debug_root = debug_root

    def ensure_session(self) -> None:
        return None

    def open_workspace(self) -> None:
        return None

    def submit_job(self, payload: ProviderJobPayload) -> str:
        return f"failing-provider-{payload.project_id}"

    def wait_for_completion(self, job_id: str) -> None:
        raise RuntimeError(f"Selector #render-button timed out for {job_id}")

    def collect_downloads(self, job_id: str) -> list[str]:
        return []

    def capture_debug_artifacts(self, job_id: str) -> list[str]:
        return []

    def capture_failure_artifacts(self, job_id: str | None, error: Exception) -> list[str]:
        return write_failure_debug_artifacts(
            self._debug_root,
            provider_job_id=job_id,
            error=error,
            snapshot_html="<html><body>provider panel at failure</body></html>",
        )


class RetryOnceBrowserProvider:
    def __init__(self, download_root: Path, *, failure_message: str) -> None:
        self._download_root = download_root
        self._debug_root = download_root / "debug"
        self._download_root.mkdir(parents=True, exist_ok=True)
        self._debug_root.mkdir(parents=True, exist_ok=True)
        self._failure_message = failure_message
        self._submitted_jobs: dict[str, ProviderJobPayload] = {}
        self._wait_calls = 0

    def ensure_session(self) -> None:
        return None

    def open_workspace(self) -> None:
        return None

    def submit_job(self, payload: ProviderJobPayload) -> str:
        job_id = f"retry-once-{len(self._submitted_jobs) + 1}"
        self._submitted_jobs[job_id] = payload
        return job_id

    def wait_for_completion(self, job_id: str) -> None:
        self._wait_calls += 1
        if self._wait_calls == 1:
            raise RuntimeError(f"{self._failure_message} for {job_id}")

    def collect_downloads(self, job_id: str) -> list[str]:
        output_path = self._download_root / f"{job_id}.wav"
        output_path.write_bytes(b"retry succeeded")
        return [str(output_path)]

    def capture_debug_artifacts(self, job_id: str) -> list[str]:
        return []

    def capture_failure_artifacts(self, job_id: str | None, error: Exception) -> list[str]:
        return write_failure_debug_artifacts(
            self._debug_root,
            provider_job_id=job_id,
            error=error,
            snapshot_html="<html><body>retryable provider failure</body></html>",
        )


class ManualInterventionBrowserProvider:
    def __init__(self, debug_root: Path) -> None:
        self._debug_root = debug_root
        self._download_root = debug_root / "downloads"
        self._debug_root.mkdir(parents=True, exist_ok=True)
        self._download_root.mkdir(parents=True, exist_ok=True)

    def ensure_session(self) -> None:
        return None

    def open_workspace(self) -> None:
        return None

    def submit_job(self, payload: ProviderJobPayload) -> str:
        return f"manual-intervention-{payload.project_id}"

    def wait_for_completion(self, job_id: str) -> None:
        raise RuntimeError(
            f"Login expired cookie=session-secret token=raw-token for provider job {job_id}"
        )

    def collect_downloads(self, job_id: str) -> list[str]:
        return []

    def capture_debug_artifacts(self, job_id: str) -> list[str]:
        return []

    def capture_failure_artifacts(self, job_id: str | None, error: Exception) -> list[str]:
        return write_failure_debug_artifacts(
            self._debug_root,
            provider_job_id=job_id,
            error=error,
            snapshot_html=f"<html><body>{error}</body></html>",
        )


def test_browser_worker_captures_failure_screenshot_and_html_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Capture browser failures",
        objective="Validate provider failure debug artifacts",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    monkeypatch.setattr(
        "workers.browser.runtime._get_provider",
        lambda settings, job, selector_bundle=None, session_descriptor=None: FailingBrowserProvider(
            tmp_path / "downloads" / "debug" / "failing"
        ),
    )

    processed_jobs = _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory)
    assert processed_jobs == 1

    detail_response = client.get(f"/api/jobs/{job_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["job"]["state"] == "failed"
    event_types = {log["event_type"] for log in detail["job_logs"]}
    assert "browser_failure_artifacts_captured" in event_types
    assert "job_failed" in event_types

    failure_log = next(
        log
        for log in detail["job_logs"]
        if log["event_type"] == "browser_failure_artifacts_captured"
    )
    artifact_paths = failure_log["metadata_json"]["failure_artifact_paths"]
    assert len(artifact_paths) == 2

    screenshot_path = next(Path(path) for path in artifact_paths if path.endswith(".png"))
    snapshot_path = next(Path(path) for path in artifact_paths if path.endswith(".html"))
    assert screenshot_path.exists()
    assert screenshot_path.read_bytes().startswith(b"\x89PNG")
    assert snapshot_path.exists()
    assert "provider panel at failure" in snapshot_path.read_text(encoding="utf-8")

    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "failure_message",
    ["Provider timed out while waiting for render", "Selector #render-button not found"],
)
def test_browser_worker_retries_retryable_provider_failures_once(
    tmp_path: Path,
    monkeypatch,
    failure_message: str,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Retry provider failures",
        objective="Retry timeout and selector errors once before failing",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    monkeypatch.setattr(
        "workers.browser.runtime._get_provider",
        lambda settings, job, selector_bundle=None, session_descriptor=None: (
            RetryOnceBrowserProvider(
                tmp_path / "downloads",
                failure_message=failure_message,
            )
        ),
    )

    processed_jobs = _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory)
    assert processed_jobs == 1

    detail_response = client.get(f"/api/jobs/{job_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["job"]["state"] == "completed"
    assert any(
        log["event_type"] == "browser_provider_retry_scheduled" for log in detail["job_logs"]
    )
    assert any(
        log["event_type"] == "browser_failure_artifacts_captured" for log in detail["job_logs"]
    )

    app.dependency_overrides.clear()


def test_browser_worker_pauses_for_manual_intervention_without_leaking_secrets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Pause for auth recovery",
        objective="Validate manual intervention handling for browser auth issues",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    monkeypatch.setattr(
        "workers.browser.runtime._get_provider",
        lambda settings, job, selector_bundle=None, session_descriptor=None: (
            ManualInterventionBrowserProvider(tmp_path / "downloads" / "debug" / "manual")
        ),
    )

    processed_jobs = _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory)
    assert processed_jobs == 1

    detail_response = client.get(f"/api/jobs/{job_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["job"]["state"] == "waiting_external"
    assert "[redacted]" in detail["job"]["error_message"]
    assert "session-secret" not in detail["job"]["error_message"]
    assert "raw-token" not in detail["job"]["error_message"]
    assert detail["generation_attempts"][0]["state"] == "waiting_external"
    assert detail["related_assets"][0]["status"] == "planned"
    event_types = {log["event_type"] for log in detail["job_logs"]}
    assert "browser_manual_intervention_detected" in event_types
    assert "manual_intervention_required" in event_types
    assert "job_failed" not in event_types

    serialized_logs = json.dumps(detail["job_logs"])
    assert "session-secret" not in serialized_logs
    assert "raw-token" not in serialized_logs
    assert "[redacted]" in serialized_logs

    failure_log = next(
        log
        for log in detail["job_logs"]
        if log["event_type"] == "browser_failure_artifacts_captured"
    )
    snapshot_path = next(
        Path(path)
        for path in failure_log["metadata_json"]["failure_artifact_paths"]
        if path.endswith(".html")
    )
    assert snapshot_path.exists()
    snapshot_html = snapshot_path.read_text(encoding="utf-8")
    assert "session-secret" not in snapshot_html
    assert "raw-token" not in snapshot_html
    assert "[redacted]" in snapshot_html

    app.dependency_overrides.clear()


def test_browser_worker_logs_duplicate_asset_checksums(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Detect duplicate visuals",
        objective="Validate duplicate checksum observability",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    first_queue_response = client.post(f"/api/projects/{project_id}/generate/visuals", json={})
    assert first_queue_response.status_code == 201
    assert _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory) == 1

    second_queue_response = client.post(f"/api/projects/{project_id}/generate/visuals", json={})
    assert second_queue_response.status_code == 201
    second_job_id = second_queue_response.json()["id"]
    assert _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory) == 1

    detail_response = client.get(f"/api/jobs/{second_job_id}")
    assert detail_response.status_code == 200
    duplicate_logs = [
        log
        for log in detail_response.json()["job_logs"]
        if log["event_type"] == "duplicate_asset_detected"
    ]
    assert duplicate_logs
    assert duplicate_logs[0]["metadata_json"]["duplicate_asset_ids"]

    app.dependency_overrides.clear()


def test_browser_worker_quarantines_mismatched_download_counts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Quarantine mismatched downloads",
        objective="Validate download mismatch safety",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201

    first_download = tmp_path / "first-unexpected.wav"
    second_download = tmp_path / "second-unexpected.wav"
    first_download.write_bytes(b"first")
    second_download.write_bytes(b"second")

    with session_factory() as session:
        job = get_background_job(session, UUID(queue_response.json()["id"]))
        assert job is not None
        attempt = job.generation_attempts[0]

        with pytest.raises(ValueError, match="Quarantined 2 file"):
            _materialize_attempt_outputs(
                session,
                attempt,
                [str(first_download), str(second_download)],
            )
        session.commit()

        quarantine_root = tmp_path / "storage" / "projects" / project_id / "quarantine"
        quarantined_files = [path for path in quarantine_root.glob("**/*") if path.is_file()]
        assert len(quarantined_files) == 2
        assert not first_download.exists()
        assert not second_download.exists()

        quarantine_log = session.scalar(
            select(JobLog).where(JobLog.event_type == "downloads_quarantined")
        )
        assert quarantine_log is not None
        assert quarantine_log.metadata_json["expected_count"] == 1
        assert quarantine_log.metadata_json["actual_count"] == 2

    app.dependency_overrides.clear()


def test_browser_worker_ingestion_is_idempotent_for_existing_matching_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Idempotent download ingestion",
        objective="Avoid overwriting matching canonical files",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201

    incoming_download = tmp_path / "provider-output.wav"
    incoming_download.write_bytes(b"same audio bytes")

    with session_factory() as session:
        job = get_background_job(session, UUID(queue_response.json()["id"]))
        assert job is not None
        attempt = job.generation_attempts[0]
        asset = attempt.assets[0]
        assert asset.file_path is not None

        canonical_path = tmp_path / asset.file_path
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        canonical_path.write_bytes(b"same audio bytes")

        _materialize_attempt_outputs(session, attempt, [str(incoming_download)])
        session.commit()

        assert not incoming_download.exists()
        assert canonical_path.read_bytes() == b"same audio bytes"
        assert asset.checksum is not None

        idempotent_log = session.scalar(
            select(JobLog).where(JobLog.event_type == "asset_ingestion_idempotent")
        )
        assert idempotent_log is not None
        assert idempotent_log.metadata_json["asset_id"] == str(asset.id)

    app.dependency_overrides.clear()


def test_browser_worker_quarantines_conflicting_canonical_asset_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Conflicting download ingestion",
        objective="Never overwrite canonical files with mismatched downloads",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201

    incoming_download = tmp_path / "provider-output.wav"
    incoming_download.write_bytes(b"different incoming bytes")

    with session_factory() as session:
        job = get_background_job(session, UUID(queue_response.json()["id"]))
        assert job is not None
        attempt = job.generation_attempts[0]
        asset = attempt.assets[0]
        assert asset.file_path is not None

        canonical_path = tmp_path / asset.file_path
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        canonical_path.write_bytes(b"existing canonical bytes")

        with pytest.raises(ValueError, match="Canonical asset path already exists"):
            _materialize_attempt_outputs(session, attempt, [str(incoming_download)])
        session.commit()

        assert canonical_path.read_bytes() == b"existing canonical bytes"
        assert not incoming_download.exists()
        quarantine_root = tmp_path / "storage" / "projects" / project_id / "quarantine"
        quarantined_files = [path for path in quarantine_root.glob("**/*") if path.is_file()]
        assert len(quarantined_files) == 1
        assert quarantined_files[0].read_bytes() == b"different incoming bytes"

        conflict_log = session.scalar(
            select(JobLog).where(JobLog.event_type == "asset_ingestion_conflict")
        )
        assert conflict_log is not None
        assert conflict_log.metadata_json["asset_id"] == str(asset.id)

    app.dependency_overrides.clear()


def test_browser_worker_rejects_canonical_asset_paths_outside_storage_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Reject escaped asset path",
        objective="Validate browser ingest path boundary checks",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201

    incoming_download = tmp_path / "provider-output.wav"
    incoming_download.write_bytes(b"safe bytes")

    with session_factory() as session:
        job = get_background_job(session, UUID(queue_response.json()["id"]))
        assert job is not None
        attempt = job.generation_attempts[0]
        asset = attempt.assets[0]
        asset.file_path = str(tmp_path / "outside-storage" / "escaped.wav")
        session.add(asset)
        session.commit()

        with pytest.raises(ValueError, match="Browser asset destination path must stay"):
            _materialize_attempt_outputs(session, attempt, [str(incoming_download)])

    app.dependency_overrides.clear()


def test_browser_debug_artifacts_redact_secret_like_values(tmp_path: Path) -> None:
    provider = DryRunElevenLabsProvider(tmp_path / "downloads")
    job_id = provider.submit_job(
        ProviderJobPayload(
            project_id="project-1",
            prompt="Narration token=raw-token api_key=raw-key",
        )
    )

    prompt_artifacts = provider.capture_debug_artifacts(job_id)
    prompt_text = Path(prompt_artifacts[0]).read_text(encoding="utf-8")
    assert "raw-token" not in prompt_text
    assert "raw-key" not in prompt_text
    assert "[redacted]" in prompt_text

    failure_artifacts = write_failure_debug_artifacts(
        tmp_path / "downloads" / "debug",
        provider_job_id=job_id,
        error=RuntimeError("cookie=session-secret"),
        snapshot_html="<html><body>token=raw-token</body></html>",
    )
    failure_html = Path(failure_artifacts[1]).read_text(encoding="utf-8")
    assert "raw-token" not in failure_html
    assert "session-secret" not in failure_html
    assert "[redacted]" in failure_html


def test_asset_review_routes_update_status_and_approval_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Review generated assets",
        objective="Validate asset approval and rejection flow",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    _queue_asset_jobs(client, project_id)
    _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory)

    blocked_transition_response = client.post(
        f"/api/projects/{project_id}/transition",
        json={"target_status": "rough_cut_ready"},
    )
    assert blocked_transition_response.status_code == 409
    assert "asset set has been explicitly approved" in _error_message(blocked_transition_response)

    approve_assets_response = client.post(f"/api/projects/{project_id}/assets/approve", json={})
    assert approve_assets_response.status_code == 200
    assert approve_assets_response.json()["stage"] == "assets"
    assert approve_assets_response.json()["decision"] == "approved"

    approvals_response = client.get(f"/api/projects/{project_id}/approvals")
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()
    assert any(
        approval["stage"] == "assets" and approval["decision"] == "approved"
        for approval in approvals
    )

    blocked_until_media_response = client.post(
        f"/api/projects/{project_id}/transition",
        json={"target_status": "rough_cut_ready"},
    )
    assert blocked_until_media_response.status_code == 409
    assert "media worker has created a rough-cut artifact" in _error_message(
        blocked_until_media_response
    )

    app.dependency_overrides.clear()


def test_asset_level_review_and_regeneration_routes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Regenerate one asset",
        objective="Validate per-asset review actions",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    _queue_asset_jobs(client, project_id)
    _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory)

    assets_response = client.get(f"/api/projects/{project_id}/assets")
    assert assets_response.status_code == 200
    visual_asset = next(
        asset for asset in assets_response.json() if asset["asset_type"] == "scene_image"
    )

    get_asset_response = client.get(f"/api/assets/{visual_asset['id']}")
    assert get_asset_response.status_code == 200
    assert get_asset_response.json()["id"] == visual_asset["id"]

    approve_asset_response = client.post(f"/api/assets/{visual_asset['id']}/approve", json={})
    assert approve_asset_response.status_code == 200
    assert approve_asset_response.json()["target_type"] == "asset"
    assert approve_asset_response.json()["decision"] == "approved"

    reject_asset_response = client.post(
        f"/api/assets/{visual_asset['id']}/reject",
        json={"feedback_notes": "Need a clearer image."},
    )
    assert reject_asset_response.status_code == 200
    assert reject_asset_response.json()["target_type"] == "asset"
    assert reject_asset_response.json()["decision"] == "rejected"

    rejected_asset_response = client.get(f"/api/assets/{visual_asset['id']}")
    assert rejected_asset_response.status_code == 200
    assert rejected_asset_response.json()["status"] == "rejected"

    regenerate_response = client.post(
        f"/api/assets/{visual_asset['id']}/regenerate",
        json={"feedback_notes": "Try a more specific visual direction."},
    )
    assert regenerate_response.status_code == 201
    regenerated_job = regenerate_response.json()
    assert regenerated_job["job_type"] == "generate_visuals_browser"
    assert regenerated_job["payload_json"]["scene_count"] == 1
    assert regenerated_job["payload_json"]["scene_ids"] == [visual_asset["scene_id"]]

    updated_assets_response = client.get(f"/api/projects/{project_id}/assets")
    assert updated_assets_response.status_code == 200
    scene_assets = [
        asset
        for asset in updated_assets_response.json()
        if asset["scene_id"] == visual_asset["scene_id"] and asset["asset_type"] == "scene_image"
    ]
    assert any(asset["status"] == "rejected" for asset in scene_assets)
    assert any(asset["status"] == "planned" for asset in scene_assets)

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "asset_generation"

    app.dependency_overrides.clear()


def test_asset_rejection_and_content_route_work_after_generation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Reject generated assets",
        objective="Validate review rejection and content previews",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    _queue_asset_jobs(client, project_id)
    _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory)

    assets_response = client.get(f"/api/projects/{project_id}/assets")
    assets = assets_response.json()
    visual_asset = next(asset for asset in assets if asset["asset_type"] == "scene_image")

    content_response = client.get(f"/api/assets/{visual_asset['id']}/content")
    assert content_response.status_code == 200
    assert content_response.headers["content-type"].startswith("image/svg+xml")
    assert "Dry-run visual artifact" in content_response.text

    reject_assets_response = client.post(
        f"/api/projects/{project_id}/assets/reject",
        json={"feedback_notes": "These visuals need a stronger direction."},
    )
    assert reject_assets_response.status_code == 200
    assert reject_assets_response.json()["stage"] == "assets"
    assert reject_assets_response.json()["decision"] == "rejected"

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "asset_generation"

    updated_assets_response = client.get(f"/api/projects/{project_id}/assets")
    updated_assets = updated_assets_response.json()
    assert all(
        asset["status"] == "rejected" for asset in updated_assets if asset["status"] != "planned"
    )

    app.dependency_overrides.clear()
