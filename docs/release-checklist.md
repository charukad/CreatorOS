# Release Checklist

Use this before pushing a larger CreatorOS milestone or asking someone else to test the repo.

## Automated Checks
- Run `.venv/bin/ruff check .`
- Run `.venv/bin/pytest`
- Run `pnpm --filter web lint`
- Run `pnpm typecheck`
- Run `DATABASE_URL=sqlite+pysqlite:///:memory: .venv/bin/alembic upgrade head`
- Run `pnpm --filter web build`

## Manual Smoke Checks
- Create or seed a demo brand profile and project.
- Move one project through idea generation, script approval, asset generation, asset approval, rough-cut composition, final approval, publish prep, manual published completion, and analytics sync.
- Confirm every publish action is blocked until the matching approval exists.
- Confirm failed or waiting jobs show useful logs, debug artifacts, and manual intervention notes.
- Confirm generated files stay under `storage/`, browser profiles stay outside git, and readiness output does not expose credentials.

## Documentation Checks
- Update `docs/backend-api.md` for route or payload changes.
- Update `docs/database-schema.md` for table or relationship changes.
- Update `docs/queue-jobs.md` for job payload, retry, or state changes.
- Update `docs/browser-automation-spec.md` for provider/debug artifact behavior.
- Update `docs/env-setup.md` for environment variable or setup changes.
- Update `docs/full-project-task-list.md` with completed tasks and remaining manual checks.
