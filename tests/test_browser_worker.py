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
from workers.browser.runtime import run_pending_jobs


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

    audio_queue_response = client.post(
        f"/api/projects/{project_id}/generate/audio",
        json={"voice_label": "Warm guide"},
    )
    visuals_queue_response = client.post(f"/api/projects/{project_id}/generate/visuals", json={})

    assert audio_queue_response.status_code == 201
    assert visuals_queue_response.status_code == 201

    processed_jobs = run_pending_jobs(
        settings=BrowserWorkerSettings(
            browser_provider_mode="dry_run",
            browser_max_jobs_per_run=10,
            playwright_download_root=tmp_path / "downloads",
        ),
        session_factory=session_factory,
    )

    assert processed_jobs == 2

    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert len(jobs) == 2
    assert all(job["state"] == "completed" for job in jobs)
    assert all(job["progress_percent"] == 100 for job in jobs)

    assets_response = client.get(f"/api/projects/{project_id}/assets")
    assert assets_response.status_code == 200
    assets = assets_response.json()
    assert len(assets) == len(script["scenes"]) + 1
    assert all(asset["status"] == "ready" for asset in assets)

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
        assert "Dry-run visual artifact" in visual_path.read_text(encoding="utf-8")

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "asset_generation"

    app.dependency_overrides.clear()
