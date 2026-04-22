# AGENTS.md

## Project Purpose
CreatorOS is a personal-use AI social media automation system. It uses Codex as the orchestration brain, browser automation for subscription-based web tools, a local media pipeline for automated editing, approval checkpoints, scheduling, and analytics-driven improvement.

This repository is for a **personal internal tool**, not a multi-tenant SaaS in v1.

## Non-Negotiable Product Constraints
- Personal use only in v1.
- Keep the user as the final approver before publishing.
- Prefer official APIs where available and already covered by the user's subscriptions.
- Use browser automation only where API access is unavailable, impractical, or intentionally avoided for cost reasons.
- Design for resilience against changing web UIs.
- Never hardcode secrets.
- Every long-running step must be modeled as a background job.
- Every artifact must be traceable to a project, scene, and generation attempt.

## Architecture Summary
Main parts:
- `apps/web`: Next.js dashboard for setup, approvals, project management, previews, scheduling, analytics.
- `apps/api`: FastAPI backend for orchestration, persistence, auth/session, queues, approvals, analytics, metadata.
- `workers/browser`: Playwright workers for ElevenLabs/Flow/browser-assisted actions.
- `workers/media`: FFmpeg-based media assembly and export workers.
- `workers/publisher`: approval-safe publisher handoff worker for manual or future platform upload adapters.
- `packages/shared`: shared schemas, enums, helpers, types.
- `docs`: product, architecture, API, DB, queue, environment, and automation specs.

## Tech Choices
- Frontend: Next.js + TypeScript + Tailwind + shadcn/ui
- Backend: FastAPI + SQLAlchemy + Pydantic
- Database: PostgreSQL
- Queue/Cache: Redis
- Browser automation: Playwright
- Video pipeline: FFmpeg
- Storage: local file storage first; optional cloud storage later

## Primary Development Goals
1. Build a stable project-centric workflow.
2. Ship idea -> script -> approval -> asset generation -> rough cut -> approval -> publish flow.
3. Keep all pipeline stages resumable and retryable.
4. Build strong observability and logs for browser automation.
5. Keep the system modular enough to replace browser automation with APIs later.

## Repository Layout
- `apps/web/` UI application
- `apps/api/` backend API
- `workers/browser/` browser automation worker
- `workers/media/` media assembly worker
- `workers/publisher/` publish handoff and platform adapter worker
- `packages/shared/` shared contracts and utilities
- `docs/` docs for Codex and humans
- `storage/` generated files, downloads, previews, exports (gitignored)
- `scripts/` setup/dev scripts

## Working Style Instructions for Codex
- Make incremental, reviewable changes.
- Prefer small commits and clean module boundaries.
- Do not introduce hidden coupling across services.
- Avoid speculative abstractions until the core workflow works.
- Keep browser selectors centralized and versioned.
- Favor typed schemas and explicit enums for state transitions.
- Add logs around every external/tool interaction.
- Preserve manual override paths in all critical flows.

## Definition of Done
A task is done only when all of the following are true:
1. The code builds successfully.
2. Relevant lint/type checks pass.
3. Relevant automated tests pass.
4. The feature is reachable through the intended UI/API/worker path.
5. State changes are persisted correctly.
6. Errors are surfaced clearly in logs and UI.
7. The feature does not break the project workflow.
8. Documentation is updated if architecture or behavior changed.

## Commands Codex Should Use
These commands are the target interface and should exist in the repo:
- Install deps: `pnpm install` and `pip install -r requirements.txt`
- Start frontend: `pnpm --filter web dev`
- Start backend: `uvicorn apps.api.main:app --reload`
- Start browser worker: `python -m workers.browser.main`
- Start media worker: `python -m workers.media.main`
- Start publisher worker: `python -m workers.publisher.main`
- Lint frontend: `pnpm --filter web lint`
- Typecheck frontend: `pnpm --filter web typecheck`
- Backend tests: `pytest`
- Format Python: `ruff format .`
- Lint Python: `ruff check .`
- Database migrate: `alembic upgrade head`

## Guardrails
- Never commit real credentials, cookies, or browser profiles.
- Never assume browser automation selectors are stable; isolate them.
- Never skip approval checkpoints for publish actions.
- Never directly publish without an explicit approved publish job state.
- Never delete generated artifacts without a reversible retention policy.
- Never hide failures from the UI.

## Key Product Workflows
1. Onboarding and brand profile setup
2. Idea generation and approval
3. Script generation and approval
4. Browser-assisted asset generation
5. Asset review and rough cut generation
6. Final approval
7. Scheduling/publishing
8. Analytics sync and recommendations

## Testing Priorities
Highest priority tests:
- project lifecycle state transitions
- approval gating
- scene JSON validation
- download ingestion mapping
- media timeline assembly
- publish job safety checks
- browser worker retry/resume logic

## Preferred Implementation Order
1. Core schemas and DB
2. Project CRUD + state machine
3. Brand profile and settings
4. Idea/script generation flow
5. Approval system
6. Browser worker for ElevenLabs
7. Browser worker for Flow
8. Download manager
9. Media assembler
10. Publishing center
11. Analytics and learning loop

## Documentation Rule
If a change affects API shape, DB schema, queue payloads, state transitions, browser selectors, or storage paths, update the corresponding file in `docs/` in the same task.
