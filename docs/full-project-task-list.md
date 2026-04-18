# CreatorOS Full Project Task List

Use this file as the master implementation checklist for CreatorOS. Mark items as complete as work ships.

Legend:
- `[ ]` Not started
- `[x]` Completed
- `Manual check:` requires a human validation step before the phase should be considered done

## Phase 0 - Product Alignment and Repo Bootstrap

### Build tasks
- [ ] Confirm v1 scope is personal-use only and document any out-of-scope SaaS/multi-user ideas
- [ ] Finalize the intended monorepo layout for `apps/web`, `apps/api`, `workers/browser`, `workers/media`, `packages/shared`, `scripts`, `tests`, and `storage`
- [x] Create the missing repo skeleton folders from the planned structure
- [x] Add root workspace config for Node packages
- [x] Add Python project configuration and dependency management files
- [x] Add shared code quality tooling for TypeScript, Python, formatting, linting, and tests
- [x] Add `.gitignore` entries for env files, browser profiles, downloads, exports, caches, and generated media
- [x] Add example environment files for web, api, and workers
- [x] Add bootstrap scripts for local setup
- [x] Add a real `README.md` with setup steps, service startup commands, and architecture links
- [x] Add sample local storage directories expected by the app
- [x] Add a docs index linking all architecture and implementation documents

### Manual checks
- [ ] Manual check: the repo can be cloned on a clean machine and the setup instructions are understandable
- [ ] Manual check: no secret, cookie, browser profile, or generated artifact path is accidentally tracked by git

## Phase 1 - Shared Contracts, Enums, and Core Domain Model

### Build tasks
- [x] Create `packages/shared` for cross-service enums, types, schemas, and helpers
- [x] Define enums for project status, approval stage, asset type, provider type, job status, publish status, and analytics types
- [ ] Define shared identifiers and metadata contracts for project, scene, asset, generation attempt, approval, publish job, and analytics snapshot records
- [ ] Define queue payload schemas for every long-running job in `docs/queue-jobs.md`
- [ ] Define API request and response schemas for core resources in `docs/backend-api.md`
- [ ] Define scene manifest schema for media assembly
- [ ] Define prompt pack schema for idea, script, narration, and visual generation inputs
- [x] Define storage path helper contracts so all artifacts remain traceable to project, scene, and attempt
- [x] Add validation helpers for state transitions and approval gating
- [ ] Add test fixtures and factories for shared schema validation

### Manual checks
- [ ] Manual check: every artifact-related schema includes project, scene, and attempt traceability
- [ ] Manual check: shared contracts are usable from both Python and TypeScript without conflicting semantics

## Phase 2 - Database, Persistence, and Migrations

### Build tasks
- [x] Set up SQLAlchemy base models and migration tooling
- [ ] Create database models for `users`, `brand_profiles`, `projects`, `content_ideas`, `scripts`, `scenes`, `generation_attempts`, `assets`, `approvals`, `publish_jobs`, `analytics_snapshots`, `insights`, and `background_jobs`
- [x] Add explicit enum columns for workflow state where required
- [ ] Add foreign keys and indexes for common lookup paths
- [ ] Add created/updated timestamps consistently
- [ ] Add immutable versioning strategy for scripts and generation attempts
- [ ] Add audit-friendly approval history persistence
- [ ] Add checksum persistence for ingested files
- [ ] Add migration scripts for the full initial schema
- [ ] Add seed data helpers for local development
- [x] Add repository/service-layer persistence helpers for the main domain entities

### Manual checks
- [ ] Manual check: migrations can run from a clean database and produce the full schema successfully
- [ ] Manual check: the schema supports multiple attempts/regenerations without overwriting previous records

## Phase 3 - Backend App Foundation

### Build tasks
- [x] Create FastAPI app entrypoint and configuration loading
- [x] Add health and readiness endpoints
- [x] Add database session management and dependency injection
- [ ] Add Redis connection setup
- [x] Add structured logging and request correlation IDs
- [ ] Add global error model matching `docs/backend-api.md`
- [x] Add API router registration and versioned route structure
- [x] Add auth/session placeholder or personal-user auth implementation appropriate for v1
- [ ] Add background job submission helpers
- [x] Add service layer boundaries so routes stay thin
- [x] Add API test harness with database and Redis fixtures

