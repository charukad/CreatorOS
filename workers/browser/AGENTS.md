# workers/browser/AGENTS.md

## Purpose
Operate browser-based provider workflows with Playwright.

## Rules
- isolate providers into separate modules
- centralize selectors
- capture screenshots on failure
- do not log secrets
- map every output back to project and scene metadata
- prefer resilient selectors

## Verification
- provider smoke tests
- manual dry run with screenshots enabled
