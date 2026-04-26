"""add idea research snapshots and idea topics

Revision ID: 20260424_1400
Revises: 20260420_1100
Create Date: 2026-04-24 14:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260424_1400"
down_revision = "20260420_1100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("content_ideas") as batch_op:
        batch_op.add_column(
            sa.Column("topic", sa.Text(), nullable=False, server_default="General")
        )

    op.create_table(
        "idea_research_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("focus_topic", sa.Text(), nullable=True),
        sa.Column("source_feedback_notes", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("trend_observations_json", sa.JSON(), nullable=False),
        sa.Column("competitor_angles_json", sa.JSON(), nullable=False),
        sa.Column("posting_strategies_json", sa.JSON(), nullable=False),
        sa.Column("recommended_topics_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_idea_research_snapshots_project_id"),
        "idea_research_snapshots",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_idea_research_snapshots_user_id"),
        "idea_research_snapshots",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_idea_research_snapshots_user_id"),
        table_name="idea_research_snapshots",
    )
    op.drop_index(
        op.f("ix_idea_research_snapshots_project_id"),
        table_name="idea_research_snapshots",
    )
    op.drop_table("idea_research_snapshots")

    with op.batch_alter_table("content_ideas") as batch_op:
        batch_op.drop_column("topic")
