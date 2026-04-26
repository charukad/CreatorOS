import re
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload, selectinload

from apps.api.models.brand_profile import BrandProfile
from apps.api.models.content_idea import ContentIdea
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.models.scene import Scene
from apps.api.models.user import User
from apps.api.schemas.content_workflow import (
    ScenePromptPackResponse,
    SceneUpdate,
    ScriptGenerateRequest,
    ScriptPromptPackResponse,
)
from apps.api.schemas.enums import (
    ApprovalDecision,
    ApprovalStage,
    ApprovalTargetType,
    ContentIdeaStatus,
    ProjectStatus,
    ScriptStatus,
)
from apps.api.services.approvals import create_approval_record
from apps.api.services.assets import (
    can_enter_asset_review,
    has_approved_asset_review,
    has_ready_rough_cut,
)
from apps.api.services.brand_profiles import build_brand_prompt_context
from apps.api.services.learning_context import summarize_analytics_learning_context


def list_project_ideas(db: Session, project: Project) -> list[ContentIdea]:
    statement = (
        select(ContentIdea)
        .where(ContentIdea.project_id == project.id)
        .order_by(desc(ContentIdea.score), desc(ContentIdea.created_at))
    )
    return list(db.scalars(statement))


def get_content_idea(db: Session, user: User, idea_id: UUID) -> ContentIdea | None:
    statement = select(ContentIdea).where(ContentIdea.id == idea_id, ContentIdea.user_id == user.id)
    return db.scalar(statement)


def get_approved_content_idea(db: Session, project: Project) -> ContentIdea | None:
    statement = (
        select(ContentIdea)
        .where(
            ContentIdea.project_id == project.id,
            ContentIdea.status == ContentIdeaStatus.APPROVED,
        )
        .order_by(desc(ContentIdea.updated_at), desc(ContentIdea.created_at))
    )
    return db.scalar(statement)


def get_current_script(db: Session, project: Project) -> ProjectScript | None:
    statement = (
        select(ProjectScript)
        .options(selectinload(ProjectScript.scenes))
        .where(ProjectScript.project_id == project.id)
        .order_by(desc(ProjectScript.version_number), desc(ProjectScript.created_at))
    )
    return db.scalar(statement)


def get_project_script(db: Session, user: User, script_id: UUID) -> ProjectScript | None:
    statement = (
        select(ProjectScript)
        .options(selectinload(ProjectScript.scenes))
        .where(ProjectScript.id == script_id, ProjectScript.user_id == user.id)
    )
    return db.scalar(statement)


def get_scene(db: Session, user: User, scene_id: UUID) -> Scene | None:
    statement = (
        select(Scene)
        .options(joinedload(Scene.script))
        .join(ProjectScript, Scene.script_id == ProjectScript.id)
        .where(Scene.id == scene_id, ProjectScript.user_id == user.id)
    )
    return db.scalar(statement)


def generate_content_ideas(
    db: Session,
    user: User,
    project: Project,
    brand_profile: BrandProfile,
    *,
    idea_research_context: dict[str, object] | None = None,
    source_feedback_notes: str | None = None,
    analytics_learning_context: dict[str, object] | None = None,
) -> list[ContentIdea]:
    if project.status not in {ProjectStatus.DRAFT, ProjectStatus.IDEA_PENDING_APPROVAL}:
        raise ValueError(
            "Ideas can only be generated while the project is in draft or idea approval."
        )

    generated_ideas = [
        ContentIdea(
            user_id=user.id,
            project_id=project.id,
            topic=str(idea["topic"]),
            suggested_title=idea["suggested_title"],
            hook=idea["hook"],
            angle=idea["angle"],
            rationale=idea["rationale"],
            score=idea["score"],
            source_feedback_notes=source_feedback_notes,
        )
        for idea in _build_idea_candidates(
            project,
            brand_profile,
            source_feedback_notes,
            idea_research_context=idea_research_context,
            analytics_learning_context=analytics_learning_context,
        )
    ]

    project.status = ProjectStatus.IDEA_PENDING_APPROVAL
    db.add(project)
    db.add_all(generated_ideas)
    db.commit()

    for idea in generated_ideas:
        db.refresh(idea)

    return generated_ideas