### Manual checks
- [ ] Manual check: API startup failures are clear and actionable when env vars are missing
- [ ] Manual check: logs do not leak secrets or raw provider credentials

## Phase 4 - Web App Foundation and UX Shell

### Build tasks
- [ ] Create Next.js app structure with TypeScript, Tailwind, and shadcn/ui
- [ ] Add global layout, navigation, and project-level routing
- [x] Add API client layer and typed response handling
- [x] Add shared UI states for loading, empty, error, and retry flows
- [ ] Add notification/toast pattern for asynchronous job updates
- [ ] Add reusable cards, tables, status badges, forms, dialogs, and approval components
- [ ] Add application-wide status color mapping for project, asset, job, approval, and publish states
- [ ] Add basic dashboard home page showing projects, jobs, approvals, and recent activity
- [ ] Add route guards or session checks as needed for personal-use auth
- [ ] Add frontend test and typecheck setup

### Manual checks
- [ ] Manual check: the UI shell works on desktop and mobile widths
- [ ] Manual check: empty-state and error-state screens make the next action obvious

## Phase 5 - Brand Profile and Onboarding

### Build tasks
- [x] Build brand profile database/service/API support
- [x] Add brand profile create, edit, view, and list routes
- [ ] Add onboarding flow for channel name, niche, target audience, tone, hook style, CTA style, visual style, and posting preferences
- [ ] Add settings UI for updating brand rules later
- [ ] Add validation for missing or inconsistent brand profile data
- [ ] Add prompt context builder that converts brand profile fields into AI-ready context
- [ ] Add storage for platform preferences and output defaults
- [ ] Add support for multiple brand profiles if needed for personal multi-channel use

### Manual checks
- [ ] Manual check: onboarding captures enough information to generate useful ideas and scripts without extra prompting
- [ ] Manual check: editing a brand profile does not break existing historical project records

## Phase 6 - Project CRUD and Workflow State Machine

### Build tasks
- [ ] Build project create, edit, view, archive, and list APIs
- [x] Build project list and project detail pages in the web app
- [x] Add project fields for title, target platform, objective, notes, and linked brand profile
- [x] Implement the project state machine from `draft` through `published` and `archived`
- [x] Add explicit transition guards for every state-changing action
- [ ] Add visible project timeline/status history in the UI
- [ ] Add manual override notes for admin/user interventions
- [ ] Add project activity log capturing approvals, jobs, failures, retries, and publish actions
- [x] Add project filtering and search in the UI
- [x] Add tests for valid and invalid project status transitions

### Manual checks
- [ ] Manual check: invalid state transitions are blocked in both API and UI
- [ ] Manual check: a project’s current status is always understandable from the dashboard

## Phase 7 - Idea Generation and Research Workflow

### Build tasks
- [ ] Implement idea generation job submission from a project
- [ ] Add idea generation service using brand context and topic constraints
- [ ] Add optional research step for trends, competitor angles, and posting strategies
- [ ] Persist generated content ideas with score, rationale, topic, and angle
- [ ] Add UI for idea review, comparison, approval, rejection, and regeneration
- [ ] Add revision notes and regenerate-with-feedback flow
- [ ] Update project status when ideas are pending approval or approved
- [ ] Add tests for idea generation payload creation and approval gating

### Manual checks
- [ ] Manual check: generated ideas feel aligned with the brand profile and target platform
- [ ] Manual check: approval and rejection actions are easy to understand in the UI

## Phase 8 - Script Generation, Scene Planning, and Prompt Packs

### Build tasks
- [ ] Implement script generation job submission from an approved idea
- [ ] Build script generation service to produce hook, full script, estimated duration, titles, captions, and hashtags
- [ ] Persist script versions without overwriting previous approved or rejected versions
- [ ] Build scene breakdown generation with narration text, duration, overlay text, image prompt, video prompt, and notes
- [ ] Add script view and scene editor UI
- [ ] Add scene reorder, edit, and validation behavior
- [ ] Add regenerate script flow while preserving version history
- [ ] Add prompt-pack generation for narration and visual tools
- [ ] Add tests for scene JSON validation and script versioning

