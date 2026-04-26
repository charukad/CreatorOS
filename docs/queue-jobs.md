# Queue Jobs

## Current Implementation Note
- `generate_idea_research`, `generate_ideas`, and `generate_script` now create project-level background job records and lifecycle logs before running deterministic local planning inline
- `generate_audio_browser` and `generate_visuals_browser` can now be queued through the API
- queue submission persists `background_jobs`, `generation_attempts`, and planned `assets`
- the browser worker can now execute those queued jobs in local `dry_run` mode or through persistent-profile Playwright provider modules
- `compose_rough_cut` can now be queued after asset approval and consumed by the media worker
- `final_export` can now be queued after a completed rough-cut job for the current script
- the media worker currently probes WAV narration duration, validates contiguous timeline data, writes an audio-anchored timeline manifest, an HTML rough-cut preview artifact, an SRT subtitle sidecar asset, an FFmpeg command-plan sidecar with scene overlay text, trim/loop handling, and fade transitions, optionally renders/registers a `video/mp4` rough cut when `MEDIA_ENABLE_FFMPEG_RENDER=true`, and can render or reuse a source MP4 for the dedicated `final_video` export
- job detail, job timeline logs, safe cancel, and safe retry operations are available through the API, dedicated job detail screen, and project page
- queued browser/media job payloads include a `correlation_id` that is also copied into queue log metadata
- queued browser, media, publisher, and analytics jobs now publish Redis wake-up signals plus general `creatoros:jobs:*` event payloads after the queue write commits
- worker entrypoints now run as long-lived Redis-backed listener services that drain backlog immediately, then wait on worker-specific wake-up channels with timed polling fallback
- worker loops now publish ephemeral Redis heartbeats so operations views can show last-seen time, current loop phase, wake-up counts, and processed-job totals
- the API now exposes `GET /api/events/background-jobs/stream` so the web dashboard, project, job, and operations screens can react to pushed job events instead of relying only on timed polling
- browser provider debug artifacts and failure screenshot/HTML snapshots are captured into per-provider debug folders and linked from job logs
- browser workers now load versioned selector bundles, capture checkpoint screenshot/HTML artifacts during session setup, and log the selector version used for each provider run
- Playwright-backed ElevenLabs and Flow providers now use selector fallback resolution, provider workspace URLs, and persistent Chromium profiles when `BROWSER_PROVIDER_MODE=playwright`
- browser workers retry timeout/selector-style provider failures once before failing the job
- browser output ingestion now stages raw downloads into explicit project metadata ingest paths, writes per-download manifest sidecars, persists file checksums, treats matching repeated downloads as idempotent, logs duplicate checksums, and quarantines mismatched or conflicting downloads for manual review
- browser workers now emit per-attempt request metadata and output registration payloads under project `metadata/` paths
- browser workers now redact secret-like browser log fields and pause auth/captcha/verification failures in `waiting_external` for operator recovery
- media workers retry timeout-style FFmpeg render failures once before failing the job
- analytics snapshots can now be queued for published jobs through the API and project analytics panel, then consumed by the analytics worker with first-pass insights persisted for review
- actual Redis-backed blocking execution for inline idea/script generation and automated retry backoff policy are still pending
- automated platform polling adapters for `sync_analytics` are still pending

## Principles
- Every long-running operation is a queued job.
- Jobs must be retryable.
- Jobs must write progress updates.
- Jobs must preserve attempt history.
- Shared payload contracts live in `packages/shared/src/contracts.ts` and fixture examples live in
  `packages/shared/src/contract-fixtures.ts`.

## Core Jobs
### `generate_idea_research`
Input:
- project_id
- brand_profile_id
- optional focus topic
- optional source feedback notes

Output:
- persisted idea research snapshot with summary, trend observations, competitor angles, posting strategies, and recommended topics

Current inline-local payload includes:
- brand profile id
- target platform
- objective
- optional focus topic
- source feedback notes
- same-brand analytics learning context when prior insights exist
- generated research snapshot id after completion

### `generate_ideas`
Input:
- project_id
- brand_profile_id
- topic constraints

