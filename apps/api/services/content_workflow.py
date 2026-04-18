import re
from collections.abc import Sequence
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
) -> list[ContentIdea]:
    if project.status not in {ProjectStatus.DRAFT, ProjectStatus.IDEA_PENDING_APPROVAL}:
        raise ValueError(
            "Ideas can only be generated while the project is in draft or idea approval."
        )

    generated_ideas = [
        ContentIdea(
            user_id=user.id,
            project_id=project.id,
            suggested_title=idea["suggested_title"],
            hook=idea["hook"],
            angle=idea["angle"],
            rationale=idea["rationale"],
            score=idea["score"],
        )
        for idea in _build_idea_candidates(project, brand_profile)
    ]

    project.status = ProjectStatus.IDEA_PENDING_APPROVAL
    db.add(project)
    db.add_all(generated_ideas)
    db.commit()

    return list_project_ideas(db, project)


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
    current_script = get_current_script(db, project)
    if current_script is None or current_script.id != script.id:
        raise ValueError("Only scenes on the current script can be edited.")

    if project.status != ProjectStatus.SCRIPT_PENDING_APPROVAL:
        raise ValueError("Scenes can only be edited while the project is in script approval.")

    if script.status not in {ScriptStatus.DRAFT, ScriptStatus.REJECTED}:
        raise ValueError("Scenes can only be edited while the current script is draft or rejected.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(scene, field, value)

    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene


def build_script_prompt_pack(
    *,
    project: Project,
    brand_profile: BrandProfile,
    approved_idea: ContentIdea,
    script: ProjectScript,
) -> ScriptPromptPackResponse:
    narration_direction = (
        f"Read in a {brand_profile.tone.lower()} tone for {brand_profile.target_audience.lower()}. "
        f"Keep the pace suitable for {project.target_platform.replace('_', ' ')}."
    )

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
            ),
            video_generation_prompt=(
                f"{brand_profile.visual_style}. {scene.video_prompt} "
                f"Objective: {project.objective}. "
                f"Platform: {project.target_platform.replace('_', ' ')}."
            ),
            notes=scene.notes,
        )
        for scene in script.scenes
    ]

    return ScriptPromptPackResponse(
        script_id=script.id,
        project_id=project.id,
        brand_profile_id=brand_profile.id,
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


def _build_idea_candidates(
    project: Project, brand_profile: BrandProfile
) -> Sequence[dict[str, str | int]]:
    topic = _normalize_phrase(project.title)
    objective = _normalize_phrase(project.objective)
    audience = _normalize_phrase(brand_profile.target_audience)
    tone = _normalize_phrase(brand_profile.tone)
    hook_style = _normalize_phrase(brand_profile.hook_style)
    cta_style = _normalize_phrase(brand_profile.cta_style)
    visual_style = _normalize_phrase(brand_profile.visual_style)
    platform = _normalize_phrase(project.target_platform)
    notes = _normalize_phrase(project.notes or "Keep the advice concrete and immediately usable.")

    question_open = "?" if "question" in hook_style.lower() else ""
    audience_short = audience.split(",")[0]

    return [
        {
            "suggested_title": f"3 ways {audience_short} can apply {topic} this week",
            "hook": (
                f"What if {topic.lower()} could save {audience_short.lower()} hours this week"
                f"{question_open}"
            ),
            "angle": (
                f"Turn {objective.lower()} into a practical three-step playbook tailored to "
                f"{audience_short.lower()}."
            ),
            "rationale": (
                f"Fits the {tone.lower()} tone, gives {platform} viewers a fast payoff, and leaves "
                f"room for a {cta_style.lower()} ending."
            ),
            "score": 91,
        },
        {
            "suggested_title": f"The biggest {topic} mistake creators still make",
            "hook": f"Most creators overcomplicate {topic.lower()} before they ever get results.",
            "angle": (
                "Lead with the common mistake, then reframe the workflow into a lighter, more "
                "repeatable process."
            ),
            "rationale": (
                f"Good for {platform} because it creates tension quickly and matches the brand's "
                f"{hook_style.lower()} hook instinct."
            ),
            "score": 87,
        },
        {
            "suggested_title": f"My {topic} workflow in 4 fast shots",
            "hook": (
                f"Here is the {visual_style.lower()} version of how I approach {topic.lower()}."
            ),
            "angle": (
                "Show the workflow as a short behind-the-scenes sequence with on-screen proof "
                "and simple narration."
            ),
            "rationale": (
                f"Plays well with {visual_style.lower()} visuals and supports the project note: "
                f"{notes}"
            ),
            "score": 84,
        },
    ]


def _build_script_package(
    project: Project,
    brand_profile: BrandProfile,
    approved_idea: ContentIdea,
) -> tuple[str, str, str, str, list[str], list[str], list[dict[str, str | int | None]]]:
    topic = _normalize_phrase(project.title)
    objective = _normalize_phrase(project.objective)
    audience = _normalize_phrase(brand_profile.target_audience)
    tone = _normalize_phrase(brand_profile.tone)
    cta_style = _normalize_phrase(brand_profile.cta_style)
    visual_style = _normalize_phrase(brand_profile.visual_style)
    platform = _normalize_phrase(project.target_platform)

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
    caption = (
        f"{approved_idea.angle} Built for {platform} with a {tone.lower()} delivery and "
        f"{visual_style.lower()} visuals."
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
            "notes": "Start with immediate motion and large overlay text.",
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
            "notes": "Use a before-and-after beat to make the pain point obvious.",
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
            "notes": "Keep the middle section paced but readable for short-form viewing.",
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
            "notes": "Pause long enough for comments or follow action to feel natural.",
        },
    ]

    return hook, body, cta, caption, title_options, hashtags, scenes


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