### Manual checks
- [ ] Manual check: script approval clearly shows the hook, full script, scene plan, and platform metadata
- [ ] Manual check: editing scene data does not produce invalid prompt packs or broken durations

## Phase 9 - Approval Engine and Review History

### Build tasks
- [ ] Implement approval records for idea, script, assets, final video, and publish stages
- [ ] Add immutable approval history persistence
- [ ] Add API endpoints for approve, reject, and regenerate feedback actions
- [ ] Add reusable approval UI components for all stages
- [ ] Add approval comments/feedback capture
- [ ] Add rules so downstream jobs cannot start unless the current stage is approved
- [ ] Add clear pending-approval inbox views for the dashboard
- [ ] Add notifications for items awaiting approval
- [ ] Add tests for approval gating across the full workflow

### Manual checks
- [ ] Manual check: publish-related actions are impossible without explicit approval state
- [ ] Manual check: rejection feedback is visible to the next regeneration attempt

## Phase 10 - Queue System, Background Jobs, and Progress Tracking

### Build tasks
- [ ] Choose and implement the job runner architecture backed by Redis
- [ ] Add `background_jobs` persistence and job lifecycle tracking
- [ ] Implement job states `queued`, `running`, `waiting_external`, `completed`, `failed`, and `cancelled`
- [ ] Implement retry policy per job type as defined in `docs/queue-jobs.md`
- [ ] Add progress update hooks for long-running tasks
- [ ] Add idempotency handling for publish scheduling and file ingestion
- [ ] Add job logs and per-attempt error capture
- [ ] Add job detail API and UI screens
- [ ] Add cancel/retry controls where safe
- [ ] Add tests for retry, resume, and failure state behavior

### Manual checks
- [ ] Manual check: long-running jobs visibly update progress in the UI
- [ ] Manual check: retrying a failed job does not duplicate assets or corrupt state

## Phase 11 - Browser Worker Foundation

### Build tasks
- [ ] Create the browser worker entrypoint and worker lifecycle management
- [ ] Add Playwright setup with persistent browser profile support
- [ ] Add provider abstraction with `ensure_session`, `open_workspace`, `submit_job`, `wait_for_completion`, `collect_downloads`, and `capture_debug_artifacts`
- [ ] Create centralized selector registry with versioned selector files
- [ ] Add screenshot and HTML snapshot capture for critical checkpoints and failures
- [ ] Add download interception and metadata tagging
- [ ] Add secret-safe logging for browser interactions
- [ ] Add recoverable session handling and manual intervention status reporting
- [ ] Add browser worker tests and smoke-test harness

### Manual checks
- [ ] Manual check: browser profiles remain outside version control and survive worker restarts
- [ ] Manual check: screenshots and logs are sufficient to debug failed browser runs

## Phase 12 - ElevenLabs Browser Automation

### Build tasks
- [ ] Implement ElevenLabs provider module
- [ ] Add session/authentication check flow
- [ ] Add navigation to the speech generation workspace
- [ ] Add narration text input using approved script or scene narration source
- [ ] Add voice selection and settings application
- [ ] Add generation trigger and completion detection
- [ ] Add narration audio download handling
- [ ] Emit generation attempt metadata and output asset registration payloads
- [ ] Add retry-on-timeout and selector-failure behavior
- [ ] Add smoke tests or dry-run scripts for ElevenLabs automation

### Manual checks
- [ ] Manual check: the browser flow still works against the live ElevenLabs UI
- [ ] Manual check: downloaded narration matches the approved script and chosen voice settings
- [ ] Manual check: login/captcha/manual-auth failures cleanly hand off to the user

## Phase 13 - Flow Browser Automation for Visual Generation

### Build tasks
- [ ] Implement Google Flow provider module
- [ ] Add session/authentication check flow
- [ ] Add project/workspace navigation
- [ ] Add scene prompt submission for single-scene and batch flows
- [ ] Add completion detection for generated visuals
- [ ] Add clip/image download handling
- [ ] Map downloaded outputs back to project, scene, and generation attempt records
- [ ] Add retry and timeout handling
- [ ] Add selector fallback strategy where reasonable
- [ ] Add smoke tests or dry-run scripts for Flow automation