def approve_content_idea(
    db: Session,
    user: User,
    project: Project,
    idea: ContentIdea,
    feedback_notes: str | None = None,
) -> ContentIdea:
    if idea.project_id != project.id:
        raise ValueError("The selected idea does not belong to this project.")

    if project.status != ProjectStatus.IDEA_PENDING_APPROVAL:
        raise ValueError("Ideas can only be approved while the project is in idea approval.")

    if idea.status == ContentIdeaStatus.APPROVED:
        raise ValueError("This idea is already approved.")

    ideas = list_project_ideas(db, project)
    for existing_idea in ideas:
        if existing_idea.id == idea.id:
            existing_idea.status = ContentIdeaStatus.APPROVED
            existing_idea.feedback_notes = feedback_notes
        elif existing_idea.status != ContentIdeaStatus.REJECTED:
            existing_idea.status = ContentIdeaStatus.REJECTED

        db.add(existing_idea)

    project.status = ProjectStatus.SCRIPT_PENDING_APPROVAL
    db.add(project)
    create_approval_record(
        db,
        user=user,
        project=project,
        target_type=ApprovalTargetType.CONTENT_IDEA,
        target_id=idea.id,
        stage=ApprovalStage.IDEA,
        decision=ApprovalDecision.APPROVED,
        feedback_notes=feedback_notes,
    )
    db.commit()
    db.refresh(idea)
    return idea


def reject_content_idea(
    db: Session,
    user: User,
    project: Project,
    idea: ContentIdea,
    feedback_notes: str | None = None,
) -> ContentIdea:
    if idea.project_id != project.id:
        raise ValueError("The selected idea does not belong to this project.")

    if project.status != ProjectStatus.IDEA_PENDING_APPROVAL:
        raise ValueError("Ideas can only be rejected while the project is in idea approval.")

    if idea.status == ContentIdeaStatus.REJECTED:
        raise ValueError("This idea is already rejected.")

    if idea.status == ContentIdeaStatus.APPROVED:
        raise ValueError("Approved ideas cannot be rejected after selection.")

    idea.status = ContentIdeaStatus.REJECTED
    idea.feedback_notes = feedback_notes
    db.add(idea)
    create_approval_record(
        db,
        user=user,
        project=project,
        target_type=ApprovalTargetType.CONTENT_IDEA,
        target_id=idea.id,
        stage=ApprovalStage.IDEA,
        decision=ApprovalDecision.REJECTED,
        feedback_notes=feedback_notes,
    )
    db.commit()
    db.refresh(idea)
    return idea


