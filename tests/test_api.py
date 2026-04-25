from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import apps.api.models  # noqa: F401
from apps.api.core.redaction import redact_sensitive_value
from apps.api.db.base import Base
from apps.api.db.session import get_db
from apps.api.main import app
from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.models.user import User
from apps.api.schemas.enums import (
    AssetStatus,
    AssetType,
    BackgroundJobState,
    BackgroundJobType,
    ProjectStatus,
    ProviderName,
)
from apps.api.services.background_jobs import (
    create_job_log,
    get_background_job,
    mark_job_failed,
    mark_job_manual_intervention_required,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


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


def _make_test_client() -> TestClient:
    test_session_factory = _create_test_session()

    return _make_test_client_for_session(test_session_factory)


def _make_test_client_with_session() -> tuple[TestClient, sessionmaker[Session]]:
    test_session_factory = _create_test_session()
    return _make_test_client_for_session(test_session_factory), test_session_factory


def _make_test_client_for_session(test_session_factory: sessionmaker[Session]) -> TestClient:
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


def _create_draft_script_for_tests(client: TestClient, project_id: str) -> dict[str, object]:
    ideas_response = client.post(f"/api/projects/{project_id}/ideas/generate")
    approved_idea_id = ideas_response.json()[0]["id"]
    client.post(f"/api/ideas/{approved_idea_id}/approve", json={})

    script_response = client.post(f"/api/projects/{project_id}/scripts/generate", json={})
    return script_response.json()


def _create_approved_script_for_tests(client: TestClient, project_id: str) -> dict[str, object]:
    script = _create_draft_script_for_tests(client, project_id)
    client.post(f"/api/scripts/{script['id']}/approve", json={})
    return script


def _move_project_to_final_review_for_tests(
    session_factory: sessionmaker[Session],
    *,
    project_id: str,
    script_id: str,
) -> str:
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
            checksum="test-checksum",
        )
        project.status = ProjectStatus.FINAL_PENDING_APPROVAL
        session.add(rough_cut)
        session.add(project)
        session.commit()
        return str(rough_cut.id)


def _move_project_to_final_review_with_export_for_tests(
    session_factory: sessionmaker[Session],
    *,
    project_id: str,
    script_id: str,
) -> tuple[str, str]:
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
            checksum="test-rough-cut-checksum",
        )
        final_video = Asset(
            user_id=project.user_id,
            project_id=project.id,
            script_id=script.id,
            scene_id=None,
            generation_attempt_id=None,
            asset_type=AssetType.FINAL_VIDEO,
            status=AssetStatus.READY,
            provider_name=ProviderName.LOCAL_MEDIA,
            file_path=f"storage/projects/{project.id}/final-exports/test-final.mp4",
            mime_type="video/mp4",
            duration_seconds=script.estimated_duration_seconds,
            width=1080,
            height=1920,
            checksum="test-final-video-checksum",
        )
        project.status = ProjectStatus.FINAL_PENDING_APPROVAL
        session.add(rough_cut)
        session.add(final_video)
        session.add(project)
        session.commit()
        return str(rough_cut.id), str(final_video.id)


def _create_ready_thumbnail_for_tests(
    session_factory: sessionmaker[Session],
    *,
    project_id: str,
    script_id: str,
) -> str:
    with session_factory() as session:
        project = session.get(Project, UUID(project_id))
        script = session.get(ProjectScript, UUID(script_id))
        assert project is not None
        assert script is not None

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
            checksum=f"test-thumbnail-{project.id}",
        )
        session.add(thumbnail)
        session.commit()
        return str(thumbnail.id)


def test_live_health() -> None:
    client = TestClient(app)
    response = client.get("/api/health/live", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "api"


def test_ready_health_redacts_connection_credentials() -> None:
    client = TestClient(app)
    response = client.get("/api/health/ready")

    assert response.status_code == 200
    dependencies = response.json()["dependencies"]
    assert "creatoros:creatoros" not in dependencies["database"]
    assert "[redacted]" in dependencies["database"]


def test_redaction_helper_handles_urls_and_secret_assignments() -> None:
    value = (
        "postgresql://user:password@example.com/db?token=abc cookie=session-value api_key=raw-key"
    )

    redacted = redact_sensitive_value(value)

    assert "user:password" not in redacted
    assert "abc" not in redacted
    assert "session-value" not in redacted
    assert "raw-key" not in redacted
    assert "[redacted]" in redacted


def test_session_route_returns_single_user_identity() -> None:
    client, session_factory = _make_test_client_with_session()

    first_response = client.get("/api/session")
    second_response = client.get("/api/session")

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_payload = first_response.json()
    second_payload = second_response.json()

    assert first_payload["auth_mode"] == "single_user_local"
    assert first_payload["requires_approval_checkpoints"] is True
    assert first_payload["user"]["email"] == "creatoros-local@example.com"
    assert first_payload["user"]["name"] == "CreatorOS Local User"
    assert first_payload["user"]["id"] == second_payload["user"]["id"]

    with session_factory() as session:
      users = session.scalars(select(User)).all()

    assert len(users) == 1


def test_http_errors_use_global_error_model() -> None:
    client = _make_test_client()
    request_id = "error-model-request"

    response = client.get(f"/api/projects/{uuid4()}", headers={"X-Request-ID": request_id})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == request_id
    assert response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Project not found",
            "details": {},
            "request_id": request_id,
        }
    }

    app.dependency_overrides.clear()


def test_validation_errors_use_global_error_model() -> None:
    client = _make_test_client()
    request_id = "validation-error-request"

    response = client.post("/api/projects", json={}, headers={"X-Request-ID": request_id})

    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == request_id
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Request validation failed."
    assert body["error"]["request_id"] == request_id
    assert body["error"]["details"]["validation_errors"]

    app.dependency_overrides.clear()


