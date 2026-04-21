# CreatorOS

CreatorOS is a personal-use AI content operating system for planning, generating, reviewing, assembling, and publishing social media content with a human approval loop.

## Current Status

The repository now includes a working first vertical slice:
- a Next.js dashboard for brand profiles, projects, ideas, scripts, approvals, queued jobs, generated asset previews, and asset review
- a FastAPI service with persisted workflow records, approval history, background jobs, generation attempts, and assets
- a browser worker that can consume queued narration/visual jobs in `dry_run` mode and write local development artifacts
- shared TypeScript workflow contracts in `packages/shared`
- migration, testing, and setup scaffolding across the stack

## Project Goals

- Keep the user as the final approver before publishing
- Prefer existing subscriptions and browser automation where APIs are not practical
- Make every long-running step resumable, traceable, and observable
- Preserve all generated artifacts and generation attempts

## Repository Layout

```text
apps/
  api/       FastAPI orchestration API
  web/       Next.js dashboard
workers/
  browser/   Playwright automation worker
  media/     FFmpeg/media assembly worker
packages/
  shared/    Shared TypeScript contracts and helpers
docs/        Product and architecture documentation
storage/     Local generated artifacts and exports
scripts/     Setup and verification scripts
tests/       Initial automated tests
```

## Setup

1. Install JavaScript dependencies:

   ```bash
   pnpm install
   ```

2. Create a local virtual environment and install Python dependencies:

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```

3. Install Playwright browsers:

   ```bash
   .venv/bin/playwright install
   ```

4. Copy the environment examples you need:

   - `apps/web/.env.example`
   - `apps/api/.env.example`
   - `workers/browser/.env.example`
   - `workers/media/.env.example`

5. Run migrations once the database is configured:

   ```bash
   alembic upgrade head
   ```

## Development Commands

```bash
pnpm --filter web dev
uvicorn apps.api.main:app --reload
.venv/bin/python -m workers.browser.main
.venv/bin/python -m workers.media.main
pnpm --filter web lint
pnpm typecheck
.venv/bin/ruff check .
.venv/bin/pytest
```

## Current Worker Note

The browser worker currently supports a `dry_run` provider mode for local development. In that mode it:
- claims queued browser jobs from the database
- generates local WAV narration placeholders and SVG visual placeholders
- marks attempts and assets as completed so the end-to-end workflow can be exercised before live Playwright provider automation is wired in
- auto-promotes the project into asset review when the current script has both narration and scene assets ready

## Documentation

Documentation lives in [docs/README.md](docs/README.md) and the implementation checklist lives in [docs/full-project-task-list.md](docs/full-project-task-list.md).
