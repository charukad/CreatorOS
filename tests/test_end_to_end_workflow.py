from collections.abc import Generator
from pathlib import Path

import apps.api.models  # noqa: F401
import pytest
from apps.api.db.base import Base
from apps.api.db.session import get_db
from apps.api.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from workers.analytics.config import AnalyticsWorkerSettings
from workers.analytics.runtime import run_pending_jobs as run_analytics_jobs
from workers.browser.config import BrowserWorkerSettings
from workers.browser.providers.dry_run import DryRunElevenLabsProvider, DryRunFlowProvider
from workers.browser.runtime import run_pending_jobs as run_browser_jobs
from workers.media.config import MediaWorkerSettings
from workers.media.runtime import run_pending_jobs as run_media_jobs
from workers.publisher.config import PublisherWorkerSettings
from workers.publisher.runtime import run_pending_jobs as run_publisher_jobs


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


@pytest.fixture
def api_client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    session_factory = _create_test_session()
    client = _make_test_client(session_factory)
    try:
        yield client, session_factory
    finally:
        app.dependency_overrides.clear()


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
    assert response.status_code == 201
    return response.json()["id"]


def _create_project_for_tests(
    client: TestClient,
    brand_profile_id: str,
    *,
    title: str,
    objective: str,
) -> str:
    response = client.post(
        "/api/projects",
        json={
            "brand_profile_id": brand_profile_id,
            "title": title,
            "target_platform": "youtube_shorts",
            "objective": objective,
            "notes": None,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _generate_ideas(
    client: TestClient,
    project_id: str,
    *,
    source_feedback_notes: str | None = None,
) -> list[dict[str, object]]:
    response = client.post(
        f"/api/projects/{project_id}/ideas/generate",
        json={"source_feedback_notes": source_feedback_notes}
        if source_feedback_notes is not None
        else {},
    )
    assert response.status_code == 201
    return response.json()


def _approve_idea(
    client: TestClient,
    idea_id: str,
    *,
    feedback_notes: str | None = None,
) -> dict[str, object]:
    response = client.post(
        f"/api/ideas/{idea_id}/approve",
        json={"feedback_notes": feedback_notes} if feedback_notes is not None else {},
    )
    assert response.status_code == 200
    return response.json()


def _reject_idea(
    client: TestClient,
    idea_id: str,
    *,
    feedback_notes: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/ideas/{idea_id}/reject",
        json={"feedback_notes": feedback_notes},
    )
    assert response.status_code == 200
    return response.json()


def _generate_script(
    client: TestClient,
    project_id: str,
    *,
    source_feedback_notes: str | None = None,
) -> dict[str, object]:
    response = client.post(
        f"/api/projects/{project_id}/scripts/generate",
        json={"source_feedback_notes": source_feedback_notes}
        if source_feedback_notes is not None
        else {},
    )
    assert response.status_code == 201
    return response.json()


def _approve_script(client: TestClient, script_id: str) -> dict[str, object]:
    response = client.post(f"/api/scripts/{script_id}/approve", json={})
    assert response.status_code == 200
    return response.json()


def _reject_script(
    client: TestClient,
    script_id: str,
    *,
    feedback_notes: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/scripts/{script_id}/reject",
        json={"feedback_notes": feedback_notes},
    )
    assert response.status_code == 200
    return response.json()


def _create_approved_script_for_tests(client: TestClient, project_id: str) -> dict[str, object]:
    ideas = _generate_ideas(client, project_id)
    approved_idea = _approve_idea(client, ideas[0]["id"])
    assert approved_idea["status"] == "approved"
    script = _generate_script(client, project_id)
    approved_script = _approve_script(client, script["id"])
    assert approved_script["status"] == "approved"
    return script


def _queue_asset_jobs(client: TestClient, project_id: str) -> tuple[str, str]:
    audio_response = client.post(
        f"/api/projects/{project_id}/generate/audio",
        json={"voice_label": "Warm guide"},
    )
    visuals_response = client.post(f"/api/projects/{project_id}/generate/visuals", json={})
    assert audio_response.status_code == 201
    assert visuals_response.status_code == 201
    return audio_response.json()["id"], visuals_response.json()["id"]


def _run_browser_worker(
    *,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> int:
    return run_browser_jobs(
        settings=BrowserWorkerSettings(
            browser_provider_mode="dry_run",
            browser_max_jobs_per_run=10,
            playwright_download_root=tmp_path / "downloads",
        ),
        session_factory=session_factory,
    )


def _run_media_worker(
    *,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
    media_enable_ffmpeg_render: bool = False,
) -> int:
    return run_media_jobs(
        settings=MediaWorkerSettings(
            storage_root=tmp_path / "storage",
            downloads_root=tmp_path / "downloads",
            media_enable_ffmpeg_render=media_enable_ffmpeg_render,
        ),
        session_factory=session_factory,
    )


class SelectorFailureBrowserProvider(DryRunElevenLabsProvider):
    def wait_for_completion(self, job_id: str) -> None:
        raise RuntimeError("Selector #render-button not found")


class DownloadMismatchBrowserProvider(DryRunElevenLabsProvider):
    def collect_downloads(self, job_id: str) -> list[str]:
        first_path = self._download_root / f"{job_id}-unexpected-1.wav"
        second_path = self._download_root / f"{job_id}-unexpected-2.wav"
        first_path.write_bytes(b"unexpected-one")
        second_path.write_bytes(b"unexpected-two")
        return [str(first_path), str(second_path)]


def test_idea_approval_advances_project_to_script_pending_approval(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = api_client
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Advance project after idea approval",
        objective="Keep the project state aligned with the approved idea workflow",
    )

    ideas = _generate_ideas(client, project_id)
    approved_idea = _approve_idea(client, ideas[0]["id"])

    assert approved_idea["status"] == "approved"
    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "script_pending_approval"


def test_end_to_end_happy_path_reaches_publish_and_analytics(
    api_client: tuple[TestClient, sessionmaker[Session]],
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_ffmpeg_command(command: list[str]) -> None:
        Path(command[-1]).write_bytes(b"workflow mp4")

    monkeypatch.setattr("workers.media.runtime.run_ffmpeg_command", fake_run_ffmpeg_command)

    client, session_factory = api_client
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Happy path workflow",
        objective="Validate the full idea-to-publish pipeline",
    )

    ideas = _generate_ideas(
        client,
        project_id,
        source_feedback_notes="Lead with a strong founder pain point.",
    )
    assert len(ideas) >= 1
    approved_idea = _approve_idea(
        client,
        ideas[0]["id"],
        feedback_notes="This angle is strong enough to script.",
    )
    assert approved_idea["status"] == "approved"

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "script_pending_approval"

    script = _generate_script(
        client,
        project_id,
        source_feedback_notes="Keep scenes tight and specific.",
    )
    approved_script = _approve_script(client, script["id"])
    assert approved_script["status"] == "approved"

    _queue_asset_jobs(client, project_id)
    assert _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory) == 2

    approve_assets_response = client.post(
        f"/api/projects/{project_id}/assets/approve",
        json={"feedback_notes": "Assets are ready for rough cut."},
    )
    assert approve_assets_response.status_code == 200

    rough_cut_queue_response = client.post(f"/api/projects/{project_id}/compose/rough-cut")
    assert rough_cut_queue_response.status_code == 201
    assert (
        _run_media_worker(
            tmp_path=tmp_path,
            session_factory=session_factory,
            media_enable_ffmpeg_render=True,
        )
        == 1
    )

    final_export_queue_response = client.post(f"/api/projects/{project_id}/compose/final-export")
    assert final_export_queue_response.status_code == 201
    final_export_job_id = final_export_queue_response.json()["id"]
    assert (
        _run_media_worker(
            tmp_path=tmp_path,
            session_factory=session_factory,
            media_enable_ffmpeg_render=True,
        )
        == 1
    )

    final_export_detail_response = client.get(f"/api/jobs/{final_export_job_id}")
    assert final_export_detail_response.status_code == 200
    assert final_export_detail_response.json()["job"]["state"] == "completed"

    approve_final_video_response = client.post(
        f"/api/projects/{project_id}/final-video/approve",
        json={"feedback_notes": "Approved for publish prep."},
    )
    assert approve_final_video_response.status_code == 200

    prepare_publish_job_response = client.post(
        f"/api/projects/{project_id}/publish-jobs/prepare",
        json={
            "platform": "youtube_shorts",
            "title": "CreatorOS full workflow validation",
            "description": "Dry-run workflow completed end to end.",
            "hashtags": ["#CreatorOS", "#Workflow"],
            "idempotency_key": "happy-path-publish-job",
        },
    )
    assert prepare_publish_job_response.status_code == 201
    publish_job_id = prepare_publish_job_response.json()["id"]

    approve_publish_job_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/approve", json={}
    )
    assert approve_publish_job_response.status_code == 200

    queue_publish_job_response = client.post(f"/api/publish-jobs/{publish_job_id}/queue")
    assert queue_publish_job_response.status_code == 200
    publish_handoff_job_id = queue_publish_job_response.json()["id"]

    processed_publish_jobs = run_publisher_jobs(
        settings=PublisherWorkerSettings(storage_root=tmp_path / "storage"),
        session_factory=session_factory,
    )
    assert processed_publish_jobs == 1

    publish_handoff_detail_response = client.get(f"/api/jobs/{publish_handoff_job_id}")
    assert publish_handoff_detail_response.status_code == 200
    assert publish_handoff_detail_response.json()["job"]["state"] == "waiting_external"

    mark_published_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/mark-published",
        json={"external_post_id": "creatoros-happy-path-post"},
    )
    assert mark_published_response.status_code == 200
    assert mark_published_response.json()["status"] == "published"

    publish_handoff_completed_response = client.get(f"/api/jobs/{publish_handoff_job_id}")
    assert publish_handoff_completed_response.status_code == 200
    assert publish_handoff_completed_response.json()["job"]["state"] == "completed"

    queue_analytics_response = client.post(
        f"/api/publish-jobs/{publish_job_id}/analytics/queue",
        json={
            "views": 4800,
            "likes": 370,
            "comments": 41,
            "shares": 26,
            "saves": 18,
            "avg_view_duration": 24.2,
        },
    )
    assert queue_analytics_response.status_code == 201
    analytics_job_id = queue_analytics_response.json()["id"]

    processed_analytics_jobs = run_analytics_jobs(
        settings=AnalyticsWorkerSettings(),
        session_factory=session_factory,
    )
    assert processed_analytics_jobs == 1

    analytics_job_detail_response = client.get(f"/api/jobs/{analytics_job_id}")
    assert analytics_job_detail_response.status_code == 200
    assert analytics_job_detail_response.json()["job"]["state"] == "completed"

    project_analytics_response = client.get(f"/api/projects/{project_id}/analytics")
    assert project_analytics_response.status_code == 200
    analytics_payload = project_analytics_response.json()
    assert len(analytics_payload["snapshots"]) == 1
    assert analytics_payload["snapshots"][0]["views"] == 4800
    assert len(analytics_payload["insights"]) >= 1

    final_project_response = client.get(f"/api/projects/{project_id}")
    assert final_project_response.status_code == 200
    assert final_project_response.json()["status"] == "published"