def test_brand_profiles_crud_flow() -> None:
    client = _make_test_client()

    create_response = client.post(
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

    assert create_response.status_code == 201
    created_brand_profile = create_response.json()
    assert created_brand_profile["channel_name"] == "Creator Lab"

    list_response = client.get("/api/brand-profiles")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = client.patch(
        f"/api/brand-profiles/{created_brand_profile['id']}",
        json={"tone": "Direct and optimistic"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["tone"] == "Direct and optimistic"

    get_response = client.get(f"/api/brand-profiles/{created_brand_profile['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created_brand_profile["id"]

    app.dependency_overrides.clear()


def test_brand_profile_readiness_and_prompt_context() -> None:
    client = _make_test_client()

    create_response = client.post(
        "/api/brand-profiles",
        json={
            "channel_name": " Creator Lab ",
            "niche": "AI productivity",
            "target_audience": "Solo founders building content systems",
            "tone": "Direct and optimistic",
            "hook_style": "Question first",
            "cta_style": "Invite thoughtful comments",
            "visual_style": "Fast screen recordings with warm overlays",
            "posting_preferences_json": {
                "platforms": [" youtube_shorts ", "tiktok"],
                "default_platform": "youtube_shorts",
                "output_defaults": {
                    "aspect_ratio": "9:16",
                    "target_duration_seconds": 35,
                },
            },
        },
    )

    assert create_response.status_code == 201
    brand_profile = create_response.json()
    assert brand_profile["channel_name"] == "Creator Lab"
    assert brand_profile["posting_preferences_json"]["platforms"] == [
        "youtube_shorts",
        "tiktok",
    ]

    readiness_response = client.get(f"/api/brand-profiles/{brand_profile['id']}/readiness")
    assert readiness_response.status_code == 200
    readiness = readiness_response.json()
    assert readiness["is_ready"] is True
    assert readiness["warnings"] == []

    prompt_context_response = client.get(
        f"/api/brand-profiles/{brand_profile['id']}/prompt-context"
    )
    assert prompt_context_response.status_code == 200
    prompt_context = prompt_context_response.json()
    assert prompt_context["readiness"]["is_ready"] is True
    assert prompt_context["context_json"]["identity"]["channel_name"] == "Creator Lab"
    assert prompt_context["context_json"]["output_defaults"]["aspect_ratio"] == "9:16"
    assert "# Brand Context: Creator Lab" in prompt_context["context_markdown"]

    app.dependency_overrides.clear()


def test_brand_profile_preferences_validation_errors_are_clear() -> None:
    client = _make_test_client()

    create_response = client.post(
        "/api/brand-profiles",
        json={
            "channel_name": "Creator Lab",
            "niche": "AI productivity",
            "target_audience": "Solo founders",
            "tone": "Direct",
            "hook_style": "Question first",
            "cta_style": "Ask for comments",
            "visual_style": "Screen recordings",
            "posting_preferences_json": {"platforms": "youtube_shorts"},
        },
    )

    assert create_response.status_code == 422
    assert "platforms must be a list of strings" in str(create_response.json())

    app.dependency_overrides.clear()


def test_projects_crud_flow() -> None:
    client = _make_test_client()
    brand_profile_response = client.post(
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
    brand_profile_id = brand_profile_response.json()["id"]

    create_response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": "3 AI automations I use daily",
            "target_platform": "youtube_shorts",
            "objective": "Create a short-form educational video",
            "notes": "Keep this under 45 seconds",
        },
    )

    assert create_response.status_code == 201
    created_project = create_response.json()
    assert created_project["status"] == "draft"

    list_response = client.get("/api/projects")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = client.patch(
        f"/api/projects/{created_project['id']}",
        json={"notes": "Target TikTok and Shorts equally"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["notes"] == "Target TikTok and Shorts equally"

    get_response = client.get(f"/api/projects/{created_project['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created_project["id"]

    app.dependency_overrides.clear()


def test_project_transitions_allow_valid_next_step() -> None:
    client = _make_test_client()
    brand_profile_response = client.post(
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
    brand_profile_id = brand_profile_response.json()["id"]

    create_response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": "Workflow test project",
            "target_platform": "youtube_shorts",
            "objective": "Validate transitions",
            "notes": None,
        },
    )
    project_id = create_response.json()["id"]

    transition_response = client.post(
        f"/api/projects/{project_id}/transition",
        json={"target_status": "idea_pending_approval"},
    )

    assert transition_response.status_code == 200
    assert transition_response.json()["status"] == "idea_pending_approval"

    app.dependency_overrides.clear()


def test_project_transitions_block_invalid_jump() -> None:
    client = _make_test_client()
    brand_profile_response = client.post(
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
    brand_profile_id = brand_profile_response.json()["id"]

    create_response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": "Invalid transition project",
            "target_platform": "youtube_shorts",
            "objective": "Validate blocked jumps",
            "notes": None,
        },
    )
    project_id = create_response.json()["id"]

    transition_response = client.post(
        f"/api/projects/{project_id}/transition",
        json={"target_status": "ready_to_publish"},
    )

    assert transition_response.status_code == 409
    assert "cannot transition" in _error_message(transition_response)

    app.dependency_overrides.clear()


def test_project_archive_manual_override_activity_and_export() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Manual recovery project",
        objective="Validate archive, override, activity, and export",
        notes=None,
    )

    override_response = client.post(
        f"/api/projects/{project_id}/manual-override",
        json={
            "target_status": "failed",
            "reason": "Browser provider changed and needs operator review.",
        },
    )
    assert override_response.status_code == 200
    assert override_response.json()["status"] == "failed"

    activity_response = client.get(f"/api/projects/{project_id}/activity")
    assert activity_response.status_code == 200
    activity = activity_response.json()
    assert any(entry["activity_type"] == "manual_status_override" for entry in activity)
    assert any(entry["activity_type"] == "project_created" for entry in activity)

    export_response = client.get(f"/api/projects/{project_id}/export")
    assert export_response.status_code == 200
    export_bundle = export_response.json()
    assert export_bundle["project"]["id"] == project_id
    assert export_bundle["brand_profile"]["id"] == brand_profile_id
    assert any(
        event["event_type"] == "manual_status_override" for event in export_bundle["project_events"]
    )

    archive_response = client.post(
        f"/api/projects/{project_id}/archive",
        json={"reason": "Demo recovery check complete."},
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    blocked_override_response = client.post(
        f"/api/projects/{project_id}/manual-override",
        json={"target_status": "draft", "reason": "Should stay archived."},
    )
    assert blocked_override_response.status_code == 409
    assert "Archived projects" in _error_message(blocked_override_response)

    app.dependency_overrides.clear()


def test_generate_project_ideas_updates_project_status() -> None:
    client = _make_test_client()
    brand_profile_response = client.post(
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
    brand_profile_id = brand_profile_response.json()["id"]

    create_response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": "Launch a creator workflow",
            "target_platform": "youtube_shorts",
            "objective": "Show a repeatable short-form content system",
            "notes": "Keep it tactical",
        },
    )
    project_id = create_response.json()["id"]

    generate_response = client.post(f"/api/projects/{project_id}/ideas/generate")

    assert generate_response.status_code == 201
    ideas = generate_response.json()
    assert len(ideas) == 3
    assert all(idea["status"] == "proposed" for idea in ideas)
    assert all(idea["topic"] for idea in ideas)

    get_response = client.get(f"/api/projects/{project_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "idea_pending_approval"

    app.dependency_overrides.clear()


def test_idea_research_generation_creates_snapshot_and_completed_job() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Research-backed creator workflow",
        objective="Seed stronger short-form angles",
        notes="Favor proof over generic advice",
    )

    research_response = client.post(
        f"/api/projects/{project_id}/research/generate",
        json={
            "focus_topic": "AI creator workflows",
            "source_feedback_notes": "Bias the next batch toward tactical proof-led examples.",
        },
    )

    assert research_response.status_code == 201
    snapshot = research_response.json()
    assert snapshot["focus_topic"] == "AI creator workflows"
    assert "visible proof" in snapshot["summary"].lower()
    assert any("proof-led" in item.lower() for item in snapshot["competitor_angles_json"])
    assert len(snapshot["trend_observations_json"]) == 3
    assert len(snapshot["recommended_topics_json"]) >= 3

    list_response = client.get(f"/api/projects/{project_id}/research")
    assert list_response.status_code == 200
    listed_snapshots = list_response.json()
    assert len(listed_snapshots) == 1
    assert listed_snapshots[0]["id"] == snapshot["id"]

    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs_response.status_code == 200
    research_job = next(
        job for job in jobs_response.json() if job["job_type"] == "generate_idea_research"
    )
    assert research_job["state"] == "completed"
    assert research_job["payload_json"]["research_snapshot_id"] == snapshot["id"]

    detail_response = client.get(f"/api/jobs/{research_job['id']}")
    assert detail_response.status_code == 200
    event_types = {log["event_type"] for log in detail_response.json()["job_logs"]}
    assert {"job_queued", "job_started", "idea_research_generated", "job_completed"}.issubset(
        event_types
    )

    app.dependency_overrides.clear()


def test_idea_approval_and_script_generation_flow() -> None:
    client = _make_test_client()
    brand_profile_response = client.post(
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
    brand_profile_id = brand_profile_response.json()["id"]

    create_response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": "Build a daily content loop",
            "target_platform": "youtube_shorts",
            "objective": "Turn one workflow into multiple pieces of content",
            "notes": "Use concrete examples",
        },
    )
    project_id = create_response.json()["id"]

    generate_ideas_response = client.post(f"/api/projects/{project_id}/ideas/generate")
    ideas = generate_ideas_response.json()

    approve_response = client.post(f"/api/ideas/{ideas[0]['id']}/approve", json={})
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    generate_script_response = client.post(
        f"/api/projects/{project_id}/scripts/generate",
        json={},
    )
    assert generate_script_response.status_code == 201
    script = generate_script_response.json()
    assert script["version_number"] == 1
    assert script["status"] == "draft"
    assert len(script["scenes"]) == 4
    assert script["estimated_duration_seconds"] > 0

    current_script_response = client.get(f"/api/projects/{project_id}/scripts/current")
    assert current_script_response.status_code == 200
    assert current_script_response.json()["id"] == script["id"]

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "script_pending_approval"

    approvals_response = client.get(f"/api/projects/{project_id}/approvals")
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()
    assert len(approvals) == 1
    assert approvals[0]["stage"] == "idea"
    assert approvals[0]["decision"] == "approved"

    app.dependency_overrides.clear()


def test_idea_generation_creates_completed_project_level_job() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Track idea generation jobs",
        objective="Make planning work observable",
        notes=None,
    )

    generate_ideas_response = client.post(f"/api/projects/{project_id}/ideas/generate")

    assert generate_ideas_response.status_code == 201
    ideas = generate_ideas_response.json()
    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs_response.status_code == 200
    idea_jobs = [job for job in jobs_response.json() if job["job_type"] == "generate_ideas"]
    assert len(idea_jobs) == 1
    idea_job = idea_jobs[0]
    assert idea_job["script_id"] is None
    assert idea_job["state"] == "completed"
    assert idea_job["progress_percent"] == 100
    assert idea_job["payload_json"]["idea_count"] == len(ideas)
    assert idea_job["payload_json"]["idea_ids"] == [idea["id"] for idea in ideas]

    detail_response = client.get(f"/api/jobs/{idea_job['id']}")
    assert detail_response.status_code == 200
    event_types = {log["event_type"] for log in detail_response.json()["job_logs"]}
    assert {"job_queued", "job_started", "content_ideas_generated", "job_completed"}.issubset(
        event_types
    )

    app.dependency_overrides.clear()


def test_idea_generation_uses_latest_research_snapshot_and_persists_topics() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Use saved research in idea generation",
        objective="Generate tighter short-form hooks",
        notes=None,
    )
    research_response = client.post(
        f"/api/projects/{project_id}/research/generate",
        json={
            "focus_topic": "Short-form automation",
            "source_feedback_notes": "Make the ideas feel specific to solo creators.",
        },
    )
    assert research_response.status_code == 201
    research_snapshot = research_response.json()

    generate_ideas_response = client.post(f"/api/projects/{project_id}/ideas/generate")

    assert generate_ideas_response.status_code == 201
    ideas = generate_ideas_response.json()
    assert len(ideas) == 3
    assert all(idea["topic"] in research_snapshot["recommended_topics_json"] for idea in ideas)
    assert any("research" in idea["rationale"].lower() for idea in ideas)

    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs_response.status_code == 200
    idea_job = next(job for job in jobs_response.json() if job["job_type"] == "generate_ideas")
    assert idea_job["payload_json"]["research_snapshot_id"] == research_snapshot["id"]
    assert (
        idea_job["payload_json"]["idea_research_context"]["research_snapshot_id"]
        == research_snapshot["id"]
    )
    assert (
        idea_job["payload_json"]["idea_research_context"]["recommended_topics"]
        == research_snapshot["recommended_topics_json"]
    )

    app.dependency_overrides.clear()


