#!/usr/bin/env bash
set -euo pipefail

pnpm --filter web lint
pnpm typecheck
.venv/bin/ruff check .
.venv/bin/pytest