def test_rejected_idea_and_script_regeneration_preserve_feedback_and_resume_workflow(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = api_client
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Rejected approval recovery",
        objective="Validate idea and script regeneration after rejection",
    )

    initial_ideas = _generate_ideas(client, project_id)
    rejected_idea = _reject_idea(
        client,
        initial_ideas[0]["id"],
        feedback_notes="Too broad. Make it more concrete for solo founders.",
    )
    assert rejected_idea["status"] == "rejected"

    second_idea_batch = _generate_ideas(
        client,
        project_id,
        source_feedback_notes="Too broad. Make it more concrete for solo founders.",
    )
    assert all(
        idea["source_feedback_notes"] == "Too broad. Make it more concrete for solo founders."
        for idea in second_idea_batch
    )

    approved_idea = _approve_idea(
        client,
        second_idea_batch[0]["id"],
        feedback_notes="This one is focused enough to script.",
    )
    assert approved_idea["status"] == "approved"

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "script_pending_approval"

    first_script = _generate_script(client, project_id)
    rejected_script = _reject_script(
        client,
        first_script["id"],
        feedback_notes="Hook is okay, but the middle needs a sharper proof point.",
    )
    assert rejected_script["status"] == "rejected"

    regenerated_script = _generate_script(
        client,
        project_id,
        source_feedback_notes="Hook is okay, but the middle needs a sharper proof point.",
    )
    assert regenerated_script["version_number"] == 2
    assert (
        regenerated_script["source_feedback_notes"]
        == "Hook is okay, but the middle needs a sharper proof point."
    )

    approved_script = _approve_script(client, regenerated_script["id"])
    assert approved_script["status"] == "approved"

    approvals_response = client.get(f"/api/projects/{project_id}/approvals")
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()
    assert any(
        approval["stage"] == "idea"
        and approval["decision"] == "rejected"
        and approval["feedback_notes"] == "Too broad. Make it more concrete for solo founders."
        for approval in approvals
    )
    assert any(
        approval["stage"] == "script"
        and approval["decision"] == "rejected"
        and approval["feedback_notes"]
        == "Hook is okay, but the middle needs a sharper proof point."
        for approval in approvals
    )