def generate_project_script(
    db: Session,
    user: User,
    project: Project,
    approved_idea: ContentIdea,
    brand_profile: BrandProfile,
    payload: ScriptGenerateRequest,
    analytics_learning_context: dict[str, object] | None = None,
) -> ProjectScript:
    if approved_idea.project_id != project.id:
        raise ValueError("The approved idea does not belong to this project.")

    if approved_idea.status != ContentIdeaStatus.APPROVED:
        raise ValueError("A script can only be generated from an approved idea.")

    if project.status not in {
        ProjectStatus.IDEA_PENDING_APPROVAL,
        ProjectStatus.SCRIPT_PENDING_APPROVAL,
    }:
        raise ValueError(
            "Scripts can only be generated while the project is in "
            "idea approval or script approval."
        )

    current_script = get_current_script(db, project)
    next_version_number = 1 if current_script is None else current_script.version_number + 1

    if current_script is not None and current_script.status != ScriptStatus.SUPERSEDED:
        current_script.status = ScriptStatus.SUPERSEDED
        db.add(current_script)

    hook, body, cta, caption, title_options, hashtags, scenes = _build_script_package(
        project=project,
        brand_profile=brand_profile,
        approved_idea=approved_idea,
        analytics_learning_context=analytics_learning_context,
    )
    full_script = "\n\n".join([hook, body, cta])
    estimated_duration_seconds = sum(scene["estimated_duration_seconds"] for scene in scenes)

    script = ProjectScript(
        user_id=user.id,
        project_id=project.id,
        content_idea_id=approved_idea.id,
        version_number=next_version_number,
        status=ScriptStatus.DRAFT,
        hook=hook,
        body=body,
        cta=cta,
        full_script=full_script,
        caption=caption,
        title_options=title_options,
        hashtags=hashtags,
        estimated_duration_seconds=estimated_duration_seconds,
        source_feedback_notes=payload.source_feedback_notes,
    )
    db.add(script)
    db.flush()

    for scene_data in scenes:
        db.add(
            Scene(
                script_id=script.id,
                scene_order=scene_data["scene_order"],
                title=scene_data["title"],
                narration_text=scene_data["narration_text"],
                overlay_text=scene_data["overlay_text"],
                image_prompt=scene_data["image_prompt"],
                video_prompt=scene_data["video_prompt"],
                estimated_duration_seconds=scene_data["estimated_duration_seconds"],
                notes=scene_data["notes"],
            )
        )

    project.status = ProjectStatus.SCRIPT_PENDING_APPROVAL
    db.add(project)
    db.commit()

    refreshed_script = get_current_script(db, project)
    if refreshed_script is None:
        raise RuntimeError("Script generation completed but no script was found afterwards.")

    return refreshed_script


def approve_project_script(
    db: Session,
    user: User,
    project: Project,
    script: ProjectScript,
    feedback_notes: str | None = None,
) -> ProjectScript:
    current_script = get_current_script(db, project)
    if current_script is None or current_script.id != script.id:
        raise ValueError("Only the current script version can be approved.")

    if project.status != ProjectStatus.SCRIPT_PENDING_APPROVAL:
        raise ValueError("Scripts can only be approved while the project is in script approval.")

    if script.status == ScriptStatus.APPROVED:
        raise ValueError("This script is already approved.")

    if script.status == ScriptStatus.SUPERSEDED:
        raise ValueError("Superseded scripts cannot be approved.")

    script.status = ScriptStatus.APPROVED
    db.add(script)
    create_approval_record(
        db,
        user=user,
        project=project,
        target_type=ApprovalTargetType.SCRIPT,
        target_id=script.id,
        stage=ApprovalStage.SCRIPT,
        decision=ApprovalDecision.APPROVED,
        feedback_notes=feedback_notes,
    )
    db.commit()
    db.refresh(script)
    return script


def reject_project_script(
    db: Session,
    user: User,
    project: Project,
    script: ProjectScript,
    feedback_notes: str | None = None,
) -> ProjectScript:
    current_script = get_current_script(db, project)
    if current_script is None or current_script.id != script.id:
        raise ValueError("Only the current script version can be rejected.")

    if project.status != ProjectStatus.SCRIPT_PENDING_APPROVAL:
        raise ValueError("Scripts can only be rejected while the project is in script approval.")

    if script.status == ScriptStatus.REJECTED:
        raise ValueError("This script is already rejected.")

    if script.status == ScriptStatus.SUPERSEDED:
        raise ValueError("Superseded scripts cannot be rejected.")

    script.status = ScriptStatus.REJECTED
    db.add(script)
    create_approval_record(
        db,
        user=user,
        project=project,
        target_type=ApprovalTargetType.SCRIPT,
        target_id=script.id,
        stage=ApprovalStage.SCRIPT,
        decision=ApprovalDecision.REJECTED,
        feedback_notes=feedback_notes,
    )
    db.commit()
    db.refresh(script)
    return script


def update_scene(
    db: Session,
    *,
    project: Project,
    script: ProjectScript,
    scene: Scene,
    payload: SceneUpdate,
) -> Scene:
    _ensure_scene_plan_is_editable(db, project=project, script=script)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(scene, field, value)

    _sync_script_duration(script)
    _touch_script(script)
    db.add(scene)
    db.add(script)
    db.commit()
    db.refresh(scene)
    return scene


