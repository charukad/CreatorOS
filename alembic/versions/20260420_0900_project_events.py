"""add project events

Revision ID: 20260420_0900
Revises: 20260419_0800
Create Date: 2026-04-20 09:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260420_0900"
down_revision = "20260419_0800"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("level", sa.String(length=24), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
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
    op.create_index(op.f("ix_project_events_event_type"), "project_events", ["event_type"])
    op.create_index(op.f("ix_project_events_project_id"), "project_events", ["project_id"])
    op.create_index(op.f("ix_project_events_user_id"), "project_events", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_project_events_user_id"), table_name="project_events")
    op.drop_index(op.f("ix_project_events_project_id"), table_name="project_events")
    op.drop_index(op.f("ix_project_events_event_type"), table_name="project_events")
    op.drop_table("project_events")
