# Repository Structure

## Proposed Monorepo Layout
```text
creatoros/
├─ AGENTS.md
├─ docs/
│  ├─ project-overview.md
│  ├─ repo-structure.md
│  ├─ build-plan.md
│  ├─ backend-api.md
│  ├─ database-schema.md
│  ├─ shared-contracts.md
│  ├─ queue-jobs.md
│  ├─ browser-automation-spec.md
│  ├─ media-pipeline.md
│  └─ env-setup.md
├─ apps/
│  ├─ web/
│  │  ├─ AGENTS.md
│  │  ├─ app/
│  │  ├─ components/
│  │  ├─ lib/
│  │  ├─ hooks/
│  │  └─ types/
│  └─ api/
│     ├─ AGENTS.md
│     ├─ main.py
│     ├─ core/
│     ├─ routes/
│     ├─ models/
│     ├─ schemas/
│     ├─ services/
│     ├─ jobs/
│     └─ db/
├─ workers/
│  ├─ browser/
│  │  ├─ AGENTS.md
│  │  ├─ main.py
│  │  ├─ providers/
│  │  ├─ selectors/
│  │  ├─ downloads/
│  │  └─ sessions/
│  └─ media/
│     ├─ AGENTS.md
│     ├─ main.py
│     ├─ ffmpeg/
│     ├─ subtitles/
│     ├─ timeline/
│     └─ exporters/
├─ packages/
│  └─ shared/
│     ├─ src/contracts.ts
│     ├─ src/contract-fixtures.ts
│     ├─ src/storage.ts
│     └─ src/workflow.ts
├─ storage/
│  ├─ projects/
│  ├─ downloads/
│  ├─ previews/
│  ├─ exports/
│  └─ temp/
├─ scripts/
└─ tests/
```

## Responsibilities by Service
### `apps/web`
- dashboard UI
- setup/onboarding
- project pages
- approvals
- asset previews
- publishing calendar
- analytics views

### `apps/api`
- auth/session
- brand/project CRUD
- orchestration endpoints
- queue submission
- analytics sync requests
- publish safety checks
- state transitions

### `workers/browser`
- login/session handling
- web automation for ElevenLabs/Flow
- controlled downloads
- retry/resume
- screenshots/logging

### `workers/media`
- timeline assembly
- subtitle creation
- FFmpeg composition
- preview/final exports

## Storage Layout
Each project should have a stable folder structure:
```text
storage/projects/{project_id}/
├─ script/
├─ audio/
├─ scenes/
│  ├─ scene-001/
│  ├─ scene-002/
│  └─ ...
├─ rough-cuts/
├─ final/
├─ subtitles/
├─ publish/
├─ metadata/
└─ retention/
```