Output:
- content idea records

Current inline-local payload includes:
- brand profile id
- target platform
- objective
- latest research snapshot id when available
- derived idea research context when available
- source feedback notes for regeneration
- same-brand analytics learning context when prior insights exist
- idea count and generated idea ids after completion
- correlation id for activity/job log tracing

### `generate_script`
Input:
- project_id
- approved idea id
- brand profile context

Output:
- script record
- scene records

Current inline-local payload includes:
- approved idea id
- brand profile id
- source feedback notes
- same-brand analytics learning context when prior insights exist
- generated script id and version after completion
- scene count
- correlation id for activity/job log tracing

### `generate_audio_browser`
Input:
- project_id
- script_id
- voice settings
- provider=elevenlabs_web

Output:
- narration audio asset
- generation attempt record

Persisted queue payload includes:
- script version
- optional voice label
- narration segments derived from the current prompt pack
- a planned narration asset path with the generation attempt id embedded so regeneration does not overwrite older artifacts

Prompt-pack note:
- prompt packs include `brand_context`, a reusable structured context generated from the brand profile readiness/prompt-context service

### `generate_visuals_browser`
Input:
- project_id
- scene ids
- prompt pack
- provider=flow_web

Output:
- scene video/image assets
- generation attempt records

Persisted queue payload includes:
- script version
- selected scene ids
- scene prompt excerpts for the browser worker handoff
- planned scene asset paths with the generation attempt id embedded so every output stays traceable

### `ingest_download`
Input:
- file path
- worker context
- project/scene metadata

Output:
- asset record
- file moved to canonical storage path

### `compose_rough_cut`
Input:
- project_id
- current approved script id
- latest ready narration asset
- ready scene visual asset for every scene
- output rough-cut asset id

Output:
- rough cut preview asset
- timeline manifest sidecar file
- subtitle sidecar asset

Persisted queue payload includes:
- script version
- scene count
- planned preview path
- planned manifest path
- rough-cut output asset id
- subtitle output asset id and path
- planned MP4 path and FFmpeg command-plan path
- video output asset id when FFmpeg rendering is enabled and succeeds

### `final_export`
Input:
- project_id
- current approved script id
- rough-cut review asset id
- completed rough-cut manifest and subtitle sidecars
- optional ready rough-cut MP4 source asset
- output final-video asset id
- export profile

Output:
- final video asset
- FFmpeg command-plan sidecar

Persisted queue payload includes:
- script version
- scene count
- rough-cut asset id
- optional source MP4 asset id and path when a ready rough-cut video exists
- manifest and subtitle paths copied from the latest completed rough-cut job
- final-video output asset id and planned storage path
- planned final-export FFmpeg command-plan path
- export profile settings used for the render or source-video reuse decision

### `publish_content`
Input:
- publish_job_id
- approved_publish_job_state
- handoff_path
- adapter_name

Output:
- v1 manual handoff JSON under `storage/projects/{project_id}/publish`
- job state `waiting_external` while the user uploads on the target platform
- completed job only after manual publish completion is recorded
- explicit failure if approval, final asset, or handoff validation no longer passes

### `sync_analytics`
Input:
- publish_job_id
- platform
- manual metric snapshot payload

Output:
- analytics snapshot
- generated insights
- completed background job with snapshot id in `payload_json.analytics_snapshot_id`

Current manual v1 behavior:
- `POST /api/publish-jobs/{publish_job_id}/queue` creates a `publish_content` background job only after publish approval or scheduling
- `python -m workers.publisher.main` claims `publish_content` jobs and selects a platform-aware manual handoff adapter for YouTube, TikTok, or Facebook, with a generic manual fallback for unknown platforms
- publish handoff jobs remain `waiting_external` until the user uploads manually and records completion
- `POST /api/publish-jobs/{publish_job_id}/analytics/queue` creates a `sync_analytics` background job only after the publish job is marked `published`
- `python -m workers.analytics.main` claims `sync_analytics` jobs, persists the supplied metric snapshot, creates insights, and completes the job
- active queued/running/waiting-external analytics sync jobs block duplicate sync submissions for the same publish job
- `POST /api/publish-jobs/{publish_job_id}/sync-analytics` records an operator-supplied analytics snapshot only after the publish job is marked `published`
- the direct sync endpoint remains for compatibility, but the project UI uses the queued worker path
- analytics sync persists engagement metrics, optional retention data, and generated project-level insights
- `GET /api/analytics/account` summarizes latest snapshots per publish job across hook, duration, posting window, voice, and content type
- the project page can display the latest snapshot and insight cards for review
- official platform upload and analytics polling adapters are still pending

