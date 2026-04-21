from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_events"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id"),
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(String(24), default="info", nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    user = relationship("User", back_populates="project_events")
    project = relationship("Project", back_populates="project_events")
