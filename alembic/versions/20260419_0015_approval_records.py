"""add approval records

Revision ID: 20260419_0015
Revises: 20260418_2330
Create Date: 2026-04-19 00:15:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260419_0015"
down_revision = "20260418_2330"
branch_labels = None
depends_on = None


approval_stage_enum = sa.Enum(
    "idea",
    "script",
    "assets",
    "final_video",
    "publish",
    name="approval_stage",
    native_enum=False,
)

approval_decision_enum = sa.Enum(
    "approved",
    "rejected",
    name="approval_decision",
    native_enum=False,
)

approval_target_type_enum = sa.Enum(
    "content_idea",
    "script",
    name="approval_target_type",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", approval_target_type_enum, nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("stage", approval_stage_enum, nullable=False),
        sa.Column("decision", approval_decision_enum, nullable=False),
        sa.Column("feedback_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_approvals_project_id"), "approvals", ["project_id"], unique=False)
    op.create_index(op.f("ix_approvals_target_id"), "approvals", ["target_id"], unique=False)
    op.create_index(op.f("ix_approvals_user_id"), "approvals", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_approvals_user_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_target_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_project_id"), table_name="approvals")
    op.drop_table("approvals")
