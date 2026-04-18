from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BrandProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "brand_profiles"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True, nullable=False)
    channel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    niche: Mapped[str] = mapped_column(String(255), nullable=False)
    target_audience: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str] = mapped_column(String(255), nullable=False)
    hook_style: Mapped[str] = mapped_column(String(255), nullable=False)
    cta_style: Mapped[str] = mapped_column(String(255), nullable=False)
    visual_style: Mapped[str] = mapped_column(String(255), nullable=False)
    posting_preferences_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    user = relationship("User", back_populates="brand_profiles")
    projects = relationship("Project", back_populates="brand_profile")