def test_end_to_end_selector_failure_marks_browser_job_failed(
    api_client: tuple[TestClient, sessionmaker[Session]],
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    client, session_factory = api_client
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Selector failure workflow",
        objective="Keep browser job failures visible when provider selectors break",
    )
    _create_approved_script_for_tests(client, project_id)

    audio_job_id, _visual_job_id = _queue_asset_jobs(client, project_id)
    monkeypatch.setattr(
        "workers.browser.runtime._get_provider",
        lambda settings, job, selector_bundle=None, session_descriptor=None: (
            SelectorFailureBrowserProvider(tmp_path / "downloads")
            if str(job.id) == audio_job_id
            else DryRunFlowProvider(tmp_path / "downloads")
        ),
    )

    assert _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory) == 2

    audio_job_detail_response = client.get(f"/api/jobs/{audio_job_id}")
    assert audio_job_detail_response.status_code == 200
    audio_job_detail = audio_job_detail_response.json()
    assert audio_job_detail["job"]["state"] == "failed"
    assert any(
        log["event_type"] == "browser_failure_artifacts_captured"
        for log in audio_job_detail["job_logs"]
    )

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "asset_generation"


def test_end_to_end_download_mismatch_quarantines_provider_outputs(
    api_client: tuple[TestClient, sessionmaker[Session]],
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    client, session_factory = api_client
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="Download mismatch workflow",
        objective="Quarantine browser outputs when download counts do not match the plan",
    )
    _create_approved_script_for_tests(client, project_id)

    audio_job_id, _visual_job_id = _queue_asset_jobs(client, project_id)
    monkeypatch.setattr(
        "workers.browser.runtime._get_provider",
        lambda settings, job, selector_bundle=None, session_descriptor=None: (
            DownloadMismatchBrowserProvider(tmp_path / "downloads")
            if str(job.id) == audio_job_id
            else DryRunFlowProvider(tmp_path / "downloads")
        ),
    )

    assert _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory) == 2

    audio_job_detail_response = client.get(f"/api/jobs/{audio_job_id}")
    assert audio_job_detail_response.status_code == 200
    audio_job_detail = audio_job_detail_response.json()
    assert audio_job_detail["job"]["state"] == "failed"
    assert any(log["event_type"] == "downloads_quarantined" for log in audio_job_detail["job_logs"])

    quarantine_root = tmp_path / "storage" / "projects" / project_id / "quarantine"
    quarantined_files = [path for path in quarantine_root.glob("**/*") if path.is_file()]
    assert len(quarantined_files) >= 2