def reorder_script_scenes(
    db: Session,
    *,
    project: Project,
    script: ProjectScript,
    scene_ids: Sequence[UUID],
) -> ProjectScript:
    _ensure_scene_plan_is_editable(db, project=project, script=script)

    existing_scenes = {scene.id: scene for scene in script.scenes}
    requested_scene_ids = list(scene_ids)

    if (
        len(requested_scene_ids) != len(existing_scenes)
        or len(set(requested_scene_ids)) != len(requested_scene_ids)
        or set(requested_scene_ids) != set(existing_scenes)
    ):
        raise ValueError("Scene reorder must include every current scene exactly once.")

    for scene_order, scene_id in enumerate(requested_scene_ids, start=1):
        scene = existing_scenes[scene_id]
        scene.scene_order = scene_order
        db.add(scene)

    _sync_script_duration(script)
    _touch_script(script)
    db.add(script)
    db.commit()
    db.expire(script, ["scenes"])
    db.refresh(script)
    validate_script_scene_plan(script)
    return script


def validate_script_scene_plan(script: ProjectScript) -> list[Scene]:
    scenes = sorted(script.scenes, key=lambda scene: scene.scene_order)
    if not scenes:
        raise ValueError("A script must include at least one scene.")

    expected_scene_orders = list(range(1, len(scenes) + 1))
    actual_scene_orders = [scene.scene_order for scene in scenes]
    if actual_scene_orders != expected_scene_orders:
        raise ValueError("Script scenes must use contiguous scene_order values starting at 1.")

    if any(scene.estimated_duration_seconds < 1 for scene in scenes):
        raise ValueError("Script scenes must use positive estimated durations.")

    return scenes


def build_script_prompt_pack(
    *,
    project: Project,
    brand_profile: BrandProfile,
    approved_idea: ContentIdea,
    script: ProjectScript,
    analytics_learning_context: dict[str, object] | None = None,
) -> ScriptPromptPackResponse:
    brand_context = build_brand_prompt_context(brand_profile)
    learning_context = analytics_learning_context or _empty_analytics_learning_context(
        brand_profile=brand_profile,
        project=project,
    )
    learning_focus = summarize_analytics_learning_context(learning_context)
    narration_direction = (
        f"Read in a {brand_profile.tone.lower()} tone for {brand_profile.target_audience.lower()}. "
        f"Keep the pace suitable for {project.target_platform.replace('_', ' ')}."
    )
    if learning_focus:
        narration_direction = f"{narration_direction} Apply this learning focus: {learning_focus}"

    scenes = [
        ScenePromptPackResponse(
            scene_id=scene.id,
            scene_order=scene.scene_order,
            title=scene.title,
            estimated_duration_seconds=scene.estimated_duration_seconds,
            overlay_text=scene.overlay_text,
            narration_input=scene.narration_text,
            narration_direction=narration_direction,
            image_generation_prompt=(
                f"{brand_profile.visual_style}. {scene.image_prompt} Overlay guidance: "
                f"{scene.overlay_text}. Channel: {brand_profile.channel_name}."
                + (f" Learning focus: {learning_focus}" if learning_focus else "")
            ),
            video_generation_prompt=(
                f"{brand_profile.visual_style}. {scene.video_prompt} "
                f"Objective: {project.objective}. "
                f"Platform: {project.target_platform.replace('_', ' ')}."
                + (f" Learning focus: {learning_focus}" if learning_focus else "")
            ),
            notes=scene.notes,
        )
        for scene in validate_script_scene_plan(script)
    ]

    return ScriptPromptPackResponse(
        script_id=script.id,
        project_id=project.id,
        brand_profile_id=brand_profile.id,
        brand_context=brand_context.context_json,
        analytics_learning_context=learning_context,
        channel_name=brand_profile.channel_name,
        target_platform=project.target_platform,
        objective=project.objective,
        script_status=script.status,
        version_number=script.version_number,
        source_idea_title=approved_idea.suggested_title,
        caption=script.caption,
        hashtags=script.hashtags,
        title_options=script.title_options,
        scenes=scenes,
    )


