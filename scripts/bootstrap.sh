#!/usr/bin/env bash
set -euo pipefail

pnpm install
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/playwright install
