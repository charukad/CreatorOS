from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IdeaResearchSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "idea_research_snapshots"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id"),
        index=True,
        nullable=False,
    )
    focus_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_feedback_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    trend_observations_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    competitor_angles_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    posting_strategies_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    recommended_topics_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    user = relationship("User", back_populates="idea_research_snapshots")
    project = relationship("Project", back_populates="idea_research_snapshots")
