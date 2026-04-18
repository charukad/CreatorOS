"""add content workflow tables

Revision ID: 20260418_2330
Revises: 20260418_1905
Create Date: 2026-04-18 23:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260418_2330"
down_revision = "20260418_1905"
branch_labels = None
depends_on = None


content_idea_status_enum = sa.Enum(
    "proposed",
    "approved",
    "rejected",
    name="content_idea_status",
    native_enum=False,
)

script_status_enum = sa.Enum(
    "draft",
    "approved",
    "rejected",
    "superseded",
    name="script_status",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "content_ideas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("suggested_title", sa.String(length=255), nullable=False),
        sa.Column("hook", sa.Text(), nullable=False),
        sa.Column("angle", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("status", content_idea_status_enum, nullable=False),
        sa.Column("feedback_notes", sa.Text(), nullable=True),
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
        op.f("ix_content_ideas_project_id"),
        "content_ideas",
        ["project_id"],
        unique=False,
    )
    op.create_index(op.f("ix_content_ideas_user_id"), "content_ideas", ["user_id"], unique=False)

    op.create_table(
        "scripts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("content_idea_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", script_status_enum, nullable=False),
        sa.Column("hook", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("cta", sa.Text(), nullable=False),
        sa.Column("full_script", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("title_options", sa.JSON(), nullable=False),
        sa.Column("hashtags", sa.JSON(), nullable=False),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("source_feedback_notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["content_idea_id"], ["content_ideas.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version_number", name="uq_scripts_project_version"),
    )
    op.create_index(
        op.f("ix_scripts_content_idea_id"), "scripts", ["content_idea_id"], unique=False
    )
    op.create_index(op.f("ix_scripts_project_id"), "scripts", ["project_id"], unique=False)
    op.create_index(op.f("ix_scripts_user_id"), "scripts", ["user_id"], unique=False)

    op.create_table(
        "scenes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("script_id", sa.Uuid(), nullable=False),
        sa.Column("scene_order", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("narration_text", sa.Text(), nullable=False),
        sa.Column("overlay_text", sa.Text(), nullable=False),
        sa.Column("image_prompt", sa.Text(), nullable=False),
        sa.Column("video_prompt", sa.Text(), nullable=False),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["script_id"], ["scripts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scenes_script_id"), "scenes", ["script_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scenes_script_id"), table_name="scenes")
    op.drop_table("scenes")
    op.drop_index(op.f("ix_scripts_user_id"), table_name="scripts")
    op.drop_index(op.f("ix_scripts_project_id"), table_name="scripts")
    op.drop_index(op.f("ix_scripts_content_idea_id"), table_name="scripts")
    op.drop_table("scripts")
    op.drop_index(op.f("ix_content_ideas_user_id"), table_name="content_ideas")
    op.drop_index(op.f("ix_content_ideas_project_id"), table_name="content_ideas")
    op.drop_table("content_ideas")
