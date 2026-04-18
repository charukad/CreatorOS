from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.db.session import get_db
from apps.api.schemas.content_workflow import (
    ContentIdeaResponse,
    IdeaApprovalRequest,
    ProjectScriptResponse,
    ScriptGenerateRequest,
)
from apps.api.services.content_workflow import (
    approve_content_idea,
    generate_content_ideas,
    generate_project_script,
    get_approved_content_idea,
    get_content_idea,
    get_current_script,
    list_project_ideas,
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
        approved_idea = approve_content_idea(db, project, idea, payload.feedback_notes)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ContentIdeaResponse.model_validate(approved_idea)


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
