# Browser Automation Specification

## Purpose
Use Playwright-based browser automation to operate subscription-based tools through their web UI when API usage is not available or not desired.

## Current Implementation Note
- the browser worker can already claim queued narration and visual jobs from the database
- local development currently uses a `dry_run` provider mode that writes WAV narration placeholders and SVG visual placeholders
- dry-run providers now write prompt/debug notes under per-provider `debug` folders and job logs link to those artifact paths
- browser provider failures now capture screenshot and HTML snapshot artifact paths through the provider contract before marking the job failed
- browser worker ingestion now hashes materialized files, logs duplicate checksums, and quarantines mismatched download counts under project storage for manual review
- live Playwright navigation, selectors, screenshots, and download handling are still pending for the real providers

## Supported Providers in v1
- ElevenLabs web workflow
- Google Flow web workflow

## Core Requirements
- persistent browser profile support
- isolated provider modules
- centralized selectors
- screenshot capture at critical checkpoints
- download interception and tagging
- recoverable sessions
- human handoff if login/captcha blocks progress

## Provider Abstraction
Each provider module should expose:
- `ensure_session()`
- `open_workspace()`
- `submit_job(payload)`
- `wait_for_completion()`
- `collect_downloads()`
- `capture_debug_artifacts()`

Current debug artifact convention:
- `storage/downloads/debug/elevenlabs/*-prompt.txt`
- `storage/downloads/debug/flow/*-prompt.txt`
- `storage/downloads/debug/{provider}/failures/*-screenshot.png`
- `storage/downloads/debug/{provider}/failures/*-snapshot.html`
- job logs use `debug_artifacts_captured` with `debug_artifact_paths`
- failure logs use `browser_failure_artifacts_captured` with `failure_artifact_paths`

## Selector Strategy
- keep selectors in dedicated versioned files
- prefer stable roles/labels over brittle CSS paths
- add fallback selectors where reasonable
- tag every failure with the selector key that failed

## ElevenLabs Web Flow
1. Ensure authenticated session.
2. Open speech generation page.
3. Paste approved narration text.
4. Apply configured voice/settings.
5. Trigger generation.
6. Wait until playable/downloadable.
7. Download and emit metadata.

## Flow Web Flow
1. Ensure authenticated session.
2. Open project/workspace.
3. Submit scene prompt or prompt batch.
4. Wait for generation completion.
5. Download generated clips.
6. Tag each clip with scene mapping.

## Failure Handling
- on selector failure: screenshot + HTML snapshot + `browser_failure_artifacts_captured` log entry
- on timeout: retry once in-page, then fail job
- on download mismatch: quarantine file for manual review
- on auth issue: mark job `manual_intervention_required` / `waiting_external`

## Safety Requirements
- no automatic publish actions through browser worker without upstream approval state
- no secret values logged
- no destructive clicks without explicit provider-specific safeguards
