# Queue Jobs

## Current Implementation Note
- `generate_audio_browser` and `generate_visuals_browser` can now be queued through the API
- queue submission persists `background_jobs`, `generation_attempts`, and planned `assets`
- the browser worker can now execute those queued jobs in local `dry_run` mode and materialize WAV/SVG development artifacts
- `compose_rough_cut` can now be queued after asset approval and consumed by the media worker
- the media worker currently writes a deterministic timeline manifest plus an HTML rough-cut preview artifact
- actual Redis-backed execution, retries, and worker progress updates are still pending

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

Persisted queue payload includes:
- script version
- scene count
- planned preview path
- planned manifest path
- rough-cut output asset id

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

## Retry Policy
- browser jobs: up to 3 retries with screenshots and logs
- media jobs: up to 2 retries for transient FFmpeg failures
- publish jobs: 1 retry only, then manual review required

## Job State Model
`queued -> running -> waiting_external -> completed | failed | cancelled`
