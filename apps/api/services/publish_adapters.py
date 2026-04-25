PUBLISH_ADAPTER_FALLBACK_NAME = "manual_publish_handoff"

_PUBLISH_ADAPTER_ALIASES = {
    "facebook": "facebook_manual_handoff",
    "facebook_reels": "facebook_manual_handoff",
    "facebook_video": "facebook_manual_handoff",
    "tiktok": "tiktok_manual_handoff",
    "youtube": "youtube_studio_manual_handoff",
    "youtube_shorts": "youtube_studio_manual_handoff",
}


def normalize_publish_platform(platform: str | None) -> str:
    if platform is None:
        return ""
    return platform.strip().lower().replace("-", "_").replace(" ", "_")


def resolve_publish_adapter_name(platform: str | None) -> str:
    normalized_platform = normalize_publish_platform(platform)
    return _PUBLISH_ADAPTER_ALIASES.get(normalized_platform, PUBLISH_ADAPTER_FALLBACK_NAME)
