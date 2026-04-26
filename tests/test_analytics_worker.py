from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import apps.api.models  # noqa: F401
from apps.api.db.base import Base
from apps.api.db.session import get_db
from apps.api.main import app
from apps.api.models.analytics_snapshot import AnalyticsSnapshot
from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.models.publish_job import PublishJob
from apps.api.schemas.enums import AssetStatus, AssetType, ProjectStatus, ProviderName
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from workers.analytics.config import AnalyticsWorkerSettings
from workers.analytics.runtime import run_pending_jobs


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
            "title": "Analytics queue",
            "target_platform": "youtube_shorts",
            "objective": "Queue analytics sync",
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
        project.status = ProjectStatus.FINAL_PENDING_APPROVAL
        session.add(rough_cut)
        session.add(project)
        session.commit()


def _prepare_publish_job(
    client: TestClient,
    session_factory: sessionmaker[Session],
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
            "platform": "youtube_shorts",
            "title": "Analytics source post",
            "description": "Metadata prepared for analytics sync.",
            "hashtags": ["#CreatorOS", "Analytics"],
        },
    )
    assert prepare_response.status_code == 201
    return prepare_response.json()["id"]


def _mark_publish_job_published(
    client: TestClient,
    publish_job_id: str,
) -> None:
    approve_response = client.post(f"/api/publish-jobs/{publish_job_id}/approve", json={})
    assert approve_response.status_code == 200
    published_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/mark-published",
        json={"external_post_id": "analytics-post-123"},
    )
    assert published_response.status_code == 200
    assert published_response.json()["status"] == "published"


def test_analytics_queue_requires_published_job_and_blocks_duplicates() -> None:
    session_factory = _create_test_session()
    client = _make_test_client(session_factory)
    publish_job_id = _prepare_publish_job(client, session_factory)

    blocked_queue_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/analytics/queue",
        json={"views": 1000, "likes": 90},
    )
    assert blocked_queue_response.status_code == 409
    assert "marked published" in _error_message(blocked_queue_response)

    _mark_publish_job_published(client, publish_job_id)

    queue_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/analytics/queue",
        json={"views": 1000, "likes": 90, "comments": 12, "shares": 8},
    )
    assert queue_response.status_code == 201
    job = queue_response.json()
    assert job["job_type"] == "sync_analytics"
    assert job["state"] == "queued"
    assert job["payload_json"]["publish_job_id"] == publish_job_id
    assert job["payload_json"]["metrics"]["views"] == 1000

    duplicate_queue_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/analytics/queue",
        json={"views": 1200, "likes": 100},
    )
    assert duplicate_queue_response.status_code == 409
    assert "active analytics sync" in _error_message(duplicate_queue_response)

    app.dependency_overrides.clear()


def test_analytics_worker_persists_snapshot_insights_and_completes_job() -> None:
    session_factory = _create_test_session()
    client = _make_test_client(session_factory)
    publish_job_id = _prepare_publish_job(client, session_factory)
    _mark_publish_job_published(client, publish_job_id)

    queue_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/analytics/queue",
        json={
            "views": 2500,
            "likes": 220,
            "comments": 34,
            "shares": 18,
            "saves": 12,
            "avg_view_duration": 21.5,
        },
    )
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    processed_jobs = run_pending_jobs(
        settings=AnalyticsWorkerSettings(),
        session_factory=session_factory,
    )
    assert processed_jobs == 1

    detail_response = client.get(f"/api/jobs/{job_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["job"]["state"] == "completed"
    assert detail["job"]["progress_percent"] == 100
    assert detail["job"]["payload_json"]["analytics_snapshot_id"]
    assert any(log["event_type"] == "analytics_snapshot_synced" for log in detail["job_logs"])

    analytics_response = client.get(
        f"/api/projects/{detail['job']['project_id']}/analytics",
    )
    assert analytics_response.status_code == 200
    analytics = analytics_response.json()
    assert len(analytics["snapshots"]) == 1
    assert analytics["snapshots"][0]["views"] == 2500
    assert len(analytics["insights"]) >= 1

    with session_factory() as session:
        publish_job = session.get(PublishJob, UUID(publish_job_id))
        assert publish_job is not None
        snapshot = session.get(
            AnalyticsSnapshot,
            UUID(str(detail["job"]["payload_json"]["analytics_snapshot_id"])),
        )
        assert snapshot is not None
        assert snapshot.publish_job_id == publish_job.id

    app.dependency_overrides.clear()


def test_analytics_worker_schedules_automatic_retry_backoff_for_transient_sync_failures() -> None:
    session_factory = _create_test_session()
    client = _make_test_client(session_factory)
    publish_job_id = _prepare_publish_job(client, session_factory)
    _mark_publish_job_published(client, publish_job_id)

    queue_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/analytics/queue",
        json={"views": 1400, "likes": 95, "comments": 10, "shares": 6},
    )
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    original_sync = run_pending_jobs.__globals__["sync_publish_job_analytics"]
    sync_calls = {"count": 0}

    def flaky_sync(*args, **kwargs):
        sync_calls["count"] += 1
        if sync_calls["count"] == 1:
            raise TimeoutError("Analytics provider timed out while syncing metrics.")
        return original_sync(*args, **kwargs)

    run_pending_jobs.__globals__["sync_publish_job_analytics"] = flaky_sync
    try:
        processed_jobs = run_pending_jobs(
            settings=AnalyticsWorkerSettings(),
            session_factory=session_factory,
        )
        assert processed_jobs == 1

        detail_response = client.get(f"/api/jobs/{job_id}")
        detail = detail_response.json()
        assert detail["job"]["state"] == "queued"
        assert detail["job"]["available_at"] is not None
        assert detail["job"]["attempts"] == 1
        assert any(log["event_type"] == "job_auto_retry_scheduled" for log in detail["job_logs"])
        scheduled_at = datetime.fromisoformat(detail["job"]["available_at"].replace("Z", "+00:00"))
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=UTC)
        assert scheduled_at > datetime.now(UTC)

        assert (
            run_pending_jobs(
                settings=AnalyticsWorkerSettings(),
                session_factory=session_factory,
            )
            == 0
        )

        with session_factory() as session:
            queued_job = session.get(BackgroundJob, UUID(job_id))
            assert queued_job is not None
            queued_job.available_at = datetime.now(UTC) - timedelta(seconds=1)
            session.add(queued_job)
            session.commit()

        processed_retry_jobs = run_pending_jobs(
            settings=AnalyticsWorkerSettings(),
            session_factory=session_factory,
        )
        assert processed_retry_jobs == 1

        completed_detail_response = client.get(f"/api/jobs/{job_id}")
        completed_detail = completed_detail_response.json()
        assert completed_detail["job"]["state"] == "completed"
        assert completed_detail["job"]["attempts"] == 2
        assert completed_detail["job"]["available_at"] is None
    finally:
        run_pending_jobs.__globals__["sync_publish_job_analytics"] = original_sync

    app.dependency_overrides.clear()