def test_idea_regeneration_persists_source_feedback_notes() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Regenerate ideas with notes",
        objective="Make idea revision instructions traceable",
        notes=None,
    )
    feedback_notes = "Make the next batch more tactical and contrarian."
    client.post(f"/api/projects/{project_id}/ideas/generate", json={})

    regenerate_response = client.post(
        f"/api/projects/{project_id}/ideas/generate",
        json={"source_feedback_notes": feedback_notes},
    )

    assert regenerate_response.status_code == 201
    regenerated_ideas = regenerate_response.json()
    assert all(idea["source_feedback_notes"] == feedback_notes for idea in regenerated_ideas)
    assert all("revision note" in idea["rationale"].lower() for idea in regenerated_ideas)

    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs_response.status_code == 200
    idea_jobs = [job for job in jobs_response.json() if job["job_type"] == "generate_ideas"]
    assert len(idea_jobs) == 2
    latest_revision_job = next(
        job
        for job in idea_jobs
        if job["payload_json"].get("source_feedback_notes") == feedback_notes
    )
    assert latest_revision_job["payload_json"]["idea_ids"] == [
        idea["id"] for idea in regenerated_ideas
    ]

    app.dependency_overrides.clear()


def test_project_export_includes_idea_research_snapshots() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Export research history",
        objective="Keep planning exports complete",
        notes=None,
    )
    research_response = client.post(
        f"/api/projects/{project_id}/research/generate",
        json={"focus_topic": "Retention-focused creator workflows"},
    )
    assert research_response.status_code == 201
    snapshot = research_response.json()

    export_response = client.get(f"/api/projects/{project_id}/export")

    assert export_response.status_code == 200
    export_bundle = export_response.json()
    assert len(export_bundle["idea_research_snapshots"]) == 1
    assert export_bundle["idea_research_snapshots"][0]["id"] == snapshot["id"]
    assert (
        export_bundle["idea_research_snapshots"][0]["focus_topic"]
        == "Retention-focused creator workflows"
    )

    app.dependency_overrides.clear()


def test_script_generation_creates_completed_job_linked_to_script() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Track script generation jobs",
        objective="Make script planning observable",
        notes=None,
    )
    ideas_response = client.post(f"/api/projects/{project_id}/ideas/generate")
    approved_idea_id = ideas_response.json()[0]["id"]
    client.post(f"/api/ideas/{approved_idea_id}/approve", json={})

    script_response = client.post(
        f"/api/projects/{project_id}/scripts/generate",
        json={"source_feedback_notes": "Use tighter proof points."},
    )

    assert script_response.status_code == 201
    script = script_response.json()
    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs_response.status_code == 200
    script_jobs = [job for job in jobs_response.json() if job["job_type"] == "generate_script"]
    assert len(script_jobs) == 1
    script_job = script_jobs[0]
    assert script_job["script_id"] == script["id"]
    assert script_job["state"] == "completed"
    assert script_job["payload_json"]["script_id"] == script["id"]
    assert script_job["payload_json"]["script_version"] == 1
    assert script_job["payload_json"]["scene_count"] == len(script["scenes"])
    assert script_job["payload_json"]["source_feedback_notes"] == "Use tighter proof points."

    detail_response = client.get(f"/api/jobs/{script_job['id']}")
    assert detail_response.status_code == 200
    event_types = {log["event_type"] for log in detail_response.json()["job_logs"]}
    assert {"job_queued", "job_started", "script_generated", "job_completed"}.issubset(event_types)

    app.dependency_overrides.clear()


def test_project_transition_to_script_pending_requires_generated_script() -> None:
    client = _make_test_client()
    brand_profile_response = client.post(
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
    brand_profile_id = brand_profile_response.json()["id"]

    create_response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": "Guard script transitions",
            "target_platform": "youtube_shorts",
            "objective": "Validate workflow prerequisites",
            "notes": None,
        },
    )
    project_id = create_response.json()["id"]

    move_to_idea_response = client.post(
        f"/api/projects/{project_id}/transition",
        json={"target_status": "idea_pending_approval"},
    )
    assert move_to_idea_response.status_code == 200

    move_to_script_response = client.post(
        f"/api/projects/{project_id}/transition",
        json={"target_status": "script_pending_approval"},
    )
    assert move_to_script_response.status_code == 409
    assert "generated script" in _error_message(move_to_script_response)

    app.dependency_overrides.clear()


def test_rejecting_idea_records_approval_history() -> None:
    client = _make_test_client()
    brand_profile_response = client.post(
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
    brand_profile_id = brand_profile_response.json()["id"]

    create_response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": "Reject weak ideas",
            "target_platform": "youtube_shorts",
            "objective": "Validate explicit rejection history",
            "notes": None,
        },
    )
    project_id = create_response.json()["id"]

    generate_ideas_response = client.post(f"/api/projects/{project_id}/ideas/generate")
    idea_id = generate_ideas_response.json()[0]["id"]

    reject_response = client.post(
        f"/api/ideas/{idea_id}/reject",
        json={"feedback_notes": "This angle is too broad."},
    )

    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"
    assert reject_response.json()["feedback_notes"] == "This angle is too broad."

    approvals_response = client.get(f"/api/projects/{project_id}/approvals")
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()
    assert len(approvals) == 1
    assert approvals[0]["stage"] == "idea"
    assert approvals[0]["decision"] == "rejected"
    assert approvals[0]["feedback_notes"] == "This angle is too broad."

    app.dependency_overrides.clear()


def test_script_approval_unblocks_asset_generation() -> None:
    client = _make_test_client()
    brand_profile_response = client.post(
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
    brand_profile_id = brand_profile_response.json()["id"]

    create_response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": "Approve script before assets",
            "target_platform": "youtube_shorts",
            "objective": "Ensure asset generation stays gated",
            "notes": None,
        },
    )
    project_id = create_response.json()["id"]

    ideas_response = client.post(f"/api/projects/{project_id}/ideas/generate")
    approved_idea_id = ideas_response.json()[0]["id"]
    client.post(f"/api/ideas/{approved_idea_id}/approve", json={})

    script_response = client.post(f"/api/projects/{project_id}/scripts/generate", json={})
    script_id = script_response.json()["id"]

    blocked_transition_response = client.post(
        f"/api/projects/{project_id}/transition",
        json={"target_status": "asset_generation"},
    )
    assert blocked_transition_response.status_code == 409
    assert "current script is approved" in _error_message(blocked_transition_response)

    approve_script_response = client.post(
        f"/api/scripts/{script_id}/approve",
        json={"feedback_notes": "Good enough to move into assets."},
    )
    assert approve_script_response.status_code == 200
    assert approve_script_response.json()["status"] == "approved"

    approvals_response = client.get(f"/api/projects/{project_id}/approvals")
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()
    assert len(approvals) == 2
    assert any(
        approval["stage"] == "script" and approval["decision"] == "approved"
        for approval in approvals
    )

    allowed_transition_response = client.post(
        f"/api/projects/{project_id}/transition",
        json={"target_status": "asset_generation"},
    )
    assert allowed_transition_response.status_code == 200
    assert allowed_transition_response.json()["status"] == "asset_generation"

    app.dependency_overrides.clear()


