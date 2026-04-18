# apps/api/AGENTS.md

## Purpose
Build the orchestration API, persistence layer, and queue submission logic.

## Rules
- use Pydantic for schemas
- use explicit enums for workflow states
- keep routes thin and services testable
- every mutating route should validate current state transitions
- no silent failures

## Verification
- `ruff check .`
- `pytest`