### Manual checks
- [ ] Manual check: the browser flow still works against the live Flow UI
- [ ] Manual check: scene-to-output mapping remains correct for multi-scene generations
- [ ] Manual check: failed or mismatched downloads are quarantined for review instead of silently accepted

## Phase 14 - Download Manager and Asset Registry

### Build tasks
- [ ] Implement download watcher or explicit ingest flow for browser outputs
- [ ] Add file hash calculation and duplicate detection
- [ ] Add canonical storage path generation under `storage/projects/{project_id}`
- [ ] Move files from temporary download folders into permanent storage
- [ ] Register assets with metadata including file path, mime type, duration, resolution, checksum, scene link, and attempt link
- [ ] Add quarantine path for unknown or mismatched downloads
- [ ] Add asset approval/rejection/regeneration APIs
- [ ] Add asset gallery and preview UI
- [ ] Add tests for download ingestion mapping and duplicate handling

### Manual checks
- [ ] Manual check: files are stored in predictable project folders and can be traced back to their source attempt
- [ ] Manual check: a mismatched file never lands in the approved asset path by accident

## Phase 15 - Media Composer, Timeline Builder, and Exports

### Build tasks
- [ ] Create the media worker entrypoint and job execution pipeline
- [ ] Implement project manifest loading for rough-cut assembly
- [ ] Resolve approved assets per scene
- [ ] Use narration audio as the primary timing anchor
- [ ] Build timeline assembly logic from ordered scenes and target durations
- [ ] Add trim/loop/fallback behavior for scene duration mismatches
- [ ] Add subtitle generation pipeline
- [ ] Add overlay and transition support
- [ ] Implement FFmpeg helper modules for concat, audio overlay, subtitle burn-in, and export
- [ ] Export rough cut and final cut artifacts
- [ ] Persist timeline manifests for every export attempt
- [ ] Add rough cut preview and final export views in the UI
- [ ] Add tests for timeline manifest validation and sample export behavior

### Manual checks
- [ ] Manual check: rough cuts stay in sync with narration and scene order
- [ ] Manual check: subtitle timing, audio levels, and export quality are acceptable on real sample content
- [ ] Manual check: the same inputs produce deterministic export results

## Phase 16 - Final Approval and Publishing Center

### Build tasks
- [ ] Build publish job persistence and APIs
- [ ] Add publish preparation flow from approved final video
- [ ] Add metadata editor for title, description, hashtags, thumbnails, and platform-specific settings
- [ ] Add schedule and publish-now flows with state validation
- [ ] Add publish approval stage before any upload action
- [ ] Implement platform adapter abstraction for YouTube, Facebook, TikTok, and manual publish fallback
- [ ] Add publish safety checks so only explicitly approved publish jobs can run
- [ ] Add idempotency keys for scheduling requests
- [ ] Add publishing calendar and queue views in the UI
- [ ] Add tests for publish job safety and state transitions

### Manual checks
- [ ] Manual check: publish actions are blocked until the final approval and publish approval stages are complete
- [ ] Manual check: the metadata editor shows exactly what will be posted
- [ ] Manual check: manual publish fallback is available if automation/upload integration fails

## Phase 17 - Analytics Sync and Learning Loop

### Build tasks
- [ ] Implement analytics snapshot persistence and APIs
- [ ] Add analytics sync job flow for published content
- [ ] Store views, likes, comments, shares, saves, watch time, CTR, average view duration, and retention data
- [ ] Build project analytics screens and account-level insights views
- [ ] Add performance summaries by hook, duration, posting time, voice, and content type
- [ ] Build insight generation and recommendation persistence
- [ ] Add recommendation UI for strategy updates and future prompt guidance
- [ ] Feed analytics-derived learnings back into idea and script generation context
- [ ] Add tests for analytics ingestion and insight generation behavior

### Manual checks
- [ ] Manual check: analytics are clearly tied back to the originating project and publish job
- [ ] Manual check: recommendations are useful and not based on obviously noisy or incomplete data

## Phase 18 - Observability, Reliability, and Manual Override Tooling

