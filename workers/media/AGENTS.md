# workers/media/AGENTS.md

## Purpose
Assemble rough cuts and final exports using project manifests and approved assets.

## Rules
- audio is the primary timing anchor
- preserve manifests and intermediate outputs
- keep FFmpeg invocation helpers modular
- make exports deterministic when given the same inputs

## Verification
- timeline manifest validation
- export smoke tests on sample project assets
