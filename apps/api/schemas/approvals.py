from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.api.schemas.enums import ApprovalDecision, ApprovalStage, ApprovalTargetType


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    target_type: ApprovalTargetType
    target_id: UUID
    stage: ApprovalStage
    decision: ApprovalDecision
    feedback_notes: str | None
    created_at: datetime


class ApprovalDecisionRequest(BaseModel):
    feedback_notes: str | None = Field(default=None, max_length=5000)