def test_scene_updates_persist_and_prompt_pack_reflects_changes() -> None:
    client = _make_test_client()
    brand_profile_response = client.post(
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
    brand_profile_id = brand_profile_response.json()["id"]

    create_response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": "Edit scenes before approval",
            "target_platform": "youtube_shorts",
            "objective": "Prepare a worker-ready prompt pack",
            "notes": None,
        },
    )
    project_id = create_response.json()["id"]

    ideas_response = client.post(f"/api/projects/{project_id}/ideas/generate")
    approved_idea_id = ideas_response.json()[0]["id"]
    client.post(f"/api/ideas/{approved_idea_id}/approve", json={})

    script_response = client.post(f"/api/projects/{project_id}/scripts/generate", json={})
    script = script_response.json()
    script_id = script["id"]
    first_scene_id = script["scenes"][0]["id"]
    original_duration = sum(scene["estimated_duration_seconds"] for scene in script["scenes"])
    expected_duration = original_duration - script["scenes"][0]["estimated_duration_seconds"] + 9

    update_scene_response = client.patch(
        f"/api/scenes/{first_scene_id}",
        json={
            "overlay_text": "Updated overlay guidance",
            "estimated_duration_seconds": 9,
            "notes": "Use a cleaner visual example.",
        },
    )
    assert update_scene_response.status_code == 200
    updated_scene = update_scene_response.json()
    assert updated_scene["overlay_text"] == "Updated overlay guidance"
    assert updated_scene["estimated_duration_seconds"] == 9
    assert updated_scene["notes"] == "Use a cleaner visual example."

    current_script_response = client.get(f"/api/projects/{project_id}/scripts/current")
    assert current_script_response.status_code == 200
    assert current_script_response.json()["estimated_duration_seconds"] == expected_duration

    prompt_pack_response = client.get(f"/api/scripts/{script_id}/prompt-pack")
    assert prompt_pack_response.status_code == 200
    prompt_pack = prompt_pack_response.json()
    assert prompt_pack["source_idea_title"]
    assert prompt_pack["brand_context"]["identity"]["channel_name"] == "Creator Lab"
    assert prompt_pack["brand_context"]["platforms"] == ["youtube_shorts"]
    assert prompt_pack["scenes"][0]["overlay_text"] == "Updated overlay guidance"
    assert prompt_pack["scenes"][0]["estimated_duration_seconds"] == 9
    assert "Creator Lab" in prompt_pack["scenes"][0]["image_generation_prompt"]

    app.dependency_overrides.clear()


def test_scene_reorder_updates_orders_and_prompt_pack() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Reorder scene plan",
        objective="Keep prompt packs in edited scene order",
        notes=None,
    )
    script = _create_draft_script_for_tests(client, project_id)
    script_id = script["id"]
    reordered_scene_ids = [scene["id"] for scene in reversed(script["scenes"])]

    reorder_response = client.post(
        f"/api/scripts/{script_id}/scenes/reorder",
        json={"scene_ids": reordered_scene_ids},
    )

    assert reorder_response.status_code == 200
    reordered_script = reorder_response.json()
    assert [scene["id"] for scene in reordered_script["scenes"]] == reordered_scene_ids
    assert [scene["scene_order"] for scene in reordered_script["scenes"]] == [1, 2, 3, 4]
    assert reordered_script["estimated_duration_seconds"] == script["estimated_duration_seconds"]

    prompt_pack_response = client.get(f"/api/scripts/{script_id}/prompt-pack")
    assert prompt_pack_response.status_code == 200
    assert [
        scene_prompt["scene_id"] for scene_prompt in prompt_pack_response.json()["scenes"]
    ] == reordered_scene_ids

    app.dependency_overrides.clear()


def test_scene_reorder_requires_complete_current_scene_set_and_draft_script() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Validate scene reorder",
        objective="Block invalid scene order payloads",
        notes=None,
    )
    script = _create_draft_script_for_tests(client, project_id)
    script_id = script["id"]
    scene_ids = [scene["id"] for scene in script["scenes"]]

    duplicate_response = client.post(
        f"/api/scripts/{script_id}/scenes/reorder",
        json={"scene_ids": [scene_ids[0], scene_ids[0], *scene_ids[2:]]},
    )
    assert duplicate_response.status_code == 409
    assert "exactly once" in _error_message(duplicate_response)

    missing_response = client.post(
        f"/api/scripts/{script_id}/scenes/reorder",
        json={"scene_ids": scene_ids[:-1]},
    )
    assert missing_response.status_code == 409
    assert "exactly once" in _error_message(missing_response)

    approve_script_response = client.post(f"/api/scripts/{script_id}/approve", json={})
    assert approve_script_response.status_code == 200

    blocked_response = client.post(
        f"/api/scripts/{script_id}/scenes/reorder",
        json={"scene_ids": list(reversed(scene_ids))},
    )
    assert blocked_response.status_code == 409
    assert "draft or rejected" in _error_message(blocked_response)

    app.dependency_overrides.clear()


def test_prompt_pack_rejects_non_contiguous_scene_order() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Validate scene order before prompts",
        objective="Do not hand workers a broken scene plan",
        notes=None,
    )
    script = _create_draft_script_for_tests(client, project_id)
    script_id = script["id"]

    with session_factory() as session:
        stored_script = session.get(ProjectScript, UUID(script_id))
        assert stored_script is not None
        scene = stored_script.scenes[0]
        scene.scene_order = 99
        session.add(scene)
        session.commit()

    prompt_pack_response = client.get(f"/api/scripts/{script_id}/prompt-pack")

    assert prompt_pack_response.status_code == 409
    assert "contiguous" in _error_message(prompt_pack_response)

    app.dependency_overrides.clear()


def test_script_regeneration_preserves_version_history() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Regenerate script versions",
        objective="Preserve prior script attempts",
        notes=None,
    )

    first_script = _create_draft_script_for_tests(client, project_id)
    second_script_response = client.post(
        f"/api/projects/{project_id}/scripts/generate",
        json={"source_feedback_notes": "Make the second pass more concrete."},
    )

    assert second_script_response.status_code == 201
    second_script = second_script_response.json()
    assert second_script["version_number"] == 2
    assert second_script["source_feedback_notes"] == "Make the second pass more concrete."

    current_script_response = client.get(f"/api/projects/{project_id}/scripts/current")
    assert current_script_response.status_code == 200
    assert current_script_response.json()["id"] == second_script["id"]

    with session_factory() as session:
        stored_first_script = session.get(ProjectScript, UUID(first_script["id"]))
        assert stored_first_script is not None
        assert stored_first_script.status.value == "superseded"

    app.dependency_overrides.clear()


def test_scene_updates_are_blocked_after_script_approval() -> None:
    client = _make_test_client()
    brand_profile_response = client.post(
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
    brand_profile_id = brand_profile_response.json()["id"]

    create_response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": "Freeze scenes after approval",
            "target_platform": "youtube_shorts",
            "objective": "Protect approved script content",
            "notes": None,
        },
    )
    project_id = create_response.json()["id"]

    ideas_response = client.post(f"/api/projects/{project_id}/ideas/generate")
    approved_idea_id = ideas_response.json()[0]["id"]
    client.post(f"/api/ideas/{approved_idea_id}/approve", json={})

    script_response = client.post(f"/api/projects/{project_id}/scripts/generate", json={})
    script = script_response.json()
    script_id = script["id"]
    first_scene_id = script["scenes"][0]["id"]

    approve_script_response = client.post(f"/api/scripts/{script_id}/approve", json={})
    assert approve_script_response.status_code == 200

    blocked_update_response = client.patch(
        f"/api/scenes/{first_scene_id}",
        json={"overlay_text": "This should not be allowed"},
    )
    assert blocked_update_response.status_code == 409
    assert "draft or rejected" in _error_message(blocked_update_response)

    app.dependency_overrides.clear()


def test_queue_audio_generation_creates_job_and_planned_asset() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Queue narration after approval",
        objective="Validate queued narration planning",
        notes=None,
    )
    script = _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(
        f"/api/projects/{project_id}/generate/audio",
        json={"voice_label": "Warm guide"},
    )

    assert queue_response.status_code == 201
    queued_job = queue_response.json()
    assert queued_job["job_type"] == "generate_audio_browser"
    assert queued_job["provider_name"] == "elevenlabs_web"
    assert queued_job["state"] == "queued"
    assert queued_job["script_id"] == script["id"]
    assert queued_job["payload_json"]["voice_label"] == "Warm guide"

    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert len([job for job in jobs if job["job_type"] == "generate_audio_browser"]) == 1

    assets_response = client.get(f"/api/projects/{project_id}/assets")
    assert assets_response.status_code == 200
    assets = assets_response.json()
    assert len(assets) == 1
    assert assets[0]["asset_type"] == "narration_audio"
    assert assets[0]["status"] == "planned"
    assert assets[0]["provider_name"] == "elevenlabs_web"
    assert assets[0]["generation_attempt_id"] is not None
    assert "/audio/" in assets[0]["file_path"]

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "asset_generation"

    app.dependency_overrides.clear()


def test_queue_visual_generation_creates_scene_assets_for_current_script() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Queue visual jobs",
        objective="Validate queued visual planning",
        notes=None,
    )
    script = _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/visuals", json={})

    assert queue_response.status_code == 201
    queued_job = queue_response.json()
    assert queued_job["job_type"] == "generate_visuals_browser"
    assert queued_job["provider_name"] == "flow_web"
    assert queued_job["payload_json"]["scene_count"] == len(script["scenes"])

    assets_response = client.get(f"/api/projects/{project_id}/assets")
    assert assets_response.status_code == 200
    assets = assets_response.json()
    assert len(assets) == len(script["scenes"])
    assert all(asset["asset_type"] == "scene_image" for asset in assets)
    assert all(asset["status"] == "planned" for asset in assets)
    assert all(asset["provider_name"] == "flow_web" for asset in assets)
    assert all(asset["scene_id"] is not None for asset in assets)
    assert all(asset["generation_attempt_id"] is not None for asset in assets)
    assert all(asset["file_path"].endswith(".svg") for asset in assets)

    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs_response.status_code == 200
    assert (
        len([job for job in jobs_response.json() if job["job_type"] == "generate_visuals_browser"])
        == 1
    )

    app.dependency_overrides.clear()


