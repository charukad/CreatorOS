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
- `BROWSER_PROVIDER_MODE`
- `BROWSER_MAX_JOBS_PER_RUN`
- `PLAYWRIGHT_HEADLESS`
- `PLAYWRIGHT_PROFILE_ROOT`
- `PLAYWRIGHT_DOWNLOAD_ROOT`
- `ELEVENLABS_PROFILE_NAME`
- `FLOW_PROFILE_NAME`

### Media Worker
- `FFMPEG_BINARY`
- `MEDIA_ENABLE_FFMPEG_RENDER`

### Frontend
- `NEXT_PUBLIC_API_BASE_URL`

## Runtime Validation
- `APP_ENV=production` or `APP_ENV=prod` requires `SECRET_KEY` to be changed from local/example defaults.
- `CORS_ORIGINS` must include at least one origin.
- API and media worker storage/download path settings must not be empty.
- browser worker profile and download roots must be different paths to avoid mixing cookies/profiles with generated downloads.
- `BROWSER_MAX_JOBS_PER_RUN` must be at least `1`.
- `BROWSER_PROVIDER_MODE` is currently limited to `dry_run` until the live provider automation is implemented.
- `FFMPEG_BINARY` must not be empty.

## Local Folder Expectations
- browser downloads should land in a dedicated folder per run or provider
- project assets should move into canonical storage after ingestion
- browser profiles should remain outside version control
- in local development, `BROWSER_PROVIDER_MODE=dry_run` lets the browser worker generate WAV/SVG placeholder outputs without live provider sessions
- the media worker writes rough-cut preview and manifest files under `storage/projects/{project_id}/rough-cuts`
- the media worker writes subtitle sidecars under `storage/projects/{project_id}/subtitles`
- the media worker writes an FFmpeg command-plan JSON file beside rough-cut previews
- MP4 rendering requires FFmpeg to be installed and `MEDIA_ENABLE_FFMPEG_RENDER=true`

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