def validate_project_transition_prerequisites(
    db: Session,
    project: Project,
    target_status: ProjectStatus,
) -> None:
    current_script = get_current_script(db, project)

    if target_status == ProjectStatus.SCRIPT_PENDING_APPROVAL and current_script is None:
        raise ValueError(
            f"Project cannot transition to '{target_status.value}' without a generated script."
        )

    if target_status == ProjectStatus.ASSET_GENERATION:
        if current_script is None:
            raise ValueError(
                f"Project cannot transition to '{target_status.value}' without a generated script."
            )
        if current_script.status != ScriptStatus.APPROVED:
            raise ValueError(
                "Project cannot transition to 'asset_generation' until the current script "
                "is approved."
            )

    if target_status == ProjectStatus.ASSET_PENDING_APPROVAL:
        if current_script is None:
            raise ValueError(
                f"Project cannot transition to '{target_status.value}' without a generated script."
            )
        if not can_enter_asset_review(db, project, current_script):
            raise ValueError(
                "Project cannot transition to 'asset_pending_approval' until narration and "
                "scene assets are ready and no generation jobs are still active."
            )

    if target_status == ProjectStatus.ROUGH_CUT_READY:
        if current_script is None:
            raise ValueError(
                f"Project cannot transition to '{target_status.value}' without a generated script."
            )
        if not has_approved_asset_review(db, project, current_script):
            raise ValueError(
                "Project cannot transition to 'rough_cut_ready' until the current asset set "
                "has been explicitly approved."
            )
        if not has_ready_rough_cut(db, current_script):
            raise ValueError(
                "Project cannot transition to 'rough_cut_ready' until the media worker has "
                "created a rough-cut artifact for the current script."
            )

    if target_status == ProjectStatus.FINAL_PENDING_APPROVAL:
        if current_script is None:
            raise ValueError(
                f"Project cannot transition to '{target_status.value}' without a generated script."
            )
        from apps.api.services.publishing import get_latest_ready_final_review_asset

        if get_latest_ready_final_review_asset(db, current_script) is None:
            raise ValueError(
                "Project cannot transition to 'final_pending_approval' until a rough-cut "
                "or final-export artifact is ready for review."
            )

    if target_status == ProjectStatus.READY_TO_PUBLISH:
        if current_script is None:
            raise ValueError(
                f"Project cannot transition to '{target_status.value}' without a generated script."
            )
        from apps.api.services.publishing import (
            get_latest_ready_final_review_asset,
            has_final_video_approval,
        )

        final_asset = get_latest_ready_final_review_asset(db, current_script)
        if final_asset is None or not has_final_video_approval(db, project, final_asset):
            raise ValueError(
                "Project cannot transition to 'ready_to_publish' until the final video has "
                "explicit approval."
            )

    if target_status == ProjectStatus.SCHEDULED:
        from apps.api.services.publishing import has_scheduled_publish_job

        if not has_scheduled_publish_job(db, project):
            raise ValueError(
                "Project cannot transition to 'scheduled' until an approved publish job "
                "has been scheduled."
            )

    if target_status == ProjectStatus.PUBLISHED:
        from apps.api.services.publishing import has_published_publish_job

        if not has_published_publish_job(db, project):
            raise ValueError(
                "Project cannot transition to 'published' until a publish job has been "
                "marked as published."
            )


def _ensure_scene_plan_is_editable(
    db: Session,
    *,
    project: Project,
    script: ProjectScript,
) -> None:
    current_script = get_current_script(db, project)
    if current_script is None or current_script.id != script.id:
        raise ValueError("Only scenes on the current script can be edited.")

    if project.status != ProjectStatus.SCRIPT_PENDING_APPROVAL:
        raise ValueError("Scenes can only be edited while the project is in script approval.")

    if script.status not in {ScriptStatus.DRAFT, ScriptStatus.REJECTED}:
        raise ValueError("Scenes can only be edited while the current script is draft or rejected.")


def _sync_script_duration(script: ProjectScript) -> None:
    script.estimated_duration_seconds = sum(
        scene.estimated_duration_seconds for scene in script.scenes
    )


