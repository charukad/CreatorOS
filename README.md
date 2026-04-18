# CreatorOS

CreatorOS is a personal-use AI content operating system for planning, generating, reviewing, assembling, and publishing social media content with a human approval loop.

## Current Status

The repository now includes the first implementation bootstrap:
- a pnpm workspace with a starter Next.js app in `apps/web`
- a starter FastAPI service in `apps/api`
- starter browser and media worker entrypoints
- shared TypeScript workflow contracts in `packages/shared`
- basic migration, testing, and setup scaffolding

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
pnpm --filter web typecheck
.venv/bin/ruff check .
.venv/bin/pytest
```

## Documentation

Documentation lives in [docs/README.md](docs/README.md) and the implementation checklist lives in [docs/full-project-task-list.md](docs/full-project-task-list.md).
