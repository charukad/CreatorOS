from collections.abc import Generator

import apps.api.models  # noqa: F401
from apps.api.db.base import Base
from apps.api.db.session import get_db
from apps.api.main import app
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


def test_live_health() -> None:
    client = TestClient(app)
    response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "api"


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
    assert "cannot transition" in transition_response.json()["detail"]

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
    assert "generated script" in move_to_script_response.json()["detail"]

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
    assert "current script is approved" in blocked_transition_response.json()["detail"]

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
    assert "draft or rejected" in blocked_update_response.json()["detail"]

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
    assert all(asset["asset_type"] == "scene_video" for asset in assets)
    assert all(asset["status"] == "planned" for asset in assets)
    assert all(asset["provider_name"] == "flow_web" for asset in assets)
    assert all(asset["scene_id"] is not None for asset in assets)
    assert all(asset["generation_attempt_id"] is not None for asset in assets)

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
    assert "active audio generation job" in duplicate_queue_response.json()["detail"]

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
    assert "current script to be approved" in queue_response.json()["detail"]

    app.dependency_overrides.clear()
