from dataclasses import dataclass
from typing import Any, Protocol

from apps.api.models.asset import Asset
from apps.api.models.project import Project
from apps.api.models.publish_job import PublishJob
from apps.api.services.publish_adapters import (
    PUBLISH_ADAPTER_FALLBACK_NAME,
    resolve_publish_adapter_name,
)


class PublishAdapter(Protocol):
    name: str
    label: str

    def build_handoff_package(
        self,
        *,
        project: Project,
        publish_job: PublishJob,
        final_asset: Asset,
        thumbnail_asset: Asset | None,
    ) -> dict[str, object]: ...


@dataclass(frozen=True)
class ManualPublishAdapter:
    name: str
    label: str
    platform_family: str
    supported_platforms: tuple[str, ...]
    upload_surface: str
    required_platform_settings: tuple[str, ...]
    recommended_platform_settings: dict[str, object]
    operator_notes: tuple[str, ...]
    manual_steps: tuple[str, ...]

    def build_handoff_package(
        self,
        *,
        project: Project,
        publish_job: PublishJob,
        final_asset: Asset,
        thumbnail_asset: Asset | None,
    ) -> dict[str, object]:
        platform_settings = _coerce_platform_settings(
            publish_job.metadata_json.get("platform_settings")
            if isinstance(publish_job.metadata_json, dict)
            else None
        )
        missing_recommended_settings = [
            key for key in self.recommended_platform_settings if key not in platform_settings
        ]

        return {
            "adapter_name": self.name,
            "adapter_label": self.label,
            "safety_notice": (
                "This handoff is platform-aware, but it still requires a manual upload. "
                "Complete the upload on the platform, then return to CreatorOS and mark the "
                "publish job as published."
            ),
            "adapter": {
                "name": self.name,
                "label": self.label,
                "mode": "manual_upload",
                "platform_family": self.platform_family,
                "upload_surface": self.upload_surface,
                "supported_platforms": list(self.supported_platforms),
            },
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
            "platform_guidance": {
                "required_platform_settings": list(self.required_platform_settings),
                "recommended_platform_settings": self.recommended_platform_settings,
                "missing_recommended_platform_settings": missing_recommended_settings,
                "operator_notes": list(self.operator_notes),
            },
            "manual_steps": list(self.manual_steps),
        }


YOUTUBE_STUDIO_MANUAL_ADAPTER = ManualPublishAdapter(
    name="youtube_studio_manual_handoff",
    label="YouTube Studio Manual Handoff",
    platform_family="youtube",
    supported_platforms=("youtube_shorts", "youtube"),
    upload_surface="YouTube Studio upload flow",
    required_platform_settings=("privacy",),
    recommended_platform_settings={
        "privacy": "private",
        "audience": "not_made_for_kids",
        "playlist_id": "optional",
    },
    operator_notes=(
        "Confirm the upload stays vertical and appears in the Shorts workflow.",
        "Review audience and visibility settings before going live.",
    ),
    manual_steps=(
        "Open YouTube Studio for the target channel.",
        "Upload the final video asset through the Shorts-compatible flow.",
        "Apply the title, description, hashtags, thumbnail, and playlist settings.",
        "Confirm privacy, audience, and schedule details before saving or publishing.",
        "Copy the resulting video ID or URL back into CreatorOS.",
    ),
)

TIKTOK_MANUAL_ADAPTER = ManualPublishAdapter(
    name="tiktok_manual_handoff",
    label="TikTok Manual Handoff",
    platform_family="tiktok",
    supported_platforms=("tiktok",),
    upload_surface="TikTok upload flow",
    required_platform_settings=("privacy",),
    recommended_platform_settings={
        "privacy": "followers",
        "allow_comments": True,
        "disclose_ai_generated": True,
    },
    operator_notes=(
        "Double-check music, duet/stitch, and disclosure settings before publishing.",
        "Review the caption length and hashtag mix for the current TikTok account.",
    ),
    manual_steps=(
        "Open the TikTok upload flow for the target account.",
        "Upload the final video asset.",
        "Apply the caption, hashtags, thumbnail frame, and privacy settings.",
        "Review comments, duet/stitch, disclosure, and scheduling options.",
        "Copy the published post URL or ID back into CreatorOS.",
    ),
)

FACEBOOK_MANUAL_ADAPTER = ManualPublishAdapter(
    name="facebook_manual_handoff",
    label="Facebook Manual Handoff",
    platform_family="facebook",
    supported_platforms=("facebook", "facebook_reels", "facebook_video"),
    upload_surface="Facebook Reels/Video composer",
    required_platform_settings=("privacy",),
    recommended_platform_settings={
        "privacy": "friends",
        "page_id": "optional",
        "crosspost_to_instagram": False,
    },
    operator_notes=(
        "Confirm whether the upload belongs on a page, profile, or Reels surface.",
        "Review privacy and cross-posting settings before saving or publishing.",
    ),
    manual_steps=(
        "Open the Facebook publishing surface for the target page or profile.",
        "Upload the final video asset to the Reel or video composer.",
        "Apply the title, description, hashtags, thumbnail, and page settings.",
        "Review privacy, schedule, and optional Instagram cross-post settings.",
        "Copy the resulting post URL or ID back into CreatorOS.",
    ),
)

GENERIC_MANUAL_ADAPTER = ManualPublishAdapter(
    name=PUBLISH_ADAPTER_FALLBACK_NAME,
    label="Generic Manual Publish Handoff",
    platform_family="generic",
    supported_platforms=(),
    upload_surface="Manual upload checklist",
    required_platform_settings=(),
    recommended_platform_settings={"visibility": "draft"},
    operator_notes=(
        "Review the target platform's upload requirements before posting.",
        "Use manual verification if the platform has extra compliance or disclosure fields.",
    ),
    manual_steps=(
        "Open the target platform account.",
        "Upload the final video asset.",
        "Apply the title, description, hashtags, thumbnail, and platform settings.",
        "Confirm the post or scheduled publish on the platform.",
        "Copy the platform post ID or URL back into CreatorOS.",
    ),
)

_PUBLISH_ADAPTERS: dict[str, PublishAdapter] = {
    adapter.name: adapter
    for adapter in (
        YOUTUBE_STUDIO_MANUAL_ADAPTER,
        TIKTOK_MANUAL_ADAPTER,
        FACEBOOK_MANUAL_ADAPTER,
        GENERIC_MANUAL_ADAPTER,
    )
}


def get_publish_adapter(*, platform: str, adapter_name: str | None = None) -> PublishAdapter:
    resolved_adapter_name = adapter_name or resolve_publish_adapter_name(platform)
    adapter = _PUBLISH_ADAPTERS.get(resolved_adapter_name)
    if adapter is None:
        raise ValueError(f"Unsupported publish adapter: {resolved_adapter_name}")
    return adapter


def _coerce_platform_settings(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}