def test_queue_generation_blocks_duplicate_active_job_for_same_script() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Prevent duplicate jobs",
        objective="Ensure queueing stays idempotent enough for v1",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    first_queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert first_queue_response.status_code == 201

    duplicate_queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert duplicate_queue_response.status_code == 409
    assert "active audio generation job" in _error_message(duplicate_queue_response)

    app.dependency_overrides.clear()


def test_queue_generation_requires_approved_script() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Require approval before jobs",
        objective="Keep generation jobs behind approval",
        notes=None,
    )

    ideas_response = client.post(f"/api/projects/{project_id}/ideas/generate")
    approved_idea_id = ideas_response.json()[0]["id"]
    client.post(f"/api/ideas/{approved_idea_id}/approve", json={})
    client.post(f"/api/projects/{project_id}/scripts/generate", json={})

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 409
    assert "current script to be approved" in _error_message(queue_response)

    app.dependency_overrides.clear()


def test_job_detail_includes_attempts_and_related_assets() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Inspect queued job",
        objective="Expose attempts and assets for operator visibility",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    detail_response = client.get(f"/api/jobs/{job_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["job"]["id"] == job_id
    assert detail["job"]["state"] == "queued"
    assert isinstance(detail["job"]["payload_json"]["correlation_id"], str)
    assert len(detail["generation_attempts"]) == 1
    assert detail["generation_attempts"][0]["background_job_id"] == job_id
    assert len(detail["related_assets"]) == 1
    assert detail["related_assets"][0]["asset_type"] == "narration_audio"
    assert detail["related_assets"][0]["status"] == "planned"
    assert len(detail["job_logs"]) == 1
    assert detail["job_logs"][0]["event_type"] == "job_queued"

    activity_response = client.get(f"/api/projects/{project_id}/activity")
    assert activity_response.status_code == 200
    activity = activity_response.json()
    assert any(entry["activity_type"] == "job_queued" for entry in activity)

    app.dependency_overrides.clear()


def test_job_manual_intervention_marks_waiting_external_and_logs_reason() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Manual intervention job",
        objective="Expose manual intervention job state",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    intervention_response = client.post(
        f"/api/jobs/{job_id}/manual-intervention",
        json={"reason": "Login expired and the browser session needs operator action."},
    )
    assert intervention_response.status_code == 200
    detail = intervention_response.json()
    assert detail["job"]["state"] == "waiting_external"
    assert "Login expired" in detail["job"]["error_message"]
    assert any(log["event_type"] == "manual_intervention_required" for log in detail["job_logs"])

    activity_response = client.get(f"/api/projects/{project_id}/activity")
    assert activity_response.status_code == 200
    assert any(
        entry["activity_type"] == "manual_intervention_required"
        for entry in activity_response.json()
    )

    app.dependency_overrides.clear()


def test_operations_recovery_snapshot_surfaces_jobs_and_ingest_warnings() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Recover blocked jobs",
        objective="Validate the operations recovery dashboard data",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    failed_queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert failed_queue_response.status_code == 201
    failed_job_id = failed_queue_response.json()["id"]

    with session_factory() as session:
        failed_job = get_background_job(session, UUID(failed_job_id))
        assert failed_job is not None
        mark_job_failed(session, failed_job, "Provider timed out while generating narration.")

    waiting_queue_response = client.post(f"/api/projects/{project_id}/generate/visuals", json={})
    assert waiting_queue_response.status_code == 201
    waiting_job_id = waiting_queue_response.json()["id"]

    with session_factory() as session:
        waiting_job = get_background_job(session, UUID(waiting_job_id))
        assert waiting_job is not None
        mark_job_manual_intervention_required(
            session,
            waiting_job,
            reason="Provider login expired.",
        )
        waiting_job = get_background_job(session, UUID(waiting_job_id))
        assert waiting_job is not None
        create_job_log(
            session,
            waiting_job,
            event_type="downloads_quarantined",
            message="Unexpected files were quarantined.",
            level="warning",
            metadata={
                "expected_count": 1,
                "actual_count": 2,
                "quarantine_paths": ["storage/projects/example/quarantine/file.wav"],
            },
        )
        create_job_log(
            session,
            waiting_job,
            event_type="duplicate_asset_detected",
            message="Generated asset checksum matches an existing asset.",
            level="warning",
            metadata={"duplicate_asset_ids": ["asset-1"]},
        )
        session.commit()

    stale_queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert stale_queue_response.status_code == 201
    stale_job_id = stale_queue_response.json()["id"]

    with session_factory() as session:
        stale_cutoff = datetime.now(UTC) - timedelta(hours=2)
        session.execute(
            update(BackgroundJob)
            .where(BackgroundJob.id == UUID(stale_job_id))
            .values(
                state=BackgroundJobState.RUNNING,
                updated_at=stale_cutoff,
            )
        )
        session.commit()

    recovery_response = client.get("/api/operations/recovery?stale_after_minutes=30&limit=10")
    assert recovery_response.status_code == 200
    recovery = recovery_response.json()

    assert recovery["summary"]["failed_jobs"] == 1
    assert recovery["summary"]["waiting_jobs"] == 1
    assert recovery["summary"]["stale_running_jobs"] == 1
    assert recovery["summary"]["quarantined_downloads"] == 1
    assert recovery["summary"]["duplicate_asset_warnings"] == 1
    assert recovery["summary"]["total_attention_items"] == 5

    assert recovery["failed_jobs"][0]["job"]["id"] == failed_job_id
    assert recovery["failed_jobs"][0]["project_title"] == "Recover blocked jobs"
    assert recovery["failed_jobs"][0]["latest_log_event_type"] == "job_failed"
    assert recovery["waiting_jobs"][0]["job"]["id"] == waiting_job_id
    assert recovery["stale_running_jobs"][0]["job"]["id"] == stale_job_id
    assert recovery["quarantined_downloads"][0]["event_type"] == "downloads_quarantined"
    assert recovery["duplicate_asset_warnings"][0]["event_type"] == "duplicate_asset_detected"

    app.dependency_overrides.clear()


def test_artifact_retention_plan_surfaces_safe_and_manual_cleanup_candidates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Retention review project",
        objective="Plan safe cleanup without deleting generated files",
        notes=None,
    )
    script = _create_approved_script_for_tests(client, project_id)

    stored_asset_path = Path("storage") / "projects" / project_id / "audio" / "rejected.wav"
    stored_asset_path.parent.mkdir(parents=True, exist_ok=True)
    stored_asset_path.write_bytes(b"rejected narration")
    missing_asset_path = f"storage/projects/{project_id}/audio/missing.wav"

    with session_factory() as session:
        project = session.get(Project, UUID(project_id))
        script_model = session.get(ProjectScript, UUID(str(script["id"])))
        assert project is not None
        assert script_model is not None

        rejected_asset = Asset(
            user_id=project.user_id,
            project_id=project.id,
            script_id=script_model.id,
            scene_id=None,
            generation_attempt_id=None,
            asset_type=AssetType.NARRATION_AUDIO,
            status=AssetStatus.REJECTED,
            provider_name=ProviderName.ELEVENLABS_WEB,
            file_path=str(stored_asset_path),
            mime_type="audio/wav",
            duration_seconds=12,
            width=None,
            height=None,
            checksum="rejected-audio-checksum",
        )
        missing_asset = Asset(
            user_id=project.user_id,
            project_id=project.id,
            script_id=script_model.id,
            scene_id=None,
            generation_attempt_id=None,
            asset_type=AssetType.SCENE_VIDEO,
            status=AssetStatus.FAILED,
            provider_name=ProviderName.FLOW_WEB,
            file_path=missing_asset_path,
            mime_type="video/mp4",
            duration_seconds=8,
            width=1080,
            height=1920,
            checksum=None,
        )
        session.add_all([rejected_asset, missing_asset])
        session.commit()

    response = client.get("/api/operations/artifacts/retention-plan?limit=10")
    assert response.status_code == 200
    retention_plan = response.json()
    candidates_by_path = {
        candidate["file_path"]: candidate for candidate in retention_plan["candidates"]
    }

    safe_candidate = candidates_by_path[str(stored_asset_path)]
    assert safe_candidate["safe_to_cleanup"] is True
    assert safe_candidate["recommended_action"] == "move_to_retention"
    assert safe_candidate["file_exists"] is True
    assert safe_candidate["size_bytes"] == len(b"rejected narration")
    assert "/retention/asset-" in safe_candidate["retention_manifest_path"]

    repair_candidate = candidates_by_path[missing_asset_path]
    assert repair_candidate["safe_to_cleanup"] is False
    assert repair_candidate["recommended_action"] == "repair_missing_file"
    assert repair_candidate["file_exists"] is False
    assert repair_candidate["retention_manifest_path"] is None

    assert retention_plan["summary"]["candidate_count"] == 2
    assert retention_plan["summary"]["safe_candidate_count"] == 1
    assert retention_plan["summary"]["total_reclaimable_bytes"] == len(b"rejected narration")

    app.dependency_overrides.clear()


