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
    jobs = jobs_response.json()
    assert len(jobs) == 2
    assert all(job["state"] == "completed" for job in jobs)
    assert all(job["progress_percent"] == 100 for job in jobs)
    for job in jobs:
        detail_response = client.get(f"/api/jobs/{job['id']}")
        assert detail_response.status_code == 200
        event_types = {log["event_type"] for log in detail_response.json()["job_logs"]}
        assert "job_claimed" in event_types
        assert "job_completed" in event_types
        assert "debug_artifacts_captured" in event_types
        assert "job_progress_updated" in event_types
        debug_logs = [
            log
            for log in detail_response.json()["job_logs"]
            if log["event_type"] == "debug_artifacts_captured"
        ]
        assert debug_logs
        for debug_path in debug_logs[0]["metadata_json"]["debug_artifact_paths"]:
            assert (tmp_path / debug_path).exists()

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
