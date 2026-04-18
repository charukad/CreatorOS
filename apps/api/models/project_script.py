from uuid import UUID

from sqlalchemy import JSON, Enum, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from apps.api.schemas.enums import ScriptStatus


class ProjectScript(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scripts"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id"), index=True, nullable=False
    )
    content_idea_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("content_ideas.id"),
        index=True,
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ScriptStatus] = mapped_column(
        Enum(
            ScriptStatus,
            name="script_status",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        default=ScriptStatus.DRAFT,
        nullable=False,
    )
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    cta: Mapped[str] = mapped_column(Text, nullable=False)
    full_script: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    title_options: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    hashtags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    source_feedback_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="scripts")
    project = relationship("Project", back_populates="scripts")
    content_idea = relationship("ContentIdea", back_populates="scripts")
    scenes = relationship(
        "Scene",
        back_populates="script",
        cascade="all, delete-orphan",
        order_by="Scene.scene_order",
    )
