# Queue Jobs

## Current Implementation Note
- `generate_audio_browser` and `generate_visuals_browser` can now be queued through the API
- queue submission persists `background_jobs`, `generation_attempts`, and planned `assets`
- the browser worker can now execute those queued jobs in local `dry_run` mode and materialize WAV/SVG development artifacts
- `compose_rough_cut` can now be queued after asset approval and consumed by the media worker
- the media worker currently probes WAV narration duration, validates contiguous timeline data, writes an audio-anchored timeline manifest, an HTML rough-cut preview artifact, an SRT subtitle sidecar asset, an FFmpeg command-plan sidecar with scene overlay text, trim/loop handling, and fade transitions, and optionally renders/registers a `video/mp4` rough cut when `MEDIA_ENABLE_FFMPEG_RENDER=true`
- job detail, job timeline logs, safe cancel, and safe retry operations are available through the API, dedicated job detail screen, and project page
- queued browser/media job payloads include a `correlation_id` that is also copied into queue log metadata
- browser provider debug artifacts are captured into per-provider debug folders and linked from job logs
- browser output ingestion now persists file checksums, writes per-attempt asset paths, logs duplicate checksums, and quarantines mismatched download counts for manual review
- analytics snapshots can now be manually synced for published jobs through the API and project analytics panel, with first-pass insights persisted for review
- actual Redis-backed execution, automated retry policy, and live worker progress updates are still pending
- automated analytics platform polling through `sync_analytics` is still pending

## Principles
- Every long-running operation is a queued job.
- Jobs must be retryable.
- Jobs must write progress updates.
- Jobs must preserve attempt history.

## Core Jobs
### `generate_ideas`
Input:
- project_id
- brand_profile_id
- topic constraints

Output:
- content idea records

### `generate_script`
Input:
- project_id
- approved idea id
- brand profile context

Output:
- script record
- scene records

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
- rough cut id
- export profile

Output:
- final video asset

### `publish_content`
Input:
- publish_job_id

Output:
- published status or explicit failure

### `sync_analytics`
Input:
- publish_job_id

Output:
- analytics snapshot
- possibly new insights

Current manual v1 behavior:
- `POST /api/publish-jobs/{publish_job_id}/sync-analytics` records an operator-supplied analytics snapshot only after the publish job is marked `published`
- the API persists engagement metrics, optional retention data, and generated project-level insights
- the project page can display the latest snapshot and insight cards for review
- a queue-backed worker and official platform adapters are still pending

## Retry Policy
- browser jobs: up to 3 retries with screenshots and logs
- media jobs: up to 2 retries for transient FFmpeg failures
- publish jobs: 1 retry only, then manual review required

Current manual retry behavior:
- `POST /api/jobs/{job_id}/retry` is allowed only for `failed` or `cancelled` jobs
- retry resets the existing job to `queued`, clears the job error, and reuses the existing generation attempts and planned assets instead of creating duplicate placeholders
- retry resets related non-rejected assets to `planned` and clears stale checksums
- retry is blocked when another active job of the same type already exists for the same script
- completed jobs cannot be retried from the API

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
- `job_claimed`
- `job_progress_updated`
- `attempt_started`
- `attempt_completed`
- `job_completed`
- `job_failed`
- `job_cancelled`
- `job_retried`

Logs include:
- `level` for UI severity
- `message` for human-readable diagnosis
- `metadata_json` for structured details such as progress, worker type, scene id, or previous state
- project, script, background job, and optional generation attempt identifiers

Additional current recovery events:
- `debug_artifacts_captured`
- `downloads_quarantined`
- `duplicate_asset_detected`
- `manual_intervention_required`
