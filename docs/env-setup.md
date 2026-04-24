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
CreatorOS now supports layered local env files for the API and each worker. Settings load, in order, from the service directory and repo root using these patterns:
- `.env`
- `.env.local`
- `.env.{environment}`
- `.env.{environment}.local`
- `.env.secrets.local`
- `.env.{environment}.secrets.local`

Normalized environment names:
- `dev` and `development` load the `development` overlays
- `test`, `testing`, and `ci` load the `testing` overlays
- `prod` and `production` load the `production` overlays
- `local-production` and `localprod` load the `localprod` overlays

Recommended local secret-loading pattern:
- keep shared non-secret defaults in tracked `.env.example` files
- keep machine-local overrides in untracked `.env.local`
- keep real secrets in untracked `.env.secrets.local` or `.env.{environment}.secrets.local`
- never store browser cookies, persistent profiles, or provider credentials in tracked files

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
- `PLAYWRIGHT_ACTION_TIMEOUT_MS`
- `PLAYWRIGHT_NAVIGATION_TIMEOUT_MS`
- `PLAYWRIGHT_DOWNLOAD_TIMEOUT_MS`
- `PLAYWRIGHT_PROFILE_ROOT`
- `PLAYWRIGHT_DOWNLOAD_ROOT`
- `ELEVENLABS_PROFILE_NAME`
- `FLOW_PROFILE_NAME`
- `ELEVENLABS_WORKSPACE_URL`
- `FLOW_WORKSPACE_URL`

### Media Worker
- `FFMPEG_BINARY`
- `MEDIA_ENABLE_FFMPEG_RENDER`

### Publisher Worker
- `PUBLISHER_MAX_JOBS_PER_RUN`
- `STORAGE_ROOT`

### Analytics Worker
- `ANALYTICS_MAX_JOBS_PER_RUN`

### Frontend
- `NEXT_PUBLIC_API_BASE_URL`

## Runtime Validation
- `APP_ENV=production` or `APP_ENV=prod` requires `SECRET_KEY` to be changed from local/example defaults.
- `APP_ENV=local-production` follows the same unsafe-secret protections as production while still targeting local-only infrastructure.
- `CORS_ORIGINS` must include at least one origin.
- API and media worker storage/download path settings must not be empty.
- browser worker profile and download roots must be different paths to avoid mixing cookies/profiles with generated downloads.
- `BROWSER_MAX_JOBS_PER_RUN` must be at least `1`.
- `PUBLISHER_MAX_JOBS_PER_RUN` must be at least `1`.
- `ANALYTICS_MAX_JOBS_PER_RUN` must be at least `1`.
- `BROWSER_PROVIDER_MODE` must be either `dry_run` or `playwright`.
- `ELEVENLABS_WORKSPACE_URL` and `FLOW_WORKSPACE_URL` must not be empty in `playwright` mode.
- `FFMPEG_BINARY` must not be empty.
- browser and media workers reject ingest, artifact, quarantine, and render paths that resolve outside the configured storage roots.

## Local Folder Expectations
- browser downloads should land in a dedicated folder per run or provider
- project assets should move into canonical storage after ingestion
- browser profiles should remain outside version control
- in local development, `BROWSER_PROVIDER_MODE=dry_run` lets the browser worker generate WAV/SVG placeholder outputs without live provider sessions
- `BROWSER_PROVIDER_MODE=playwright` launches persistent Chromium profiles under `PLAYWRIGHT_PROFILE_ROOT` and writes provider downloads under `PLAYWRIGHT_DOWNLOAD_ROOT/{provider}/{profile}`
- the media worker writes rough-cut preview and manifest files under `storage/projects/{project_id}/rough-cuts`
- the media worker writes subtitle sidecars under `storage/projects/{project_id}/subtitles`
- the media worker writes an FFmpeg command-plan JSON file beside rough-cut previews
- the publisher worker writes manual upload handoffs under `storage/projects/{project_id}/publish`
- future cleanup moves should write retention manifests under `storage/projects/{project_id}/retention` before any generated artifact leaves canonical storage
- MP4 rendering requires FFmpeg to be installed and `MEDIA_ENABLE_FFMPEG_RENDER=true`
- provider debug HTML snapshots are redacted before they are written to disk

## Local Security Checks
- Run `./scripts/secret_scan.py` before committing or pushing larger config-heavy changes.
- Use `./scripts/dependency_audit.sh` for an on-demand dependency vulnerability check.
- The CI workflow runs the secret scan on every push/PR and a separate weekly dependency audit workflow.

## Setup Steps
1. Install system dependencies.
2. Install frontend dependencies with pnpm.
3. Create a local Python virtual environment and install backend/worker dependencies inside it.
4. Install Playwright browsers.
5. Start PostgreSQL and Redis.
6. Create env files for web, api, and workers.
7. Run database migrations.
8. Start frontend, backend, and workers.

## Local Demo Data
After migrations, create a safe demo brand profile and project with:
```bash
.venv/bin/python -m scripts.seed_demo
```

The script is idempotent by demo title/channel name and creates audit activity for manual QA.

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
.venv/bin/python -m workers.publisher.main
.venv/bin/python -m workers.analytics.main
```
