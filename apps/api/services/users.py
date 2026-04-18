from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.core.config import get_settings
from apps.api.models.user import User


def get_or_create_default_user(db: Session) -> User:
    settings = get_settings()
    user = db.scalar(select(User).where(User.email == settings.default_user_email))
    if user is not None:
        return user

    user = User(email=settings.default_user_email, name=settings.default_user_name)
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_user = db.scalar(select(User).where(User.email == settings.default_user_email))
        if existing_user is None:
            raise
        return existing_user

    db.refresh(user)
    return user
