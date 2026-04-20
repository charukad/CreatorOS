from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.db.session import get_db
from apps.api.schemas.brand_profiles import (
    BrandProfileCreate,
    BrandProfileReadinessResponse,
    BrandProfileResponse,
    BrandProfileUpdate,
    BrandPromptContextResponse,
)
from apps.api.services.brand_profiles import (
    build_brand_prompt_context,
    create_brand_profile,
    evaluate_brand_profile_readiness,
    get_brand_profile,
    list_brand_profiles,
    update_brand_profile,
)
from apps.api.services.users import get_or_create_default_user

router = APIRouter(prefix="/brand-profiles", tags=["brand-profiles"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=BrandProfileResponse, status_code=status.HTTP_201_CREATED)
def create_brand_profile_route(
    payload: BrandProfileCreate,
    db: DbSession,
) -> BrandProfileResponse:
    user = get_or_create_default_user(db)
    brand_profile = create_brand_profile(db, user, payload)
    return BrandProfileResponse.model_validate(brand_profile)


@router.get("", response_model=list[BrandProfileResponse])
def list_brand_profiles_route(db: DbSession) -> list[BrandProfileResponse]:
    user = get_or_create_default_user(db)
    brand_profiles = list_brand_profiles(db, user)
    return [BrandProfileResponse.model_validate(brand_profile) for brand_profile in brand_profiles]


@router.get("/{brand_profile_id}", response_model=BrandProfileResponse)
def get_brand_profile_route(brand_profile_id: UUID, db: DbSession) -> BrandProfileResponse:
    user = get_or_create_default_user(db)
    brand_profile = get_brand_profile(db, user, brand_profile_id)
    if brand_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand profile not found")

    return BrandProfileResponse.model_validate(brand_profile)


@router.get("/{brand_profile_id}/readiness", response_model=BrandProfileReadinessResponse)
def get_brand_profile_readiness_route(
    brand_profile_id: UUID,
    db: DbSession,
) -> BrandProfileReadinessResponse:
    user = get_or_create_default_user(db)
    brand_profile = get_brand_profile(db, user, brand_profile_id)
    if brand_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand profile not found")

    return evaluate_brand_profile_readiness(brand_profile)


@router.get("/{brand_profile_id}/prompt-context", response_model=BrandPromptContextResponse)
def get_brand_profile_prompt_context_route(
    brand_profile_id: UUID,
    db: DbSession,
) -> BrandPromptContextResponse:
    user = get_or_create_default_user(db)
    brand_profile = get_brand_profile(db, user, brand_profile_id)
    if brand_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand profile not found")

    return build_brand_prompt_context(brand_profile)


@router.patch("/{brand_profile_id}", response_model=BrandProfileResponse)
def update_brand_profile_route(
    brand_profile_id: UUID,
    payload: BrandProfileUpdate,
    db: DbSession,
) -> BrandProfileResponse:
    user = get_or_create_default_user(db)
    brand_profile = get_brand_profile(db, user, brand_profile_id)
    if brand_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand profile not found")

    updated_brand_profile = update_brand_profile(db, brand_profile, payload)
    return BrandProfileResponse.model_validate(updated_brand_profile)
