#!/usr/bin/env bash
set -euo pipefail

pnpm --filter web lint
pnpm --filter web typecheck
.venv/bin/ruff check .
.venv/bin/pytest
