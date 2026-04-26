#!/usr/bin/env bash
set -euo pipefail

./scripts/secret_scan.py
pnpm --filter web lint
pnpm typecheck
.venv/bin/ruff check .
.venv/bin/pytest
