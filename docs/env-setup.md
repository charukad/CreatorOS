# Environment Setup

## Required Software
- Node.js 20+
- pnpm
- Python 3.11+
- PostgreSQL
- Redis
- FFmpeg
- Playwright browsers

## Environment Variables
### Backend
- `DATABASE_URL`
- `REDIS_URL`
- `STORAGE_ROOT`
- `DOWNLOADS_ROOT`
- `APP_ENV`
- `SECRET_KEY`
- `DEFAULT_USER_EMAIL`
- `DEFAULT_USER_NAME`

### Browser Worker
- `PLAYWRIGHT_HEADLESS`
- `PLAYWRIGHT_PROFILE_ROOT`
- `PLAYWRIGHT_DOWNLOAD_ROOT`
- `ELEVENLABS_PROFILE_NAME`
- `FLOW_PROFILE_NAME`

### Frontend
- `NEXT_PUBLIC_API_BASE_URL`

## Local Folder Expectations
- browser downloads should land in a dedicated folder per run or provider
- project assets should move into canonical storage after ingestion
- browser profiles should remain outside version control

## Setup Steps
1. Install system dependencies.
2. Install frontend dependencies with pnpm.
3. Create a local Python virtual environment and install backend/worker dependencies inside it.
4. Install Playwright browsers.
5. Start PostgreSQL and Redis.
6. Create env files for web, api, and workers.
7. Run database migrations.
8. Start frontend, backend, and workers.

## Target Commands
```bash
pnpm install
.venv/bin/python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/playwright install
alembic upgrade head
pnpm --filter web dev
uvicorn apps.api.main:app --reload
.venv/bin/python -m workers.browser.main
.venv/bin/python -m workers.media.main
```
