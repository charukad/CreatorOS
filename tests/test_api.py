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