def test_cancel_queued_generation_job_marks_attempts_and_assets_failed() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Cancel queued job",
        objective="Stop queued work before a worker claims it",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200
    detail = cancel_response.json()
    assert detail["job"]["state"] == "cancelled"
    assert detail["job"]["error_message"] == "Cancelled by user."
    assert detail["generation_attempts"][0]["state"] == "cancelled"
    assert detail["related_assets"][0]["status"] == "failed"
    assert any(log["event_type"] == "job_cancelled" for log in detail["job_logs"])

    jobs_response = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs_response.status_code == 200
    cancelled_job = next(job for job in jobs_response.json() if job["id"] == job_id)
    assert cancelled_job["state"] == "cancelled"

    app.dependency_overrides.clear()


def test_retry_cancelled_job_reuses_existing_attempts_and_assets() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Retry cancelled job",
        objective="Reuse existing queue records without duplicate assets",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/visuals", json={})
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    initial_detail_response = client.get(f"/api/jobs/{job_id}")
    initial_detail = initial_detail_response.json()
    initial_attempt_ids = {attempt["id"] for attempt in initial_detail["generation_attempts"]}
    initial_asset_ids = {asset["id"] for asset in initial_detail["related_assets"]}

    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200

    retry_response = client.post(f"/api/jobs/{job_id}/retry")
    assert retry_response.status_code == 200
    retried_detail = retry_response.json()
    assert retried_detail["job"]["state"] == "queued"
    assert retried_detail["job"]["progress_percent"] == 0
    assert retried_detail["job"]["error_message"] is None
    retried_attempt_ids = {attempt["id"] for attempt in retried_detail["generation_attempts"]}
    assert retried_attempt_ids == initial_attempt_ids
    assert {asset["id"] for asset in retried_detail["related_assets"]} == initial_asset_ids
    assert all(attempt["state"] == "queued" for attempt in retried_detail["generation_attempts"])
    assert all(asset["status"] == "planned" for asset in retried_detail["related_assets"])
    assert any(log["event_type"] == "job_retried" for log in retried_detail["job_logs"])

    assets_response = client.get(f"/api/projects/{project_id}/assets")
    assert assets_response.status_code == 200
    assert {asset["id"] for asset in assets_response.json()} == initial_asset_ids

    app.dependency_overrides.clear()


def test_retry_failed_job_resets_error_without_duplicate_assets() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Retry failed job",
        objective="Recover from worker failure safely",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    initial_detail_response = client.get(f"/api/jobs/{job_id}")
    initial_asset_ids = {asset["id"] for asset in initial_detail_response.json()["related_assets"]}

    with session_factory() as session:
        job = get_background_job(session, UUID(job_id))
        assert job is not None
        mark_job_failed(session, job, "Provider timed out.")

    failed_detail_response = client.get(f"/api/jobs/{job_id}")
    assert failed_detail_response.status_code == 200
    failed_detail = failed_detail_response.json()
    assert failed_detail["job"]["state"] == "failed"
    assert failed_detail["related_assets"][0]["status"] == "failed"
    assert any(log["event_type"] == "job_failed" for log in failed_detail["job_logs"])

    retry_response = client.post(f"/api/jobs/{job_id}/retry")
    assert retry_response.status_code == 200
    retried_detail = retry_response.json()
    assert retried_detail["job"]["state"] == "queued"
    assert retried_detail["job"]["error_message"] is None
    assert {asset["id"] for asset in retried_detail["related_assets"]} == initial_asset_ids
    assert all(asset["status"] == "planned" for asset in retried_detail["related_assets"])
    assert any(log["event_type"] == "job_retried" for log in retried_detail["job_logs"])

    app.dependency_overrides.clear()


def test_retry_policy_blocks_exhausted_and_unsupported_job_types() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Retry policy limits",
        objective="Validate per-job retry budgets",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    with session_factory() as session:
        job = get_background_job(session, UUID(job_id))
        assert job is not None
        job.state = BackgroundJobState.FAILED
        job.attempts = 4
        job.error_message = "Provider exhausted retries."
        session.add(job)
        session.commit()

    exhausted_retry_response = client.post(f"/api/jobs/{job_id}/retry")
    assert exhausted_retry_response.status_code == 409
    assert "Retry limit exceeded" in _error_message(exhausted_retry_response)

    with session_factory() as session:
        project = session.get(Project, UUID(project_id))
        assert project is not None
        planning_job = BackgroundJob(
            user_id=project.user_id,
            project_id=project.id,
            script_id=None,
            job_type=BackgroundJobType.GENERATE_IDEAS,
            provider_name=None,
            state=BackgroundJobState.FAILED,
            payload_json={"idea_count": 3},
            attempts=1,
            progress_percent=0,
            error_message="Inline planner failed.",
            started_at=None,
            finished_at=datetime.now(UTC),
        )
        session.add(planning_job)
        session.commit()
        planning_job_id = str(planning_job.id)

    unsupported_retry_response = client.post(f"/api/jobs/{planning_job_id}/retry")
    assert unsupported_retry_response.status_code == 409
    assert "does not support manual retry" in _error_message(unsupported_retry_response)

    app.dependency_overrides.clear()


def test_resume_stale_running_browser_job_requeues_unfinished_work() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Resume stale browser job",
        objective="Recover interrupted running work safely",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    with session_factory() as session:
        job = get_background_job(session, UUID(job_id))
        assert job is not None
        attempt = job.generation_attempts[0]
        asset = attempt.assets[0]
        job.state = BackgroundJobState.RUNNING
        job.progress_percent = 45
        job.updated_at = datetime.now(UTC)
        attempt.state = BackgroundJobState.RUNNING
        asset.status = AssetStatus.GENERATING
        asset.checksum = "partial-checksum"
        session.add_all([job, attempt, asset])
        session.commit()

    recent_resume_response = client.post(f"/api/jobs/{job_id}/resume")
    assert recent_resume_response.status_code == 409
    assert "not stale enough" in _error_message(recent_resume_response)

    with session_factory() as session:
        stale_cutoff = datetime.now(UTC) - timedelta(hours=2)
        job = get_background_job(session, UUID(job_id))
        assert job is not None
        job.state = BackgroundJobState.RUNNING
        job.updated_at = stale_cutoff
        session.add(job)
        session.commit()

    resume_response = client.post(f"/api/jobs/{job_id}/resume")
    assert resume_response.status_code == 200
    resumed_detail = resume_response.json()
    assert resumed_detail["job"]["state"] == "queued"
    assert resumed_detail["job"]["progress_percent"] == 0
    assert resumed_detail["job"]["error_message"] is None
    assert resumed_detail["generation_attempts"][0]["state"] == "queued"
    assert resumed_detail["related_assets"][0]["status"] == "planned"
    assert resumed_detail["related_assets"][0]["checksum"] is None
    assert any(log["event_type"] == "job_resumed" for log in resumed_detail["job_logs"])

    app.dependency_overrides.clear()


def test_job_controls_block_invalid_states() -> None:
    client = _make_test_client()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Block invalid job operations",
        objective="Keep retry and cancel state-safe",
        notes=None,
    )
    _create_approved_script_for_tests(client, project_id)

    queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert queue_response.status_code == 201
    job_id = queue_response.json()["id"]

    retry_queued_response = client.post(f"/api/jobs/{job_id}/retry")
    assert retry_queued_response.status_code == 409
    assert "failed or cancelled" in _error_message(retry_queued_response)

    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200

    second_cancel_response = client.post(f"/api/jobs/{job_id}/cancel")
    assert second_cancel_response.status_code == 409
    assert "queued or waiting-external" in _error_message(second_cancel_response)

    replacement_queue_response = client.post(f"/api/projects/{project_id}/generate/audio", json={})
    assert replacement_queue_response.status_code == 201

    blocked_retry_response = client.post(f"/api/jobs/{job_id}/retry")
    assert blocked_retry_response.status_code == 409
    assert "another active job" in _error_message(blocked_retry_response)

    app.dependency_overrides.clear()


