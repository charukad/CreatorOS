from typing import Protocol

from apps.api.models.asset import Asset
from apps.api.models.project import Project
from apps.api.models.publish_job import PublishJob


class PublishAdapter(Protocol):
    name: str

    def build_handoff_package(
        self,
        *,
        project: Project,
        publish_job: PublishJob,
        final_asset: Asset,
        thumbnail_asset: Asset | None,
    ) -> dict[str, object]: ...


class ManualPublishHandoffAdapter:
    name = "manual_publish_handoff"

    def build_handoff_package(
        self,
        *,
        project: Project,
        publish_job: PublishJob,
        final_asset: Asset,
        thumbnail_asset: Asset | None,
    ) -> dict[str, object]:
        platform_settings = publish_job.metadata_json.get("platform_settings", {})
        if not isinstance(platform_settings, dict):
            platform_settings = {}

        return {
            "adapter_name": self.name,
            "safety_notice": (
                "This handoff does not publish automatically. Upload manually, then return to "
                "CreatorOS and mark the publish job as published."
            ),
            "project": {
                "id": str(project.id),
                "title": project.title,
                "target_platform": project.target_platform,
            },
            "publish_job": {
                "id": str(publish_job.id),
                "platform": publish_job.platform,
                "status": publish_job.status.value,
                "title": publish_job.title,
                "description": publish_job.description,
                "hashtags": publish_job.hashtags_json,
                "scheduled_for": (
                    publish_job.scheduled_for.isoformat()
                    if publish_job.scheduled_for is not None
                    else None
                ),
                "platform_settings": platform_settings,
            },
            "assets": {
                "final_asset_id": str(final_asset.id),
                "final_asset_path": final_asset.file_path,
                "thumbnail_asset_id": str(thumbnail_asset.id) if thumbnail_asset else None,
                "thumbnail_asset_path": thumbnail_asset.file_path if thumbnail_asset else None,
            },
            "manual_steps": [
                "Open the target platform account.",
                "Upload the final video asset.",
                "Apply the title, description, hashtags, thumbnail, and platform settings.",
                "Confirm the post or scheduled publish on the platform.",
                "Copy the platform post ID or URL back into CreatorOS.",
            ],
        }
