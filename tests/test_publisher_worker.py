from collections.abc import Generator
from pathlib import Path
from uuid import UUID

import apps.api.models  # noqa: F401
from apps.api.db.base import Base
from apps.api.db.session import get_db
from apps.api.main import app
from apps.api.models.asset import Asset
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.schemas.enums import AssetStatus, AssetType, ProjectStatus, ProviderName
from apps.api.services.publish_adapters import resolve_publish_adapter_name
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from workers.publisher.config import PublisherWorkerSettings
from workers.publisher.runtime import run_pending_jobs


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
            "title": "Publisher handoff",
            "target_platform": "youtube_shorts",
            "objective": "Generate a manual publish handoff",
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


def _move_project_to_final_review_for_tests(
    session_factory: sessionmaker[Session],
    *,
    project_id: str,
    script_id: str,
) -> None:
    with session_factory() as session:
        project = session.get(Project, UUID(project_id))
        script = session.get(ProjectScript, UUID(script_id))
        assert project is not None
        assert script is not None

        rough_cut = Asset(
            user_id=project.user_id,
            project_id=project.id,
            script_id=script.id,
            scene_id=None,
            generation_attempt_id=None,
            asset_type=AssetType.ROUGH_CUT,
            status=AssetStatus.READY,
            provider_name=ProviderName.LOCAL_MEDIA,
            file_path=f"storage/projects/{project.id}/rough-cuts/test-final.html",
            mime_type="text/html",
            duration_seconds=script.estimated_duration_seconds,
            width=1080,
            height=1920,
            checksum="test-final-checksum",
        )
        thumbnail = Asset(
            user_id=project.user_id,
            project_id=project.id,
            script_id=script.id,
            scene_id=None,
            generation_attempt_id=None,
            asset_type=AssetType.THUMBNAIL,
            status=AssetStatus.READY,
            provider_name=ProviderName.LOCAL_MEDIA,
            file_path=f"storage/projects/{project.id}/thumbnails/test-thumbnail.png",
            mime_type="image/png",
            duration_seconds=None,
            width=1080,
            height=1920,
            checksum="test-thumbnail-checksum",
        )
        project.status = ProjectStatus.FINAL_PENDING_APPROVAL
        session.add(rough_cut)
        session.add(thumbnail)
        session.add(project)
        session.commit()


def _prepare_publish_job(
    client: TestClient,
    session_factory: sessionmaker[Session],
    *,
    platform: str = "youtube_shorts",
) -> str:
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(client, brand_profile_id)
    script = _create_approved_script_for_tests(client, project_id)
    _move_project_to_final_review_for_tests(
        session_factory,
        project_id=project_id,
        script_id=str(script["id"]),
    )
    client.post(f"/api/projects/{project_id}/final-video/approve", json={})
    prepare_response = client.post(
        f"/api/projects/{project_id}/publish-jobs/prepare",
        json={
            "platform": platform,
            "title": "Manual handoff title",
            "description": "Metadata prepared for a manual upload.",
            "hashtags": ["#CreatorOS", "Publish"],
        },
    )
    assert prepare_response.status_code == 201
    return prepare_response.json()["id"]


def test_publish_handoff_queue_requires_approval_and_blocks_duplicates() -> None:
    session_factory = _create_test_session()
    client = _make_test_client(session_factory)
    publish_job_id = _prepare_publish_job(client, session_factory)

    blocked_queue_response = client.post(f"/api/publish-jobs/{publish_job_id}/queue")
    assert blocked_queue_response.status_code == 409
    assert "approved or scheduled" in _error_message(blocked_queue_response)

    approve_response = client.post(f"/api/publish-jobs/{publish_job_id}/approve", json={})
    assert approve_response.status_code == 200

    queue_response = client.post(f"/api/publish-jobs/{publish_job_id}/queue")
    assert queue_response.status_code == 200
    job = queue_response.json()
    assert job["job_type"] == "publish_content"
    assert job["state"] == "queued"
    assert job["payload_json"]["publish_job_id"] == publish_job_id
    assert job["payload_json"]["adapter_name"] == "youtube_studio_manual_handoff"
    assert job["payload_json"]["platform"] == "youtube_shorts"

    duplicate_queue_response = client.post(f"/api/publish-jobs/{publish_job_id}/queue")
    assert duplicate_queue_response.status_code == 409
    assert "active publish handoff" in _error_message(duplicate_queue_response)

    app.dependency_overrides.clear()


def test_publish_adapter_resolution_prefers_platform_specific_handoffs() -> None:
    assert resolve_publish_adapter_name("youtube_shorts") == "youtube_studio_manual_handoff"
    assert resolve_publish_adapter_name("tiktok") == "tiktok_manual_handoff"
    assert resolve_publish_adapter_name("facebook_reels") == "facebook_manual_handoff"
    assert resolve_publish_adapter_name("custom_portal") == "manual_publish_handoff"


def test_publish_handoff_queue_falls_back_to_generic_adapter_for_unknown_platform() -> None:
    session_factory = _create_test_session()
    client = _make_test_client(session_factory)
    publish_job_id = _prepare_publish_job(
        client,
        session_factory,
        platform="custom_portal",
    )
    client.post(f"/api/publish-jobs/{publish_job_id}/approve", json={})

    queue_response = client.post(f"/api/publish-jobs/{publish_job_id}/queue")
    assert queue_response.status_code == 200
    assert queue_response.json()["payload_json"]["adapter_name"] == "manual_publish_handoff"

    app.dependency_overrides.clear()


def test_publisher_worker_generates_handoff_and_waits_for_manual_completion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    session_factory = _create_test_session()
    client = _make_test_client(session_factory)
    publish_job_id = _prepare_publish_job(client, session_factory)
    client.post(f"/api/publish-jobs/{publish_job_id}/approve", json={})

    queue_response = client.post(f"/api/publish-jobs/{publish_job_id}/queue")
    assert queue_response.status_code == 200
    job_id = queue_response.json()["id"]

    processed_jobs = run_pending_jobs(
        settings=PublisherWorkerSettings(storage_root=tmp_path / "storage"),
        session_factory=session_factory,
    )
    assert processed_jobs == 1

    detail_response = client.get(f"/api/jobs/{job_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["job"]["state"] == "waiting_external"
    assert detail["job"]["progress_percent"] == 90
    assert "Manual publish handoff is ready" in detail["job"]["error_message"]
    assert detail["job"]["payload_json"]["adapter_name"] == "youtube_studio_manual_handoff"
    assert any(log["event_type"] == "manual_publish_handoff_ready" for log in detail["job_logs"])

    handoff_path = tmp_path / detail["job"]["payload_json"]["handoff_path"]
    handoff_payload = handoff_path.read_text(encoding="utf-8")
    assert "Manual handoff title" in handoff_payload
    assert "YouTube Studio Manual Handoff" in handoff_payload
    assert (
        "This handoff is platform-aware, but it still requires a manual upload"
        in handoff_payload
    )

    published_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/mark-published",
        json={
            "external_post_id": "manual-post-123",
            "manual_publish_notes": "Uploaded after reviewing the handoff package.",
        },
    )
    assert published_response.status_code == 200
    assert published_response.json()["status"] == "published"

    completed_detail_response = client.get(f"/api/jobs/{job_id}")
    completed_detail = completed_detail_response.json()
    assert completed_detail["job"]["state"] == "completed"
    assert completed_detail["job"]["progress_percent"] == 100
    assert any(
        log["event_type"] == "publish_handoff_completed" for log in completed_detail["job_logs"]
    )

    app.dependency_overrides.clear()