def test_final_video_approval_unblocks_publish_prep_with_idempotency() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Approve final video",
        objective="Move a completed rough cut into publish prep",
        notes=None,
    )
    script = _create_approved_script_for_tests(client, project_id)
    rough_cut_asset_id = _move_project_to_final_review_for_tests(
        session_factory,
        project_id=project_id,
        script_id=str(script["id"]),
    )

    blocked_prepare_response = client.post(
        f"/api/projects/{project_id}/publish-jobs/prepare",
        json={
            "platform": "youtube_shorts",
            "title": "Ready too early",
            "description": "This should not prepare before final approval.",
            "hashtags": ["#CreatorOS"],
        },
    )
    assert blocked_prepare_response.status_code == 409
    assert "final video approval" in _error_message(blocked_prepare_response).lower()

    approval_response = client.post(f"/api/projects/{project_id}/final-video/approve", json={})
    assert approval_response.status_code == 200
    approval = approval_response.json()
    assert approval["stage"] == "final_video"
    assert approval["decision"] == "approved"
    assert approval["target_type"] == "asset"
    assert approval["target_id"] == rough_cut_asset_id

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "ready_to_publish"

    prepare_payload = {
        "platform": "youtube_shorts",
        "title": "Final publish title",
        "description": "Approved metadata for publishing.",
        "hashtags": ["#CreatorOS", "#Workflow"],
        "idempotency_key": "publish-prep-1",
    }
    prepare_response = client.post(
        f"/api/projects/{project_id}/publish-jobs/prepare",
        json=prepare_payload,
    )
    assert prepare_response.status_code == 201
    publish_job = prepare_response.json()
    assert publish_job["status"] == "pending_approval"
    assert publish_job["final_asset_id"] == rough_cut_asset_id
    assert publish_job["hashtags_json"] == ["#CreatorOS", "#Workflow"]

    idempotent_prepare_response = client.post(
        f"/api/projects/{project_id}/publish-jobs/prepare",
        json=prepare_payload,
    )
    assert idempotent_prepare_response.status_code == 201
    assert idempotent_prepare_response.json()["id"] == publish_job["id"]

    list_response = client.get(f"/api/projects/{project_id}/publish-jobs")
    assert list_response.status_code == 200
    assert [job["id"] for job in list_response.json()] == [publish_job["id"]]

    app.dependency_overrides.clear()


def test_final_video_approval_prefers_exported_final_asset_for_publish_prep() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Prefer final export for publish prep",
        objective="Use the dedicated final video when it exists",
        notes=None,
    )
    script = _create_approved_script_for_tests(client, project_id)
    rough_cut_asset_id, final_video_asset_id = _move_project_to_final_review_with_export_for_tests(
        session_factory,
        project_id=project_id,
        script_id=str(script["id"]),
    )

    approval_response = client.post(f"/api/projects/{project_id}/final-video/approve", json={})

    assert approval_response.status_code == 200
    approval = approval_response.json()
    assert approval["target_id"] == final_video_asset_id
    assert approval["target_id"] != rough_cut_asset_id

    prepare_response = client.post(
        f"/api/projects/{project_id}/publish-jobs/prepare",
        json={
            "platform": "youtube_shorts",
            "title": "Use final export",
            "description": "Publish from the final MP4 asset.",
            "hashtags": ["#CreatorOS"],
        },
    )

    assert prepare_response.status_code == 201
    publish_job = prepare_response.json()
    assert publish_job["final_asset_id"] == final_video_asset_id

    app.dependency_overrides.clear()


def test_publish_job_approval_schedule_and_manual_publish_flow() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Publish center",
        objective="Validate explicit publish approval and manual completion",
        notes=None,
    )
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
            "title": "Publish this video",
            "description": "Metadata that needs approval.",
            "hashtags": ["#AI", "#CreatorOS"],
        },
    )
    assert prepare_response.status_code == 201
    publish_job_id = prepare_response.json()["id"]

    blocked_schedule_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/schedule",
        json={"scheduled_for": "2030-01-01T00:00:00+00:00"},
    )
    assert blocked_schedule_response.status_code == 409
    assert "approved publish jobs" in _error_message(blocked_schedule_response)

    approve_response = client.post(f"/api/publish-jobs/{publish_job_id}/approve", json={})
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    approvals_response = client.get(f"/api/projects/{project_id}/approvals")
    assert approvals_response.status_code == 200
    assert any(
        approval["stage"] == "publish" and approval["target_id"] == publish_job_id
        for approval in approvals_response.json()
    )

    schedule_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/schedule",
        json={"scheduled_for": "2030-01-01T00:00:00+00:00"},
    )
    assert schedule_response.status_code == 200
    assert schedule_response.json()["status"] == "scheduled"

    idempotent_schedule_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/schedule",
        json={"scheduled_for": "2030-01-01T00:00:00+00:00"},
    )
    assert idempotent_schedule_response.status_code == 200
    assert idempotent_schedule_response.json()["id"] == publish_job_id
    assert idempotent_schedule_response.json()["scheduled_for"].startswith(
        "2030-01-01T00:00:00"
    )

    reschedule_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/schedule",
        json={"scheduled_for": "2030-01-02T00:00:00+00:00"},
    )
    assert reschedule_response.status_code == 409
    assert "cannot be rescheduled" in _error_message(reschedule_response)

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "scheduled"

    published_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/mark-published",
        json={
            "external_post_id": "yt-short-123",
            "manual_publish_notes": "Published manually after final approval.",
        },
    )
    assert published_response.status_code == 200
    assert published_response.json()["status"] == "published"
    assert published_response.json()["external_post_id"] == "yt-short-123"

    final_project_response = client.get(f"/api/projects/{project_id}")
    assert final_project_response.status_code == 200
    assert final_project_response.json()["status"] == "published"

    app.dependency_overrides.clear()


def test_publish_metadata_editor_updates_pending_job_and_requires_reapproval() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Edit publish metadata",
        objective="Revise title, schedule, thumbnail, and platform settings before publishing",
        notes=None,
    )
    script = _create_approved_script_for_tests(client, project_id)
    _move_project_to_final_review_for_tests(
        session_factory,
        project_id=project_id,
        script_id=str(script["id"]),
    )
    thumbnail_asset_id = _create_ready_thumbnail_for_tests(
        session_factory,
        project_id=project_id,
        script_id=str(script["id"]),
    )
    client.post(f"/api/projects/{project_id}/final-video/approve", json={})

    prepare_response = client.post(
        f"/api/projects/{project_id}/publish-jobs/prepare",
        json={
            "platform": "youtube_shorts",
            "title": "Original publish title",
            "description": "Original publish description.",
            "hashtags": ["CreatorOS", "#AI", "#AI"],
        },
    )
    assert prepare_response.status_code == 201
    publish_job_id = prepare_response.json()["id"]

    pending_update_response = client.patch(
        f"/api/publish-jobs/{publish_job_id}/metadata",
        json={
            "title": "Sharper publish title",
            "description": "Updated publish description.",
            "hashtags": ["CreatorOS", "#Workflow", ""],
            "scheduled_for": "2030-01-02T03:00:00+00:00",
            "thumbnail_asset_id": thumbnail_asset_id,
            "platform_settings": {"privacy": "private", "playlist_id": "creatoros"},
            "change_notes": "Tightened the hook before publish approval.",
        },
    )
    assert pending_update_response.status_code == 200
    updated_job = pending_update_response.json()
    assert updated_job["status"] == "pending_approval"
    assert updated_job["title"] == "Sharper publish title"
    assert updated_job["description"] == "Updated publish description."
    assert updated_job["hashtags_json"] == ["#CreatorOS", "#Workflow"]
    assert updated_job["metadata_json"]["thumbnail_asset_id"] == thumbnail_asset_id
    assert updated_job["metadata_json"]["platform_settings"] == {
        "privacy": "private",
        "playlist_id": "creatoros",
    }
    assert updated_job["metadata_json"]["last_metadata_update"]["change_notes"] == (
        "Tightened the hook before publish approval."
    )

    approve_response = client.post(f"/api/publish-jobs/{publish_job_id}/approve", json={})
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    approved_update_response = client.patch(
        f"/api/publish-jobs/{publish_job_id}/metadata",
        json={"title": "Needs approval again", "change_notes": "Changed after approval."},
    )
    assert approved_update_response.status_code == 200
    assert approved_update_response.json()["status"] == "pending_approval"

    blocked_schedule_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/schedule",
        json={"scheduled_for": "2030-01-03T00:00:00+00:00"},
    )
    assert blocked_schedule_response.status_code == 409
    assert "approved publish jobs" in _error_message(blocked_schedule_response)

    activity_response = client.get(f"/api/projects/{project_id}/activity")
    assert activity_response.status_code == 200
    assert any(
        activity["activity_type"] == "publish_metadata_updated"
        and activity["metadata_json"]["requires_reapproval"] is True
        for activity in activity_response.json()
    )

    app.dependency_overrides.clear()


def test_publish_metadata_editor_blocks_scheduled_jobs() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Lock scheduled publish metadata",
        objective="Prevent edits after schedule handoff",
        notes=None,
    )
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
            "title": "Scheduled metadata",
            "description": "This metadata will lock once scheduled.",
            "hashtags": ["#CreatorOS"],
        },
    )
    publish_job_id = prepare_response.json()["id"]
    client.post(f"/api/publish-jobs/{publish_job_id}/approve", json={})
    schedule_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/schedule",
        json={"scheduled_for": "2030-01-01T00:00:00+00:00"},
    )
    assert schedule_response.status_code == 200

    blocked_update_response = client.patch(
        f"/api/publish-jobs/{publish_job_id}/metadata",
        json={"title": "Too late to edit"},
    )
    assert blocked_update_response.status_code == 409
    assert "before scheduling or publishing" in _error_message(blocked_update_response)

    app.dependency_overrides.clear()