### Build tasks
- [ ] Add structured logs across API, browser worker, and media worker
- [ ] Add error reporting and correlation IDs across job chains
- [ ] Add per-provider debug artifact storage for screenshots, HTML snapshots, and failure notes
- [ ] Add manual retry and resume tools for browser and media jobs
- [ ] Add manual override controls for blocked workflow states
- [ ] Add explicit `manual_intervention_required` handling where needed
- [ ] Add operator-facing status pages for failed jobs, stuck jobs, and quarantined assets
- [ ] Add cleanup and retention strategy for generated artifacts without destructive permanent deletion
- [ ] Add backup/export strategy for project metadata and approvals

### Manual checks
- [ ] Manual check: a failed job can be debugged without reading raw code
- [ ] Manual check: manual interventions leave an audit trail and do not hide the original failure

## Phase 19 - Security, Config, and Environment Hardening

### Build tasks
- [ ] Add env validation for all services
- [ ] Ensure no secrets are hardcoded anywhere in code, docs, or tests
- [ ] Add safe secret-loading patterns for local development
- [ ] Add storage permission checks for downloads, profiles, temp files, and exports
- [ ] Add config separation for development, testing, and production-like local environments
- [ ] Add safe logging redaction for tokens, cookies, and provider credentials
- [ ] Add validation for external file paths before ingest or processing
- [ ] Add dependency audit and update workflow

### Manual checks
- [ ] Manual check: local setup works without exposing secrets in logs or screenshots
- [ ] Manual check: browser profiles and downloads are stored in the intended private locations

## Phase 20 - Testing, QA, and Launch Readiness

### Build tasks
- [ ] Add unit tests for schemas, services, state transitions, and helpers
- [ ] Add API integration tests for project, idea, script, approval, asset, publish, and analytics routes
- [ ] Add browser worker smoke tests and replay-friendly debug fixtures
- [ ] Add media pipeline smoke tests with sample assets
- [ ] Add end-to-end happy-path test from project creation to final export
- [ ] Add end-to-end failure-path tests for rejected approvals, selector failures, download mismatch, and FFmpeg failure
- [ ] Add CI workflow for lint, typecheck, tests, and migration checks
- [ ] Add release checklist for docs, env samples, migrations, and smoke tests
- [ ] Add sample demo project data for manual validation

### Manual checks
- [ ] Manual check: full workflow succeeds on a real sample project from idea to export
- [ ] Manual check: approval checkpoints genuinely stop the workflow until the user approves
- [ ] Manual check: browser workers, media exports, and publish preparation are stable across multiple runs

## Ongoing Documentation Tasks

### Build tasks
- [ ] Update `docs/backend-api.md` whenever API routes or payloads change
- [ ] Update `docs/database-schema.md` whenever the database schema changes
- [ ] Update `docs/queue-jobs.md` whenever job payloads, retry policy, or job states change
- [ ] Update `docs/browser-automation-spec.md` whenever providers, selectors, or failure handling change
- [ ] Update `docs/media-pipeline.md` whenever manifests, subtitle flow, or export behavior changes
- [ ] Update `docs/env-setup.md` whenever setup commands or env vars change
- [ ] Keep this task list updated as new features, blockers, or manual QA steps are discovered

### Manual checks
- [ ] Manual check: docs stay in sync with the code after every significant feature or architecture change

## Final MVP Completion Gate

Mark MVP complete only after all items below are true:

- [ ] A user can create and manage a brand profile
- [ ] A user can create a project and move it through the defined workflow states
- [ ] A user can generate and approve ideas
- [ ] A user can generate, edit, and approve scripts and scene plans
- [ ] The browser worker can generate narration through ElevenLabs and register the asset
- [ ] The browser worker can generate scene visuals through Flow and register the assets
- [ ] The download manager correctly maps generated files into canonical project storage
- [ ] The media worker can assemble a rough cut automatically from approved assets
- [ ] A user can review and approve the final video
- [ ] The system can prepare metadata and a publish job with approval gating
- [ ] The system can sync analytics and surface useful insights
- [ ] Logs, retries, and manual override paths are present for critical failures
- [ ] Core lint, typecheck, migration, and test commands pass
- [ ] All required manual checks for the shipped phases have been completed
