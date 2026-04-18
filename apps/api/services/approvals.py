from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.approval import Approval
from apps.api.models.project import Project
from apps.api.models.user import User
from apps.api.schemas.enums import ApprovalDecision, ApprovalStage, ApprovalTargetType


def list_project_approvals(db: Session, project: Project) -> list[Approval]:
    statement = (
        select(Approval)
        .where(Approval.project_id == project.id)
        .order_by(desc(Approval.created_at))
    )
    return list(db.scalars(statement))


def create_approval_record(
    db: Session,
    *,
    user: User,
    project: Project,
    target_type: ApprovalTargetType,
    target_id: UUID,
    stage: ApprovalStage,
    decision: ApprovalDecision,
    feedback_notes: str | None,
) -> Approval:
    approval = Approval(
        user_id=user.id,
        project_id=project.id,
        target_type=target_type,
        target_id=target_id,
        stage=stage,
        decision=decision,
        feedback_notes=feedback_notes,
    )
    db.add(approval)
    db.flush()
    return approval
