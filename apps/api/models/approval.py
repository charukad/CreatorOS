from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, UUIDPrimaryKeyMixin
from apps.api.schemas.enums import ApprovalDecision, ApprovalStage, ApprovalTargetType


class Approval(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "approvals"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id"), index=True, nullable=False
    )
    target_type: Mapped[ApprovalTargetType] = mapped_column(
        Enum(
            ApprovalTargetType,
            name="approval_target_type",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        nullable=False,
    )
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    stage: Mapped[ApprovalStage] = mapped_column(
        Enum(
            ApprovalStage,
            name="approval_stage",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        nullable=False,
    )
    decision: Mapped[ApprovalDecision] = mapped_column(
        Enum(
            ApprovalDecision,
            name="approval_decision",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        nullable=False,
    )
    feedback_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="approvals")
    project = relationship("Project", back_populates="approvals")
