import json
from collections.abc import Generator
from pathlib import Path

import apps.api.models  # noqa: F401
from apps.api.db.base import Base
from apps.api.db.session import get_db
from apps.api.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from workers.browser.config import BrowserWorkerSettings
from workers.browser.runtime import run_pending_jobs as run_browser_jobs
from workers.media.config import MediaWorkerSettings
from workers.media.runtime import run_pending_jobs as run_media_jobs


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


def _create_project_for_tests(client: TestClient, brand_profile_id: str) -> str:
    response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": "Assemble a rough cut",
            "target_platform": "youtube_shorts",
            "objective": "Validate rough-cut media composition",
            "notes": None,
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


def _queue_and_finish_asset_jobs(
    *,
    client: TestClient,
    project_id: str,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    audio_response = client.post(
        f"/api/projects/{project_id}/generate/audio",
        json={"voice_label": "Warm guide"},
    )
    visual_response = client.post(f"/api/projects/{project_id}/generate/visuals", json={})
    assert audio_response.status_code == 201
    assert visual_response.status_code == 201

    processed_jobs = run_browser_jobs(
        settings=BrowserWorkerSettings(
            browser_provider_mode="dry_run",
            browser_max_jobs_per_run=10,
            playwright_download_root=tmp_path / "downloads",
        ),
        session_factory=session_factory,
    )
    assert processed_jobs == 2


def test_media_worker_composes_rough_cut_preview_after_asset_approval(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(client, brand_profile_id)
    script = _create_approved_script_for_tests(client, project_id)
    _queue_and_finish_asset_jobs(
        client=client,
        project_id=project_id,
        tmp_path=tmp_path,
        session_factory=session_factory,
    )

    approve_assets_response = client.post(f"/api/projects/{project_id}/assets/approve", json={})
    assert approve_assets_response.status_code == 200

    queue_response = client.post(f"/api/projects/{project_id}/compose/rough-cut")
    assert queue_response.status_code == 201
    assert queue_response.json()["job_type"] == "compose_rough_cut"

    processed_media_jobs = run_media_jobs(
        settings=MediaWorkerSettings(
            storage_root=tmp_path / "storage",
            downloads_root=tmp_path / "downloads",
        ),
        session_factory=session_factory,
    )
    assert processed_media_jobs == 1

    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs_response.status_code == 200
    rough_cut_job = next(
        job for job in jobs_response.json() if job["job_type"] == "compose_rough_cut"
    )
    assert rough_cut_job["state"] == "completed"
    assert rough_cut_job["progress_percent"] == 100

    manifest_path = tmp_path / rough_cut_job["payload_json"]["manifest_path"]
    subtitle_path = tmp_path / rough_cut_job["payload_json"]["subtitle_path"]
    ffmpeg_command_path = tmp_path / rough_cut_job["payload_json"]["ffmpeg_command_path"]
    assert manifest_path.exists()
    assert subtitle_path.exists()
    assert ffmpeg_command_path.exists()
    assert f'"script_id": "{script["id"]}"' in manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["timing_strategy"]["source"] == "narration_audio_wav"
    assert manifest["narration_asset"]["probed_duration_seconds"] is not None
    assert manifest["scenes"][-1]["end_seconds"] == manifest["total_duration_seconds"]
    assert "00:00:00,000 -->" in subtitle_path.read_text(encoding="utf-8")
    command_plan = json.loads(ffmpeg_command_path.read_text(encoding="utf-8"))
    assert command_plan["command"][0] == "ffmpeg"
    assert command_plan["export_profile"]["transition_seconds"] == 0.25
    assert command_plan["inputs"]["scenes"][0]["overlay_text"]

    assets_response = client.get(f"/api/projects/{project_id}/assets")
    assert assets_response.status_code == 200
    rough_cut_assets = [
        asset for asset in assets_response.json() if asset["asset_type"] == "rough_cut"
    ]
    subtitle_assets = [
        asset for asset in assets_response.json() if asset["asset_type"] == "subtitle_file"
    ]
    assert len(rough_cut_assets) == 1
    assert len(subtitle_assets) == 1
    rough_cut_asset = rough_cut_assets[0]
    subtitle_asset = subtitle_assets[0]
    assert rough_cut_asset["status"] == "ready"
    assert rough_cut_asset["mime_type"] == "text/html"
    assert rough_cut_asset["checksum"] is not None
    assert subtitle_asset["status"] == "ready"
    assert subtitle_asset["mime_type"] == "application/x-subrip"
    assert subtitle_asset["checksum"] is not None

    preview_path = tmp_path / rough_cut_asset["file_path"]
    assert preview_path.exists()
    assert "CreatorOS Rough Cut Preview" in preview_path.read_text(encoding="utf-8")

    content_response = client.get(f"/api/assets/{rough_cut_asset['id']}/content")
    assert content_response.status_code == 200
    assert content_response.headers["content-type"].startswith("text/html")
    assert "CreatorOS Rough Cut Preview" in content_response.text

    subtitle_response = client.get(f"/api/assets/{subtitle_asset['id']}/content")
    assert subtitle_response.status_code == 200
    assert subtitle_response.headers["content-type"].startswith("application/x-subrip")
    assert "00:00:00,000 -->" in subtitle_response.text

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "rough_cut_ready"

    app.dependency_overrides.clear()


def test_rough_cut_queue_requires_asset_approval(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(client, brand_profile_id)
    _create_approved_script_for_tests(client, project_id)
    _queue_and_finish_asset_jobs(
        client=client,
        project_id=project_id,
        tmp_path=tmp_path,
        session_factory=session_factory,
    )

    queue_response = client.post(f"/api/projects/{project_id}/compose/rough-cut")
    assert queue_response.status_code == 409
    assert "Approve the current asset set" in _error_message(queue_response)

    app.dependency_overrides.clear()


def test_media_worker_registers_mp4_asset_when_ffmpeg_render_is_enabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_ffmpeg_command(command: list[str]) -> None:
        Path(command[-1]).write_bytes(b"fake mp4")

    monkeypatch.setattr("workers.media.runtime.run_ffmpeg_command", fake_run_ffmpeg_command)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(client, brand_profile_id)
    _create_approved_script_for_tests(client, project_id)
    _queue_and_finish_asset_jobs(
        client=client,
        project_id=project_id,
        tmp_path=tmp_path,
        session_factory=session_factory,
    )

    approve_assets_response = client.post(f"/api/projects/{project_id}/assets/approve", json={})
    assert approve_assets_response.status_code == 200

    queue_response = client.post(f"/api/projects/{project_id}/compose/rough-cut")
    assert queue_response.status_code == 201

    processed_media_jobs = run_media_jobs(
        settings=MediaWorkerSettings(
            storage_root=tmp_path / "storage",
            downloads_root=tmp_path / "downloads",
            media_enable_ffmpeg_render=True,
        ),
        session_factory=session_factory,
    )
    assert processed_media_jobs == 1

    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    rough_cut_job = next(
        job for job in jobs_response.json() if job["job_type"] == "compose_rough_cut"
    )
    assert rough_cut_job["state"] == "completed"
    assert rough_cut_job["payload_json"]["ffmpeg_rendered"] is True
    assert rough_cut_job["payload_json"]["video_asset_id"] is not None

    command_plan_path = tmp_path / rough_cut_job["payload_json"]["ffmpeg_command_path"]
    command_plan = json.loads(command_plan_path.read_text(encoding="utf-8"))
    assert command_plan["enabled"] is True

    assets_response = client.get(f"/api/projects/{project_id}/assets")
    video_assets = [asset for asset in assets_response.json() if asset["mime_type"] == "video/mp4"]
    assert len(video_assets) == 1
    video_asset = video_assets[0]
    assert video_asset["asset_type"] == "rough_cut"
    assert video_asset["status"] == "ready"
    assert video_asset["checksum"] is not None
    assert (tmp_path / video_asset["file_path"]).read_bytes() == b"fake mp4"

    content_response = client.get(f"/api/assets/{video_asset['id']}/content")
    assert content_response.status_code == 200
    assert content_response.headers["content-type"].startswith("video/mp4")

    app.dependency_overrides.clear()


def test_media_worker_retries_transient_ffmpeg_timeout_once(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    ffmpeg_calls = {"count": 0}

    def flaky_run_ffmpeg_command(command: list[str]) -> None:
        ffmpeg_calls["count"] += 1
        if ffmpeg_calls["count"] == 1:
            raise RuntimeError("FFmpeg timed out while rendering preview.")
        Path(command[-1]).write_bytes(b"retry mp4")

    monkeypatch.setattr("workers.media.runtime.run_ffmpeg_command", flaky_run_ffmpeg_command)

    session_factory = _create_test_session()
    client = _make_test_client(session_factory)

    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(client, brand_profile_id)
    _create_approved_script_for_tests(client, project_id)
    _queue_and_finish_asset_jobs(
        client=client,
        project_id=project_id,
        tmp_path=tmp_path,
        session_factory=session_factory,
    )

    approve_assets_response = client.post(f"/api/projects/{project_id}/assets/approve", json={})
    assert approve_assets_response.status_code == 200

    queue_response = client.post(f"/api/projects/{project_id}/compose/rough-cut")
    assert queue_response.status_code == 201

    processed_media_jobs = run_media_jobs(
        settings=MediaWorkerSettings(
            storage_root=tmp_path / "storage",
            downloads_root=tmp_path / "downloads",
            media_enable_ffmpeg_render=True,
        ),
        session_factory=session_factory,
    )
    assert processed_media_jobs == 1
    assert ffmpeg_calls["count"] == 2

    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    rough_cut_job = next(
        job for job in jobs_response.json() if job["job_type"] == "compose_rough_cut"
    )
    assert rough_cut_job["state"] == "completed"

    detail_response = client.get(f"/api/jobs/{rough_cut_job['id']}")
    assert detail_response.status_code == 200
    assert any(
        log["event_type"] == "media_render_retry_scheduled"
        for log in detail_response.json()["job_logs"]
    )

    app.dependency_overrides.clear()
