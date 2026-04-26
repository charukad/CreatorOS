from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from apps.api.schemas.enums import ContentIdeaStatus


class ContentIdea(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_ideas"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id"), index=True, nullable=False
    )
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_title: Mapped[str] = mapped_column(String(255), nullable=False)
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    angle: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    source_feedback_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ContentIdeaStatus] = mapped_column(
        Enum(
            ContentIdeaStatus,
            name="content_idea_status",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        default=ContentIdeaStatus.PROPOSED,
        nullable=False,
    )
    feedback_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="content_ideas")
    project = relationship("Project", back_populates="content_ideas")
    scripts = relationship("ProjectScript", back_populates="content_idea")
