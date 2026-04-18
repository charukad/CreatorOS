from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.db.session import get_db
from apps.api.schemas.projects import ProjectCreate, ProjectResponse, ProjectUpdate
from apps.api.services.projects import (
    create_project,
    get_owned_brand_profile,
    get_project,
    list_projects,
    update_project,
)
from apps.api.services.users import get_or_create_default_user

router = APIRouter(prefix="/projects", tags=["projects"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_route(payload: ProjectCreate, db: DbSession) -> ProjectResponse:
    user = get_or_create_default_user(db)
    brand_profile = get_owned_brand_profile(db, user, payload.brand_profile_id)
    if brand_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found",
        )

    project = create_project(db, user, brand_profile, payload)
    return ProjectResponse.model_validate(project)


@router.get("", response_model=list[ProjectResponse])
def list_projects_route(db: DbSession) -> list[ProjectResponse]:
    user = get_or_create_default_user(db)
    projects = list_projects(db, user)
    return [ProjectResponse.model_validate(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_route(project_id: UUID, db: DbSession) -> ProjectResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project_route(
    project_id: UUID,
    payload: ProjectUpdate,
    db: DbSession,
) -> ProjectResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    brand_profile = None
    if payload.brand_profile_id is not None:
        brand_profile = get_owned_brand_profile(db, user, payload.brand_profile_id)
        if brand_profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Brand profile not found",
            )

    updated_project = update_project(db, project, payload, brand_profile=brand_profile)
    return ProjectResponse.model_validate(updated_project)