def test_end_to_end_ffmpeg_failure_keeps_project_blocked_before_final_review(
    api_client: tuple[TestClient, sessionmaker[Session]],
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def failing_run_ffmpeg_command(_command: list[str]) -> None:
        raise RuntimeError("Encoder crashed unexpectedly during render.")

    monkeypatch.setattr("workers.media.runtime.run_ffmpeg_command", failing_run_ffmpeg_command)

    client, session_factory = api_client
    brand_profile_id = _create_brand_profile_for_tests(client)
    project_id = _create_project_for_tests(
        client,
        brand_profile_id,
        title="FFmpeg failure workflow",
        objective="Keep final-review gates closed when media rendering fails",
    )
    _create_approved_script_for_tests(client, project_id)
    _queue_asset_jobs(client, project_id)
    assert _run_browser_worker(tmp_path=tmp_path, session_factory=session_factory) == 2

    approve_assets_response = client.post(f"/api/projects/{project_id}/assets/approve", json={})
    assert approve_assets_response.status_code == 200

    rough_cut_queue_response = client.post(f"/api/projects/{project_id}/compose/rough-cut")
    assert rough_cut_queue_response.status_code == 201
    rough_cut_job_id = rough_cut_queue_response.json()["id"]

    assert (
        _run_media_worker(
            tmp_path=tmp_path,
            session_factory=session_factory,
            media_enable_ffmpeg_render=True,
        )
        == 1
    )

    rough_cut_job_detail_response = client.get(f"/api/jobs/{rough_cut_job_id}")
    assert rough_cut_job_detail_response.status_code == 200
    rough_cut_job_detail = rough_cut_job_detail_response.json()
    assert rough_cut_job_detail["job"]["state"] == "failed"
    assert (
        "Encoder crashed unexpectedly during render."
        in rough_cut_job_detail["job"]["error_message"]
    )

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["status"] == "asset_pending_approval"