def _touch_script(script: ProjectScript) -> None:
    script.updated_at = datetime.now(UTC)


def _build_idea_candidates(
    project: Project,
    brand_profile: BrandProfile,
    source_feedback_notes: str | None = None,
    *,
    idea_research_context: dict[str, object] | None = None,
    analytics_learning_context: dict[str, object] | None = None,
) -> Sequence[dict[str, str | int]]:
    research_topics = _research_topics(
        idea_research_context,
        fallback=_normalize_phrase(project.title),
    )
    research_summary = _normalize_phrase(
        str(idea_research_context.get("summary", "")) if idea_research_context else ""
    )
    trend_observations = _research_lines(idea_research_context, "trend_observations")
    competitor_angles = _research_lines(idea_research_context, "competitor_angles")
    posting_strategies = _research_lines(idea_research_context, "posting_strategies")
    objective = _normalize_phrase(project.objective)
    audience = _normalize_phrase(brand_profile.target_audience)
    tone = _normalize_phrase(brand_profile.tone)
    hook_style = _normalize_phrase(brand_profile.hook_style)
    cta_style = _normalize_phrase(brand_profile.cta_style)
    visual_style = _normalize_phrase(brand_profile.visual_style)
    platform = _normalize_phrase(project.target_platform)
    notes = _normalize_phrase(project.notes or "Keep the advice concrete and immediately usable.")
    revision_note = _normalize_phrase(source_feedback_notes or "")
    revision_guidance = f" Responds to revision note: {revision_note}." if revision_note else ""
    learning_focus = summarize_analytics_learning_context(analytics_learning_context)
    learning_guidance = (
        f" Uses recent performance learning: {learning_focus}" if learning_focus else ""
    )

    question_open = "?" if "question" in hook_style.lower() else ""
    audience_short = audience.split(",")[0]
    revised_prefix = "Revised: " if revision_note else ""
    learned_prefix = "Analytics-backed: " if learning_focus and not revised_prefix else ""
    research_prefix = (
        "Research-led: " if research_summary and not revised_prefix and not learned_prefix else ""
    )
    primary_topic = research_topics[0]
    secondary_topic = research_topics[1] if len(research_topics) > 1 else primary_topic
    tertiary_topic = research_topics[2] if len(research_topics) > 2 else primary_topic
    first_trend = trend_observations[0] if trend_observations else ""
    first_competitor = competitor_angles[0] if competitor_angles else ""
    first_strategy = posting_strategies[0] if posting_strategies else ""
    research_guidance = f" Research summary: {research_summary}." if research_summary else ""
    research_rationale_suffix = (
        f" Uses research guidance from the latest snapshot.{research_guidance}"
        if research_summary
        else ""
    )

    return [
        {
            "topic": primary_topic,
            "suggested_title": (
                f"{revised_prefix}{learned_prefix}{research_prefix}3 ways "
                f"{audience_short} can apply "
                f"{primary_topic} this week"
            ),
            "hook": (
                f"What if {primary_topic.lower()} could save {audience_short.lower()} "
                "hours this week"
                f"{question_open}"
            ),
            "angle": (
                f"Turn {objective.lower()} into a practical three-step playbook tailored to "
                f"{audience_short.lower()} and focused on {primary_topic.lower()}."
                + (f" Use the revision focus: {revision_note}." if revision_note else "")
                + (f" Use this research observation: {first_trend}." if first_trend else "")
                + learning_guidance
            ),
            "rationale": (
                f"Fits the {tone.lower()} tone, gives {platform} viewers a fast payoff, and leaves "
                f"room for a {cta_style.lower()} ending.{revision_guidance}{learning_guidance}"
                f"{research_rationale_suffix}"
            ),
            "score": 94 if learning_focus else 91,
        },
        {
            "topic": secondary_topic,
            "suggested_title": (
                f"{revised_prefix}The biggest {secondary_topic} mistake creators still make"
            ),
            "hook": (
                f"Most creators overcomplicate {secondary_topic.lower()} before they ever get "
                "results."
            ),
            "angle": (
                "Lead with the common mistake, then reframe the workflow into a lighter, more "
                "repeatable process."
                + (f" Fold in this requested direction: {revision_note}." if revision_note else "")
                + (
                    f" Differentiate with this competitor gap: {first_competitor}."
                    if first_competitor
                    else ""
                )
                + learning_guidance
            ),
            "rationale": (
                f"Good for {platform} because it creates tension quickly and matches the brand's "
                f"{hook_style.lower()} hook instinct.{revision_guidance}{learning_guidance}"
                f"{research_rationale_suffix}"
            ),
            "score": 90 if learning_focus else 87,
        },
        {
            "topic": tertiary_topic,
            "suggested_title": (f"{revised_prefix}My {tertiary_topic} workflow in 4 fast shots"),
            "hook": (
                f"Here is the {visual_style.lower()} version of how I approach "
                f"{tertiary_topic.lower()}."
            ),
            "angle": (
                "Show the workflow as a short behind-the-scenes sequence with on-screen proof "
                "and simple narration."
                + (f" Shape the proof around: {revision_note}." if revision_note else "")
                + (f" Apply this posting strategy: {first_strategy}." if first_strategy else "")
                + learning_guidance
            ),
            "rationale": (
                f"Plays well with {visual_style.lower()} visuals and supports the project note: "
                f"{notes}.{revision_guidance}{learning_guidance}"
                f"{research_rationale_suffix}"
            ),
            "score": 87 if learning_focus else 84,
        },
    ]


