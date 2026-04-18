# Queue Jobs

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

### `generate_visuals_browser`
Input:
- project_id
- scene ids
- prompt pack
- provider=flow_web

Output:
- scene video/image assets
- generation attempt records

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
- audio asset id
- approved scene assets
- subtitle mode

Output:
- rough cut asset
- timeline manifest

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
