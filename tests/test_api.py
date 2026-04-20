from collections.abc import Generator
from uuid import UUID, uuid4

import apps.api.models  # noqa: F401
from apps.api.core.redaction import redact_sensitive_value
from apps.api.db.base import Base
from apps.api.db.session import get_db
from apps.api.main import app
from apps.api.models.asset import Asset
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.schemas.enums import AssetStatus, AssetType, ProjectStatus, ProviderName
from apps.api.services.background_jobs import get_background_job, mark_job_failed
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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
        "postgresql://user:password@example.com/db?token=abc "
        "cookie=session-value api_key=raw-key"
    )

    redacted = redact_sensitive_value(value)

    assert "user:password" not in redacted
    assert "abc" not in redacted
    assert "session-value" not in redacted
    assert "raw-key" not in redacted
    assert "[redacted]" in redacted


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

    get_response = client.get(f"/api/projects/{project_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "idea_pending_approval"

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

    prompt_pack_response = client.get(f"/api/scripts/{script_id}/prompt-pack")
    assert prompt_pack_response.status_code == 200
    prompt_pack = prompt_pack_response.json()
    assert prompt_pack["source_idea_title"]
    assert prompt_pack["scenes"][0]["overlay_text"] == "Updated overlay guidance"
    assert prompt_pack["scenes"][0]["estimated_duration_seconds"] == 9
    assert "Creator Lab" in prompt_pack["scenes"][0]["image_generation_prompt"]

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
    assert len(jobs) == 1

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
    assert len(jobs_response.json()) == 1

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
    assert jobs_response.json()[0]["state"] == "cancelled"

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
    initial_attempt_ids = {
        attempt["id"] for attempt in initial_detail["generation_attempts"]
    }
    initial_asset_ids = {asset["id"] for asset in initial_detail["related_assets"]}

    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200

    retry_response = client.post(f"/api/jobs/{job_id}/retry")
    assert retry_response.status_code == 200
    retried_detail = retry_response.json()
    assert retried_detail["job"]["state"] == "queued"
    assert retried_detail["job"]["progress_percent"] == 0
    assert retried_detail["job"]["error_message"] is None
    retried_attempt_ids = {
        attempt["id"] for attempt in retried_detail["generation_attempts"]
    }
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
