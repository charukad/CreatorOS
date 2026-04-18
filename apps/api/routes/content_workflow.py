from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.db.session import get_db
from apps.api.schemas.approvals import ApprovalDecisionRequest, ApprovalResponse
from apps.api.schemas.content_workflow import (
    ContentIdeaResponse,
    IdeaApprovalRequest,
    ProjectScriptResponse,
    SceneResponse,
    SceneUpdate,
    ScriptGenerateRequest,
    ScriptPromptPackResponse,
)
from apps.api.services.approvals import list_project_approvals
from apps.api.services.content_workflow import (
    approve_content_idea,
    approve_project_script,
    build_script_prompt_pack,
    generate_content_ideas,
    generate_project_script,
    get_approved_content_idea,
    get_content_idea,
    get_current_script,
    get_project_script,
    get_scene,
    list_project_ideas,
    reject_content_idea,
    reject_project_script,
    update_scene,
)
from apps.api.services.projects import get_owned_brand_profile, get_project
from apps.api.services.users import get_or_create_default_user

router = APIRouter(tags=["content-workflow"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/projects/{project_id}/ideas", response_model=list[ContentIdeaResponse])
def list_project_ideas_route(project_id: UUID, db: DbSession) -> list[ContentIdeaResponse]:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    ideas = list_project_ideas(db, project)
    return [ContentIdeaResponse.model_validate(idea) for idea in ideas]


@router.get("/projects/{project_id}/approvals", response_model=list[ApprovalResponse])
def list_project_approvals_route(project_id: UUID, db: DbSession) -> list[ApprovalResponse]:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    approvals = list_project_approvals(db, project)
    return [ApprovalResponse.model_validate(approval) for approval in approvals]


@router.post(
    "/projects/{project_id}/ideas/generate",
    response_model=list[ContentIdeaResponse],
    status_code=status.HTTP_201_CREATED,
)
def generate_project_ideas_route(project_id: UUID, db: DbSession) -> list[ContentIdeaResponse]:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    brand_profile = get_owned_brand_profile(db, user, project.brand_profile_id)
    if brand_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found",
        )

    try:
        ideas = generate_content_ideas(db, user, project, brand_profile)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return [ContentIdeaResponse.model_validate(idea) for idea in ideas]


@router.post("/ideas/{idea_id}/approve", response_model=ContentIdeaResponse)
def approve_idea_route(
    idea_id: UUID,
    payload: IdeaApprovalRequest,
    db: DbSession,
) -> ContentIdeaResponse:
    user = get_or_create_default_user(db)
    idea = get_content_idea(db, user, idea_id)
    if idea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Idea not found")

    project = get_project(db, user, idea.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        approved_idea = approve_content_idea(db, user, project, idea, payload.feedback_notes)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ContentIdeaResponse.model_validate(approved_idea)


@router.post("/ideas/{idea_id}/reject", response_model=ContentIdeaResponse)
def reject_idea_route(
    idea_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> ContentIdeaResponse:
    user = get_or_create_default_user(db)
    idea = get_content_idea(db, user, idea_id)
    if idea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Idea not found")

    project = get_project(db, user, idea.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        rejected_idea = reject_content_idea(db, user, project, idea, payload.feedback_notes)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ContentIdeaResponse.model_validate(rejected_idea)


@router.get(
    "/projects/{project_id}/scripts/current",
    response_model=ProjectScriptResponse | None,
)
def get_current_project_script_route(
    project_id: UUID,
    db: DbSession,
) -> ProjectScriptResponse | None:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    script = get_current_script(db, project)
    return ProjectScriptResponse.model_validate(script) if script is not None else None


@router.get("/scripts/{script_id}/scenes", response_model=list[SceneResponse])
def list_script_scenes_route(script_id: UUID, db: DbSession) -> list[SceneResponse]:
    user = get_or_create_default_user(db)
    script = get_project_script(db, user, script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    return [SceneResponse.model_validate(scene) for scene in script.scenes]


@router.get("/scripts/{script_id}/prompt-pack", response_model=ScriptPromptPackResponse)
def get_script_prompt_pack_route(script_id: UUID, db: DbSession) -> ScriptPromptPackResponse:
    user = get_or_create_default_user(db)
    script = get_project_script(db, user, script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    project = get_project(db, user, script.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    brand_profile = get_owned_brand_profile(db, user, project.brand_profile_id)
    if brand_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found",
        )

    source_idea = get_content_idea(db, user, script.content_idea_id)
    if source_idea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source idea not found")

    return build_script_prompt_pack(
        project=project,
        brand_profile=brand_profile,
        approved_idea=source_idea,
        script=script,
    )


@router.post(
    "/projects/{project_id}/scripts/generate",
    response_model=ProjectScriptResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_project_script_route(
    project_id: UUID,
    payload: ScriptGenerateRequest,
    db: DbSession,
) -> ProjectScriptResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    brand_profile = get_owned_brand_profile(db, user, project.brand_profile_id)
    if brand_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found",
        )

    approved_idea = get_approved_content_idea(db, project)
    if approved_idea is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approve an idea before generating a script.",
        )

    try:
        script = generate_project_script(db, user, project, approved_idea, brand_profile, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ProjectScriptResponse.model_validate(script)


@router.post("/scripts/{script_id}/approve", response_model=ProjectScriptResponse)
def approve_script_route(
    script_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> ProjectScriptResponse:
    user = get_or_create_default_user(db)
    script = get_project_script(db, user, script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    project = get_project(db, user, script.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        approved_script = approve_project_script(db, user, project, script, payload.feedback_notes)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ProjectScriptResponse.model_validate(approved_script)


@router.post("/scripts/{script_id}/reject", response_model=ProjectScriptResponse)
def reject_script_route(
    script_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> ProjectScriptResponse:
    user = get_or_create_default_user(db)
    script = get_project_script(db, user, script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    project = get_project(db, user, script.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        rejected_script = reject_project_script(db, user, project, script, payload.feedback_notes)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ProjectScriptResponse.model_validate(rejected_script)


@router.patch("/scenes/{scene_id}", response_model=SceneResponse)
def update_scene_route(
    scene_id: UUID,
    payload: SceneUpdate,
    db: DbSession,
) -> SceneResponse:
    user = get_or_create_default_user(db)
    scene = get_scene(db, user, scene_id)
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")

    script = get_project_script(db, user, scene.script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    project = get_project(db, user, script.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        updated_scene = update_scene(
            db,
            project=project,
            script=script,
            scene=scene,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return SceneResponse.model_validate(updated_scene)
