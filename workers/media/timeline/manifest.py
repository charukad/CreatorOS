from datetime import UTC, datetime

from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript


def build_timeline_manifest(
    *,
    project: Project,
    script: ProjectScript,
    job: BackgroundJob,
    narration_asset: Asset,
    scene_assets: dict[str, Asset],
    subtitle_asset: Asset | None = None,
) -> dict[str, object]:
    cursor_seconds = 0
    timeline_scenes: list[dict[str, object]] = []

    for scene in script.scenes:
        scene_asset = scene_assets[str(scene.id)]
        start_seconds = cursor_seconds
        end_seconds = start_seconds + scene.estimated_duration_seconds
        cursor_seconds = end_seconds

        timeline_scenes.append(
            {
                "scene_id": str(scene.id),
                "scene_order": scene.scene_order,
                "title": scene.title,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration_seconds": scene.estimated_duration_seconds,
                "visual_asset_id": str(scene_asset.id),
                "visual_asset_path": scene_asset.file_path,
                "visual_asset_type": scene_asset.asset_type.value,
                "overlay_text": scene.overlay_text,
                "narration_text": scene.narration_text,
                "notes": scene.notes,
            }
        )

    manifest: dict[str, object] = {
        "manifest_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "job_id": str(job.id),
        "project_id": str(project.id),
        "project_title": project.title,
        "target_platform": project.target_platform,
        "script_id": str(script.id),
        "script_version": script.version_number,
        "total_duration_seconds": cursor_seconds,
        "narration_asset": {
            "asset_id": str(narration_asset.id),
            "file_path": narration_asset.file_path,
            "mime_type": narration_asset.mime_type,
            "duration_seconds": narration_asset.duration_seconds,
        },
        "scenes": timeline_scenes,
    }

    if subtitle_asset is not None:
        manifest["subtitle_asset"] = {
            "asset_id": str(subtitle_asset.id),
            "file_path": subtitle_asset.file_path,
            "mime_type": subtitle_asset.mime_type,
        }

    return manifest