def _research_topics(
    idea_research_context: dict[str, object] | None,
    *,
    fallback: str,
) -> list[str]:
    if not idea_research_context:
        return [fallback, fallback, fallback]

    raw_topics = idea_research_context.get("recommended_topics")
    if not isinstance(raw_topics, list):
        return [fallback, fallback, fallback]

    topics = [_normalize_phrase(str(topic)) for topic in raw_topics if str(topic).strip()]
    if not topics:
        return [fallback, fallback, fallback]
    while len(topics) < 3:
        topics.append(topics[-1])
    return topics[:3]


def _research_lines(
    idea_research_context: dict[str, object] | None,
    key: str,
) -> list[str]:
    if not idea_research_context:
        return []

    raw_value = idea_research_context.get(key)
    if not isinstance(raw_value, list):
        return []

    return [_normalize_phrase(str(item)) for item in raw_value if str(item).strip()]


def _build_script_package(
    project: Project,
    brand_profile: BrandProfile,
    approved_idea: ContentIdea,
    analytics_learning_context: dict[str, object] | None = None,
) -> tuple[str, str, str, str, list[str], list[str], list[dict[str, str | int | None]]]:
    topic = _normalize_phrase(project.title)
    objective = _normalize_phrase(project.objective)
    audience = _normalize_phrase(brand_profile.target_audience)
    tone = _normalize_phrase(brand_profile.tone)
    cta_style = _normalize_phrase(brand_profile.cta_style)
    visual_style = _normalize_phrase(brand_profile.visual_style)
    platform = _normalize_phrase(project.target_platform)
    learning_focus = summarize_analytics_learning_context(analytics_learning_context)
    learning_sentence = f"Recent analytics learning: {learning_focus}" if learning_focus else None

    hook = approved_idea.hook
    body_lines = [
        (
            f"{audience} usually hear that {objective.lower()} needs a huge system, but the real "
            f"unlock is choosing one outcome and one repeatable format."
        ),
        (
            f"So I frame {topic.lower()} around a single promise, show one proof point, and end "
            f"with a next step people can copy today."
        ),
        *([learning_sentence] if learning_sentence else []),
        (
            f"That keeps the delivery {tone.lower()}, clear for {platform}, and easy to support "
            f"with {visual_style.lower()} visuals."
        ),
    ]
    body = " ".join(body_lines)
    cta = (
        f"Close by {cta_style.lower()} and invite viewers to test the first step before the "
        f"day ends."
    )

    title_options = [
        approved_idea.suggested_title,
        f"{topic}: the short playbook",
        f"{topic} for {brand_profile.niche}",
    ]
    if learning_focus:
        title_options = [*title_options, f"Analytics-backed {topic}"]

    caption = (
        f"{approved_idea.angle} Built for {platform} with a {tone.lower()} delivery and "
        f"{visual_style.lower()} visuals."
        + (f" Learning focus: {learning_focus}" if learning_focus else "")
    )
    hashtags = _build_hashtags(
        [project.target_platform, brand_profile.niche, project.title, "creatoros"]
    )
    scenes = [
        {
            "scene_order": 1,
            "title": "Hook",
            "narration_text": hook,
            "overlay_text": "The fast promise",
            "image_prompt": (
                f"High-contrast cover frame showing {topic.lower()} with bold text and "
                f"{visual_style.lower()} styling."
            ),
            "video_prompt": (
                f"Start with a punchy first-person clip that teases {topic.lower()} in under six "
                f"seconds using {visual_style.lower()} visuals."
            ),
            "estimated_duration_seconds": 6,
            "notes": _append_learning_note(
                "Start with immediate motion and large overlay text.",
                learning_focus,
            ),
        },
        {
            "scene_order": 2,
            "title": "Problem",
            "narration_text": body_lines[0],
            "overlay_text": "Why most people stall",
            "image_prompt": (
                f"Visualize the frustration of trying to scale {objective.lower()} without a "
                f"repeatable process."
            ),
            "video_prompt": (
                f"Show a cluttered workflow, then contrast it with a cleaner setup geared toward "
                f"{audience.lower()}."
            ),
            "estimated_duration_seconds": 8,
            "notes": _append_learning_note(
                "Use a before-and-after beat to make the pain point obvious.",
                learning_focus,
            ),
        },
        {
            "scene_order": 3,
            "title": "Framework",
            "narration_text": f"{body_lines[1]} {body_lines[2]}",
            "overlay_text": "Promise, proof, next step",
            "image_prompt": (
                f"Storyboard a three-step framework for {topic.lower()} with clean annotations and "
                f"{visual_style.lower()} references."
            ),
            "video_prompt": (
                f"Create a three-panel explanation sequence that highlights promise, proof, and "
                f"next step for {platform} viewers."
            ),
            "estimated_duration_seconds": 12,
            "notes": _append_learning_note(
                "Keep the middle section paced but readable for short-form viewing.",
                learning_focus,
            ),
        },
        {
            "scene_order": 4,
            "title": "CTA",
            "narration_text": cta,
            "overlay_text": "Try it today",
            "image_prompt": (
                f"Clean outro frame that reinforces the next step and leaves room for a "
                f"{cta_style.lower()} CTA."
            ),
            "video_prompt": (
                f"End with a confident close-up and on-screen CTA that matches a {tone.lower()} "
                f"brand voice."
            ),
            "estimated_duration_seconds": 7,
            "notes": _append_learning_note(
                "Pause long enough for comments or follow action to feel natural.",
                learning_focus,
            ),
        },
    ]

    return hook, body, cta, caption, title_options, hashtags, scenes


def _empty_analytics_learning_context(
    *,
    brand_profile: BrandProfile,
    project: Project,
) -> dict[str, object]:
    return {
        "available": False,
        "brand_profile_id": str(brand_profile.id),
        "target_project_id": str(project.id),
        "source_count": 0,
        "guidance": [],
        "items": [],
    }


def _append_learning_note(note: str, learning_focus: str | None) -> str:
    if not learning_focus:
        return note

    return f"{note} Learning focus: {learning_focus}"


def _build_hashtags(values: Sequence[str]) -> list[str]:
    hashtags: list[str] = []
    for value in values:
        slug = re.sub(r"[^a-zA-Z0-9]+", " ", value).title().replace(" ", "")
        if not slug:
            continue

        hashtag = f"#{slug}"
        if hashtag not in hashtags:
            hashtags.append(hashtag)

    return hashtags[:5]


def _normalize_phrase(value: str) -> str:
    return " ".join(value.replace("_", " ").split()).strip()