def test_project_publish_transitions_require_publish_job_state() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Guard publish transitions",
        objective="Block manual status jumps without publish job state",
        notes=None,
    )
    script = _create_approved_script_for_tests(client, project_id)
    _move_project_to_final_review_for_tests(
        session_factory,
        project_id=project_id,
        script_id=str(script["id"]),
    )
    client.post(f"/api/projects/{project_id}/final-video/approve", json={})

    blocked_scheduled_response = client.post(
        f"/api/projects/{project_id}/transition",
        json={"target_status": "scheduled"},
    )
    assert blocked_scheduled_response.status_code == 409
    assert "publish job" in _error_message(blocked_scheduled_response)

    prepare_response = client.post(
        f"/api/projects/{project_id}/publish-jobs/prepare",
        json={
            "platform": "youtube_shorts",
            "title": "Needs publish state",
            "description": "Prepared but not yet approved or scheduled.",
            "hashtags": [],
        },
    )
    publish_job_id = prepare_response.json()["id"]
    client.post(f"/api/publish-jobs/{publish_job_id}/approve", json={})

    blocked_published_response = client.post(
        f"/api/projects/{project_id}/transition",
        json={"target_status": "published"},
    )
    assert blocked_published_response.status_code == 409
    assert "marked as published" in _error_message(blocked_published_response)

    app.dependency_overrides.clear()


def test_analytics_sync_requires_published_job_and_generates_insights() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Learn from analytics",
        objective="Persist post performance and generate recommendations",
        notes=None,
    )
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
            "description": "Metadata for analytics validation.",
            "hashtags": ["#CreatorOS"],
        },
    )
    publish_job_id = prepare_response.json()["id"]

    blocked_sync_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/sync-analytics",
        json={
            "views": 1000,
            "likes": 90,
            "comments": 12,
            "shares": 8,
        },
    )
    assert blocked_sync_response.status_code == 409
    assert "after a publish job is marked published" in _error_message(blocked_sync_response)

    client.post(f"/api/publish-jobs/{publish_job_id}/approve", json={})
    client.post(
        f"/api/publish-jobs/{publish_job_id}/mark-published",
        json={"external_post_id": "post-analytics-1"},
    )

    sync_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/sync-analytics",
        json={
            "views": 1000,
            "likes": 90,
            "comments": 12,
            "shares": 8,
            "saves": 5,
            "avg_view_duration": 18.5,
            "retention_json": {"three_second_hold": 0.76},
        },
    )
    assert sync_response.status_code == 201
    snapshot = sync_response.json()
    assert snapshot["publish_job_id"] == publish_job_id
    assert snapshot["views"] == 1000
    assert snapshot["avg_view_duration"] == 18.5

    analytics_response = client.get(f"/api/projects/{project_id}/analytics")
    assert analytics_response.status_code == 200
    analytics = analytics_response.json()
    assert len(analytics["snapshots"]) == 1
    assert len(analytics["insights"]) >= 1
    assert any(
        insight["insight_type"] == "engagement_rate"
        and "Engagement is strong" in insight["summary"]
        for insight in analytics["insights"]
    )

    app.dependency_overrides.clear()


def test_analytics_learnings_feed_future_generation_context() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    source_project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Prior high-retention hook",
        objective="Measure what viewers respond to",
        notes=None,
    )
    source_script = _create_approved_script_for_tests(client, source_project_id)
    _move_project_to_final_review_for_tests(
        session_factory,
        project_id=source_project_id,
        script_id=str(source_script["id"]),
    )
    client.post(f"/api/projects/{source_project_id}/final-video/approve", json={})
    prepare_response = client.post(
        f"/api/projects/{source_project_id}/publish-jobs/prepare",
        json={
            "platform": "youtube_shorts",
            "title": "Analytics-backed source",
            "description": "Published source used to seed learning context.",
            "hashtags": ["#CreatorOS", "#Learning"],
        },
    )
    publish_job_id = prepare_response.json()["id"]
    client.post(f"/api/publish-jobs/{publish_job_id}/approve", json={})
    client.post(
        f"/api/publish-jobs/{publish_job_id}/mark-published",
        json={"external_post_id": "learning-source-1"},
    )
    sync_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/sync-analytics",
        json={
            "views": 2400,
            "likes": 220,
            "comments": 32,
            "shares": 18,
            "saves": 15,
            "avg_view_duration": 21.5,
        },
    )
    assert sync_response.status_code == 201

    target_project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Use analytics in the next idea",
        objective="Turn previous performance into a better creative brief",
        notes=None,
    )
    ideas_response = client.post(f"/api/projects/{target_project_id}/ideas/generate", json={})
    assert ideas_response.status_code == 201
    ideas = ideas_response.json()
    assert any("recent performance learning" in idea["rationale"].lower() for idea in ideas)

    jobs_response = client.get(f"/api/projects/{target_project_id}/jobs")
    assert jobs_response.status_code == 200
    idea_job = next(job for job in jobs_response.json() if job["job_type"] == "generate_ideas")
    idea_learning_context = idea_job["payload_json"]["analytics_learning_context"]
    assert idea_learning_context["available"] is True
    assert idea_learning_context["source_count"] >= 1
    assert idea_learning_context["items"][0]["source_project_id"] == source_project_id

    client.post(f"/api/ideas/{ideas[0]['id']}/approve", json={})
    script_response = client.post(f"/api/projects/{target_project_id}/scripts/generate", json={})
    assert script_response.status_code == 201
    script = script_response.json()
    assert "Recent analytics learning" in script["body"]
    assert "Learning focus" in script["caption"]
    assert any("Learning focus" in scene["notes"] for scene in script["scenes"])

    script_jobs_response = client.get(f"/api/projects/{target_project_id}/jobs")
    assert script_jobs_response.status_code == 200
    script_job = next(
        job for job in script_jobs_response.json() if job["job_type"] == "generate_script"
    )
    script_learning_context = script_job["payload_json"]["analytics_learning_context"]
    assert script_learning_context["available"] is True
    assert script_learning_context["items"][0]["source_project_id"] == source_project_id

    prompt_pack_response = client.get(f"/api/scripts/{script['id']}/prompt-pack")
    assert prompt_pack_response.status_code == 200
    prompt_pack = prompt_pack_response.json()
    assert prompt_pack["analytics_learning_context"]["available"] is True
    assert prompt_pack["analytics_learning_context"]["source_count"] >= 1
    assert "Learning focus" in prompt_pack["scenes"][0]["image_generation_prompt"]
    assert "Apply this learning focus" in prompt_pack["scenes"][0]["narration_direction"]

    app.dependency_overrides.clear()


def test_account_analytics_summarizes_cross_project_performance() -> None:
    client, session_factory = _make_test_client_with_session()
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Summarize account analytics",
        objective="Compare hooks duration voice and platform performance",
        notes=None,
    )
    script = _create_approved_script_for_tests(client, project_id)
    audio_response = client.post(
        f"/api/projects/{project_id}/generate/audio",
        json={"voice_label": "Warm guide"},
    )
    assert audio_response.status_code == 201

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
            "title": "Account analytics source",
            "description": "Published source used to validate account summaries.",
            "hashtags": ["#CreatorOS", "#Analytics"],
        },
    )
    publish_job_id = prepare_response.json()["id"]
    client.post(f"/api/publish-jobs/{publish_job_id}/approve", json={})
    client.post(
        f"/api/publish-jobs/{publish_job_id}/mark-published",
        json={"external_post_id": "account-summary-1"},
    )
    sync_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/sync-analytics",
        json={
            "views": 1500,
            "likes": 120,
            "comments": 22,
            "shares": 10,
            "saves": 8,
            "avg_view_duration": 17.5,
        },
    )
    assert sync_response.status_code == 201

    account_response = client.get("/api/analytics/account")
    assert account_response.status_code == 200
    account_analytics = account_response.json()
    assert account_analytics["overview"]["published_posts"] == 1
    assert account_analytics["overview"]["total_views"] == 1500
    assert account_analytics["overview"]["total_engagements"] == 160
    assert account_analytics["overview"]["top_platform"] == "youtube_shorts"

    top_post = account_analytics["top_posts"][0]
    assert top_post["publish_job_id"] == publish_job_id
    assert top_post["project_id"] == project_id
    assert top_post["views"] == 1500
    assert top_post["duration_seconds"] == script["estimated_duration_seconds"]

    assert account_analytics["hook_patterns"][0]["sample_project_id"] == project_id
    assert account_analytics["duration_buckets"][0]["publish_count"] == 1
    assert account_analytics["posting_windows"][0]["publish_count"] == 1
    assert account_analytics["voice_labels"][0]["label"] == "Warm guide"
    assert account_analytics["content_types"][0]["key"] == "youtube_shorts"
    assert account_analytics["recommendations"]

    app.dependency_overrides.clear()
