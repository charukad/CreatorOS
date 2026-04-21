from __future__ import annotations

import apps.api.models  # noqa: F401
from apps.api.db.session import SessionLocal
from apps.api.models.brand_profile import BrandProfile
from apps.api.models.project import Project
from apps.api.schemas.enums import ProjectStatus
from apps.api.services.project_events import create_project_event
from apps.api.services.users import get_or_create_default_user
from sqlalchemy import select

DEMO_CHANNEL_NAME = "CreatorOS Demo Channel"
DEMO_PROJECT_TITLE = "Demo: 3 AI automations that save an hour"


def seed_demo_data() -> None:
    with SessionLocal() as session:
        user = get_or_create_default_user(session)
        brand_profile = session.scalar(
            select(BrandProfile).where(
                BrandProfile.user_id == user.id,
                BrandProfile.channel_name == DEMO_CHANNEL_NAME,
            )
        )
        if brand_profile is None:
            brand_profile = BrandProfile(
                user_id=user.id,
                channel_name=DEMO_CHANNEL_NAME,
                niche="AI productivity",
                target_audience="Solo creators validating repeatable content systems",
                tone="Practical, direct, and optimistic",
                hook_style="Specific pain-point question",
                cta_style="Invite viewers to comment with their bottleneck",
                visual_style="Clean screen-recording mixed with bold kinetic captions",
                posting_preferences_json={
                    "platforms": ["youtube_shorts", "tiktok"],
                    "default_duration_seconds": 45,
                },
            )
            session.add(brand_profile)
            session.flush()

        project = session.scalar(
            select(Project).where(
                Project.user_id == user.id,
                Project.title == DEMO_PROJECT_TITLE,
            )
        )
        if project is None:
            project = Project(
                user_id=user.id,
                brand_profile_id=brand_profile.id,
                title=DEMO_PROJECT_TITLE,
                target_platform="youtube_shorts",
                status=ProjectStatus.DRAFT,
                objective="Create a short-form demo project for local workflow validation.",
                notes="Seeded demo record. Safe to edit or archive during local QA.",
            )
            session.add(project)
            session.flush()
            create_project_event(
                session,
                project,
                event_type="demo_project_seeded",
                title="Demo project seeded",
                description="Local sample data was created for manual validation.",
                metadata={"script": "scripts/seed_demo.py"},
            )

        session.commit()
        print(f"Demo brand profile: {brand_profile.id}")
        print(f"Demo project: {project.id}")


if __name__ == "__main__":
    seed_demo_data()
