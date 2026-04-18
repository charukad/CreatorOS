# CreatorOS Project Overview

## Summary
CreatorOS is a personal AI content operating system for planning, generating, editing, approving, publishing, and learning from social media content. It is built around Codex as the orchestration brain, browser automation for subscription-only web tools, a local media assembly pipeline, and a human-in-the-loop approval model.

## Product Goals
- Reduce manual effort for content production.
- Reuse subscriptions the user already has.
- Keep quality high via staged approvals.
- Create a repeatable asset pipeline.
- Learn from analytics to improve future content.

## Supported Content Workflow
1. User defines channel/brand profile.
2. System generates content ideas.
3. User approves an idea.
4. System writes script, hooks, titles, and scene plan.
5. User approves script.
6. Browser worker uses ElevenLabs and Flow through the web UI.
7. Download manager organizes generated assets.
8. Media worker builds a rough cut.
9. User approves or requests regeneration.
10. System prepares platform-specific metadata and schedule.
11. User approves publishing.
12. System uploads/schedules and later syncs analytics.

## Why This Project Uses Browser Automation
The user already pays for subscription-based tools and wants to avoid separate API costs when possible. Therefore, CreatorOS is designed as a personal-use automation system that can operate through web interfaces via Playwright when API usage is not desirable.

## Product Constraints
- Personal use in v1
- Human approval before publish
- Browser automation may be fragile
- Must support retries and manual overrides
- Asset generation tools may change UI over time

## Key Modules
- Brand Brain
- Research Agent
- Idea Engine
- Script Engine
- Approval Engine
- Browser Worker
- Download Manager
- Media Composer
- Publishing Engine
- Analytics Engine
- Learning Engine

## Success Criteria
- Create one complete short-form video from idea to export without manual editing.
- Persist all intermediate artifacts.
- Allow step-by-step approvals and regenerations.
- Support multiple scene clips and automated final assembly.
- Produce useful analytics summaries and improvement suggestions.