## Retry Policy
- browser jobs: up to 4 total execution attempts (initial run plus 3 retries) with screenshots, HTML snapshots, and logs
- media jobs: up to 3 total execution attempts (initial run plus 2 retries) for transient FFmpeg failures
- publish jobs: up to 2 total execution attempts (initial run plus 1 retry), then manual review required
- analytics sync jobs: up to 2 total execution attempts for operator-supplied metric snapshots
- inline idea research/idea/script planning jobs do not support manual retry; re-run the project action that created the job instead

Current manual retry behavior:
- `POST /api/jobs/{job_id}/retry` is allowed only for `failed` or `cancelled` jobs
- retry resets the existing job to `queued`, clears the job error, and reuses the existing generation attempts and planned assets instead of creating duplicate placeholders
- retry resets related non-rejected assets to `planned` and clears stale checksums
- retry enforces the per-job execution attempt budget above using `background_jobs.attempts`
- retry is blocked when another active job of the same type already exists for the same script
- completed jobs cannot be retried from the API
- browser workers also retry timeout/selector-style provider failures once inline before a job reaches `failed`
- media workers also retry timeout-style FFmpeg render failures once inline before a job reaches `failed`

Current manual resume behavior:
- `POST /api/jobs/{job_id}/resume` is allowed only for stale `running` browser and media jobs
- `stale_after_minutes` defaults to `30` so recently updated workers are not interrupted accidentally
- resume resets the existing job to `queued`, clears stale running timestamps/errors, and preserves completed attempts plus ready/rejected assets
- unfinished attempts return to `queued`; unfinished related assets return to `planned`
- resume writes a `job_resumed` warning log for the job timeline and operations review

Current manual cancel behavior:
- `POST /api/jobs/{job_id}/cancel` is allowed only for `queued` or `waiting_external` jobs
- cancellation marks the job and unfinished generation attempts as `cancelled`
- unfinished related assets are marked `failed` because the asset model does not yet have a dedicated `cancelled` state
- actively `running` jobs are not cancelled by the API until worker-aware interruption exists

## Job State Model
`queued -> running -> waiting_external -> completed | failed | cancelled`

## Persisted Job Logs
The `job_logs` table records operator-facing lifecycle events. Current event types include:
- `job_queued`
- `job_started`
- `job_claimed`
- `job_progress_updated`
- `content_ideas_generated`
- `script_generated`
- `attempt_started`
- `attempt_completed`
- `job_completed`
- `job_failed`
- `job_cancelled`
- `job_retried`
- `job_resumed`
- `browser_provider_retry_scheduled`
- `media_render_retry_scheduled`
- `asset_ingestion_idempotent`
- `asset_ingestion_conflict`
- `generation_attempt_metadata_written`
- `attempt_output_registration_written`

Logs include:
- `level` for UI severity
- `message` for human-readable diagnosis
- `metadata_json` for structured details such as progress, worker type, scene id, or previous state
- project, script, background job, and optional generation attempt identifiers

Additional current recovery events:
- `debug_artifacts_captured`
- `browser_selector_registry_loaded`
- `browser_session_prepared`
- `browser_session_validated`
- `browser_workspace_opened`
- `browser_checkpoint_artifacts_captured`
- `browser_failure_artifacts_captured`
- `browser_failure_artifact_capture_failed`
- `browser_downloads_tagged`
- `browser_manual_intervention_detected`
- `downloads_quarantined`
- `duplicate_asset_detected`
- `manual_intervention_required`
