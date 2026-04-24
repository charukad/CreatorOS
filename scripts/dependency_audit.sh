#!/usr/bin/env bash
set -euo pipefail

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm is required to run the dependency audit." >&2
  exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Expected a local virtualenv at .venv/ before running the dependency audit." >&2
  exit 1
fi

if [[ ! -x ".venv/bin/pip-audit" ]]; then
  echo "pip-audit is not installed in .venv. Run '.venv/bin/python -m pip install pip-audit' first." >&2
  exit 1
fi

echo "Running pnpm production dependency audit..."
pnpm audit --prod --audit-level high

echo "Running Python dependency audit..."
.venv/bin/pip-audit -r requirements.txt

echo "Dependency audit completed."
