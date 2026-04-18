"""initial core tables

Revision ID: 20260418_1905
Revises: None
Create Date: 2026-04-18 19:05:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260418_1905"
down_revision = None
branch_labels = None
depends_on = None


project_status_enum = sa.Enum(
    "draft",
    "idea_pending_approval",
    "script_pending_approval",
    "asset_generation",
    "asset_pending_approval",
    "rough_cut_ready",
    "final_pending_approval",
    "ready_to_publish",
    "scheduled",
    "published",
    "failed",
    "archived",
    name="project_status",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "brand_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel_name", sa.String(length=255), nullable=False),
        sa.Column("niche", sa.String(length=255), nullable=False),
        sa.Column("target_audience", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(length=255), nullable=False),
        sa.Column("hook_style", sa.String(length=255), nullable=False),
        sa.Column("cta_style", sa.String(length=255), nullable=False),
        sa.Column("visual_style", sa.String(length=255), nullable=False),
        sa.Column("posting_preferences_json", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_brand_profiles_user_id"), "brand_profiles", ["user_id"], unique=False)

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("brand_profile_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("target_platform", sa.String(length=100), nullable=False),
        sa.Column("status", project_status_enum, nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["brand_profile_id"], ["brand_profiles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_projects_brand_profile_id"),
        "projects",
        ["brand_profile_id"],
        unique=False,
    )
    op.create_index(op.f("ix_projects_user_id"), "projects", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_projects_user_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_brand_profile_id"), table_name="projects")
    op.drop_table("projects")
    op.drop_index(op.f("ix_brand_profiles_user_id"), table_name="brand_profiles")
    op.drop_table("brand_profiles")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
