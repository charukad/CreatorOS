from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.brand_profile import BrandProfile
from apps.api.models.user import User
from apps.api.schemas.brand_profiles import BrandProfileCreate, BrandProfileUpdate


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
