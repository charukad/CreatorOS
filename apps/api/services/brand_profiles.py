from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.brand_profile import BrandProfile
from apps.api.models.user import User
from apps.api.schemas.brand_profiles import (
    BrandProfileCreate,
    BrandProfileReadinessResponse,
    BrandProfileUpdate,
    BrandPromptContextResponse,
)

REQUIRED_BRAND_FIELDS = {
    "channel_name": "Channel name",
    "niche": "Niche",
    "target_audience": "Target audience",
    "tone": "Tone",
    "hook_style": "Hook style",
    "cta_style": "CTA style",
    "visual_style": "Visual style",
}


def create_brand_profile(db: Session, user: User, payload: BrandProfileCreate) -> BrandProfile:
    brand_profile = BrandProfile(user_id=user.id, **payload.model_dump())
    db.add(brand_profile)
    db.commit()
    db.refresh(brand_profile)
    return brand_profile


def list_brand_profiles(db: Session, user: User) -> list[BrandProfile]:
    statement = (
        select(BrandProfile)
        .where(BrandProfile.user_id == user.id)
        .order_by(desc(BrandProfile.updated_at), desc(BrandProfile.created_at))
    )
    return list(db.scalars(statement))


def get_brand_profile(db: Session, user: User, brand_profile_id: UUID) -> BrandProfile | None:
    statement = select(BrandProfile).where(
        BrandProfile.id == brand_profile_id,
        BrandProfile.user_id == user.id,
    )
    return db.scalar(statement)


def update_brand_profile(
    db: Session,
    brand_profile: BrandProfile,
    payload: BrandProfileUpdate,
) -> BrandProfile:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(brand_profile, field, value)

    db.add(brand_profile)
    db.commit()
    db.refresh(brand_profile)
    return brand_profile


def evaluate_brand_profile_readiness(brand_profile: BrandProfile) -> BrandProfileReadinessResponse:
    missing_fields = [
        label
        for field_name, label in REQUIRED_BRAND_FIELDS.items()
        if not str(getattr(brand_profile, field_name, "")).strip()
    ]
    warnings: list[str] = []
    posting_preferences = brand_profile.posting_preferences_json or {}
    platforms = posting_preferences.get("platforms")
    default_platform = posting_preferences.get("default_platform")
    output_defaults = posting_preferences.get("output_defaults")

    if not isinstance(platforms, list) or not platforms:
        warnings.append("Add at least one platform in posting_preferences_json.platforms.")
    elif default_platform is not None and default_platform not in platforms:
        warnings.append("Default platform should also appear in the platforms list.")

    if len(brand_profile.target_audience.strip()) < 20:
        warnings.append("Target audience is very short; add role, pain point, or skill level.")

    if len(brand_profile.visual_style.strip()) < 12:
        warnings.append("Visual style is short; add format, pacing, or visual references.")

    if output_defaults is not None and not isinstance(output_defaults, dict):
        warnings.append("posting_preferences_json.output_defaults should be an object.")

    recommended_next_steps = _brand_profile_next_steps(missing_fields, warnings)
    return BrandProfileReadinessResponse(
        brand_profile_id=brand_profile.id,
        is_ready=not missing_fields and not warnings,
        missing_fields=missing_fields,
        warnings=warnings,
        recommended_next_steps=recommended_next_steps,
    )


def build_brand_prompt_context(brand_profile: BrandProfile) -> BrandPromptContextResponse:
    readiness = evaluate_brand_profile_readiness(brand_profile)
    preferences = brand_profile.posting_preferences_json or {}
    platforms = preferences.get("platforms", [])
    output_defaults = preferences.get("output_defaults", {})
    context_json = {
        "brand_profile_id": str(brand_profile.id),
        "identity": {
            "channel_name": brand_profile.channel_name,
            "niche": brand_profile.niche,
        },
        "audience": {
            "target_audience": brand_profile.target_audience,
        },
        "voice": {
            "tone": brand_profile.tone,
            "hook_style": brand_profile.hook_style,
            "cta_style": brand_profile.cta_style,
        },
        "visuals": {
            "visual_style": brand_profile.visual_style,
        },
        "posting_preferences": preferences,
        "platforms": platforms if isinstance(platforms, list) else [],
        "output_defaults": output_defaults if isinstance(output_defaults, dict) else {},
        "operator_constraints": [
            "Keep all generated content aligned to this profile unless the user overrides it.",
            "Preserve approval checkpoints before downstream generation or publishing.",
            "Use posting preferences as defaults, not as irreversible requirements.",
        ],
    }
    context_markdown = "\n".join(
        [
            f"# Brand Context: {brand_profile.channel_name}",
            f"- Niche: {brand_profile.niche}",
            f"- Target audience: {brand_profile.target_audience}",
            f"- Tone: {brand_profile.tone}",
            f"- Hook style: {brand_profile.hook_style}",
            f"- CTA style: {brand_profile.cta_style}",
            f"- Visual style: {brand_profile.visual_style}",
            f"- Platforms: {', '.join(context_json['platforms']) or 'not specified'}",
            "",
            "## Output Defaults",
            _format_output_defaults(context_json["output_defaults"]),
        ]
    )
    return BrandPromptContextResponse(
        brand_profile_id=brand_profile.id,
        readiness=readiness,
        context_markdown=context_markdown,
        context_json=context_json,
    )


def _brand_profile_next_steps(
    missing_fields: list[str],
    warnings: list[str],
) -> list[str]:
    if missing_fields:
        return [f"Complete missing fields: {', '.join(missing_fields)}."]

    next_steps: list[str] = []
    for warning in warnings:
        if "platform" in warning.lower():
            next_steps.append("Add preferred platforms and an optional default platform.")
        elif "audience" in warning.lower():
            next_steps.append("Expand the audience with role, problem, and desired outcome.")
        elif "visual" in warning.lower():
            next_steps.append("Describe the visual format, references, pacing, and layout style.")

    if not next_steps:
        next_steps.append("Use this profile to generate project ideas and script prompt packs.")

    return list(dict.fromkeys(next_steps))


def _format_output_defaults(output_defaults: object) -> str:
    if not isinstance(output_defaults, dict) or not output_defaults:
        return "- No output defaults specified."

    return "\n".join(
        f"- {str(key).replace('_', ' ').title()}: {value}"
        for key, value in sorted(output_defaults.items())
    )
