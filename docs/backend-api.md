# Backend API Design

## API Style
- REST for v1
- JSON request/response
- background jobs returned as task references
- explicit status enums
- every API response includes an `X-Request-ID` header for operator correlation
- shared response and worker handoff contracts live in `packages/shared/src/contracts.ts`

## Personal-Use Bootstrap Note
- until auth/session is implemented, v1 local development can attach brand profiles and projects to a single configured default user

## Logging and Correlation
- the API, browser worker, and media worker use structured JSON logs
- API request logs include method, path, status code, duration, and request ID
- clients may send `X-Request-ID`; otherwise the API generates one and returns it
- log output redacts URL credentials and common token, cookie, secret, password, and API-key fields
- `GET /api/health/ready` returns redacted connection strings so readiness checks do not expose local credentials

## Current Workflow Note
- the current idea and script workflow runs synchronously inside the API as a local deterministic generator
- asset-generation planning is now persisted through queued job records, generation attempts, and planned assets
- the browser worker can now consume queued narration and visual jobs in local `dry_run` mode and mark assets ready
- browser output ingestion now persists checksums, keeps regeneration paths attempt-specific, logs duplicate asset checksums, and quarantines mismatched downloads
- when the required assets finish generating, the project moves into `asset_pending_approval` for explicit review
- after asset approval, `compose_rough_cut` queues a media-worker job that probes WAV narration duration and writes an audio-anchored timeline manifest, rough-cut preview artifact, SRT subtitle sidecar asset, FFmpeg command-plan sidecar, and optionally a `video/mp4` rough-cut asset when FFmpeg rendering is enabled
- job detail, project activity, job timeline logs, safe cancel, retry, and resume endpoints are implemented for operator recovery
- operations recovery now surfaces failed jobs, manual-intervention jobs, stale running jobs, quarantined downloads, duplicate asset warnings, and non-destructive artifact retention candidates in API responses
- final-video approval, publish-job preparation, publish approval, and queue-backed manual publish handoffs are implemented before manual published completion
- manual analytics snapshots and first-pass insight generation are implemented for published jobs
- Redis-backed execution, automated retry policy, and live worker progress updates are still planned

## Core Resources
### Brand Profiles
- `POST /api/brand-profiles`
- `GET /api/brand-profiles/:id`
- `GET /api/brand-profiles/:id/readiness`
- `GET /api/brand-profiles/:id/prompt-context`
- `PATCH /api/brand-profiles/:id`
- `GET /api/brand-profiles`

### Projects
- `POST /api/projects`
- `GET /api/projects/:id`
- `PATCH /api/projects/:id`
- `GET /api/projects`
- `POST /api/projects/:id/archive`
- `POST /api/projects/:id/manual-override`
- `POST /api/projects/:id/transition`
- `GET /api/projects/:id/ideas`
- `GET /api/projects/:id/activity`
- `GET /api/projects/:id/export`
- `GET /api/projects/:id/analytics`
- `GET /api/projects/:id/approvals`
- `GET /api/projects/:id/jobs`
- `GET /api/projects/:id/assets`
- `GET /api/projects/:id/publish-jobs`
- `POST /api/projects/:id/assets/approve`
- `POST /api/projects/:id/assets/reject`
- `POST /api/projects/:id/compose/rough-cut`
- `POST /api/projects/:id/final-video/approve`
- `POST /api/projects/:id/final-video/reject`
- `POST /api/projects/:id/publish-jobs/prepare`
- `POST /api/projects/:id/ideas/generate`
- `GET /api/projects/:id/scripts/current`
- `POST /api/projects/:id/scripts/generate`
- `POST /api/projects/:id/generate/audio`
- `POST /api/projects/:id/generate/visuals`

### Ideas
- `POST /api/ideas/:id/approve`
- `POST /api/ideas/:id/reject`

### Scripts
- `POST /api/scripts/:id/approve`
- `POST /api/scripts/:id/reject`
- `GET /api/scripts/:id/scenes`
- `POST /api/scripts/:id/scenes/reorder`
- `GET /api/scripts/:id/prompt-pack`

### Scenes
- `PATCH /api/scenes/:id`

### Asset Files
- `GET /api/assets/:id`
- `GET /api/assets/:id/content`
- `POST /api/assets/:id/approve`
- `POST /api/assets/:id/reject`
- `POST /api/assets/:id/regenerate`

### Jobs
- `GET /api/jobs/:id`
- `POST /api/jobs/:id/cancel`
- `POST /api/jobs/:id/manual-intervention`
- `POST /api/jobs/:id/resume`
- `POST /api/jobs/:id/retry`

### Operations
- `GET /api/operations/recovery`

### Analytics
- `GET /api/analytics/account`

### Publish Jobs
- `POST /api/publish-jobs/:id/approve`
- `PATCH /api/publish-jobs/:id/metadata`
- `POST /api/publish-jobs/:id/queue`
- `POST /api/publish-jobs/:id/schedule`
- `POST /api/publish-jobs/:id/mark-published`
- `POST /api/publish-jobs/:id/sync-analytics`
- `POST /api/publish-jobs/:id/analytics/queue`

## Implemented Payloads
### `POST /api/brand-profiles`
```json
{
  "channel_name": "Creator Lab",
  "niche": "AI productivity",
  "target_audience": "Founders and solo creators",
  "tone": "Direct and optimistic",
  "hook_style": "Question-led hook",
  "cta_style": "Invite discussion",
  "visual_style": "Cinematic screen-recording mix",
  "posting_preferences_json": {
    "platforms": ["youtube_shorts", "tiktok"],
    "default_platform": "youtube_shorts",
    "output_defaults": {
      "aspect_ratio": "9:16",
      "target_duration_seconds": 35
    }
  }
}
```

Behavior note:
- brand profile text fields are trimmed before persistence
- posting preferences must be a JSON object
- `platforms`, when provided, must be a list of non-empty strings
- `default_platform`, when provided, must be a non-empty string
- `output_defaults`, when provided, must be an object

### `GET /api/brand-profiles/:id/readiness`
Response excerpt:
```json
{
  "brand_profile_id": "uuid",
  "is_ready": true,
  "missing_fields": [],
  "warnings": [],
  "recommended_next_steps": [
    "Use this profile to generate project ideas and script prompt packs."
  ]
}
```

Behavior note:
- readiness checks required setup fields, platform preferences, target-audience detail, and visual-style detail
- warnings do not block saving, but they make weak onboarding visible before generation quality suffers

### `GET /api/brand-profiles/:id/prompt-context`
Response excerpt:
```json
{
  "brand_profile_id": "uuid",
  "context_markdown": "# Brand Context: Creator Lab...",
  "context_json": {
    "identity": {
      "channel_name": "Creator Lab",
      "niche": "AI productivity"
    },
    "voice": {
      "tone": "Direct and optimistic",
      "hook_style": "Question-led hook",
      "cta_style": "Invite discussion"
    },
    "output_defaults": {
      "aspect_ratio": "9:16"
    }
  }
}
```

Behavior note:
- prompt context converts saved brand profile data into reusable AI-ready markdown and structured JSON
- script prompt-pack responses include the same brand context under `brand_context`

### `POST /api/projects`
```json
{
  "brand_profile_id": "uuid",
  "title": "3 AI automations I use daily",
  "target_platform": "youtube_shorts",
  "objective": "Create a short-form educational video",
  "notes": "Keep this under 45 seconds"
}
```

### `POST /api/projects/:id/transition`
```json
{
  "target_status": "idea_pending_approval"
}
```

### `POST /api/projects/:id/archive`
```json
{
  "reason": "Project is complete and no longer needs active workflow controls."
}
```

### `POST /api/projects/:id/manual-override`
```json
{
  "target_status": "failed",
  "reason": "Browser provider changed and the project needs operator recovery."
}
```

Behavior note:
- manual overrides bypass guarded transition prerequisites but require a reason and leave a project-event audit trail

### `POST /api/projects/:id/ideas/generate`
Request body:
```json
{
  "source_feedback_notes": "Make the next batch more specific to solo founders."
}
```

Behavior note:
- creates a completed `generate_ideas` background job with lifecycle logs before returning the generated ideas
- project-level generation jobs may have `script_id: null` because they run before a script exists
- source feedback notes are copied to the generation job payload and each returned idea
- same-brand analytics learnings are copied to the generation job payload and influence idea rationales when available
- the response contains the newly generated batch; use `GET /api/projects/:id/ideas` for the full saved list

Response excerpt:
```json
[
  {
    "id": "uuid",
    "project_id": "uuid",
    "suggested_title": "3 ways solo founders can apply Build a daily content loop this week",
    "hook": "What if build a daily content loop could save solo founders hours this week?",
    "angle": "Turn the project objective into a practical three-step playbook tailored to solo founders.",
    "rationale": "Fits the brand tone and gives short-form viewers a fast payoff.",
    "score": 91,
    "source_feedback_notes": "Make the next batch more specific to solo founders.",
    "status": "proposed"
  }
]
```

### `POST /api/ideas/:id/approve`
```json
{
  "feedback_notes": "Lean harder into the transformation angle."
}
```

### `POST /api/ideas/:id/reject`
```json
{
  "feedback_notes": "This angle is too broad for the first video."
}
```

### `POST /api/projects/:id/scripts/generate`
```json
{
  "source_feedback_notes": "Keep the pacing tight and practical."
}
```

Behavior note:
- creates a completed `generate_script` background job with lifecycle logs before returning the generated script
- the generation job is linked to the new script once the script and scene records are persisted
- source feedback notes are copied to the generation job payload and persisted on the script version
- same-brand analytics learnings are copied to the generation job payload and shape the script body, caption, and scene notes when available

Response excerpt:
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "content_idea_id": "uuid",
  "version_number": 1,
  "status": "draft",
  "hook": "What if build a daily content loop could save solo founders hours this week?",
  "body": "Solo founders usually hear that turning one workflow into multiple pieces of content needs a huge system...",
  "cta": "Close by ask for comments and invite viewers to test the first step before the day ends.",
  "title_options": [
    "3 ways solo founders can apply Build a daily content loop this week",
    "Build a daily content loop: the short playbook"
  ],
  "hashtags": ["#YoutubeShorts", "#AiProductivity", "#BuildADailyContentLoop"],
  "estimated_duration_seconds": 33,
  "scenes": [
    {
      "scene_order": 1,
      "title": "Hook",
      "narration_text": "What if build a daily content loop could save solo founders hours this week?",
      "overlay_text": "The fast promise",
      "image_prompt": "High-contrast cover frame...",
      "video_prompt": "Start with a punchy first-person clip..."
    }
  ]
}
```

### `GET /api/projects/:id/scripts/current`
- returns `null` when the project has no saved script yet

### `GET /api/scripts/:id/scenes`
- returns the persisted scene list for the requested script version

### `POST /api/scripts/:id/scenes/reorder`
```json
{
  "scene_ids": ["uuid-scene-4", "uuid-scene-1", "uuid-scene-2", "uuid-scene-3"]
}
```

- only works for the current script while the project is in `script_pending_approval`
- the current script must be `draft` or `rejected`
- the request must include every current scene exactly once
- successful reorders rewrite `scene_order` values contiguously from `1`
- returns the updated script with scenes in the saved order

### `POST /api/scripts/:id/approve`
```json
{
  "feedback_notes": "Approved for asset generation."
}
```

### `POST /api/scripts/:id/reject`
```json
{
  "feedback_notes": "The hook is fine, but the middle section needs a stronger proof point."
}
```

### `GET /api/projects/:id/approvals`
Response excerpt:
```json
[
  {
    "id": "uuid",
    "project_id": "uuid",
    "target_type": "script",
    "target_id": "uuid",
    "stage": "script",
    "decision": "approved",
    "feedback_notes": "Approved for asset generation.",
    "created_at": "2026-04-19T00:20:00Z"
  }
]
```

### `PATCH /api/scenes/:id`
```json
{
  "overlay_text": "Updated overlay guidance",
  "estimated_duration_seconds": 9,
  "notes": "Use a cleaner visual example."
}
```

- scene edits are limited to the current `draft` or `rejected` script during script approval
- changing scene duration updates the script-level `estimated_duration_seconds`

### `GET /api/scripts/:id/prompt-pack`
Response excerpt:
```json
{
  "script_id": "uuid",
  "project_id": "uuid",
  "brand_profile_id": "uuid",
  "analytics_learning_context": {
    "available": true,
    "source_count": 1,
    "guidance": ["engagement rate from Prior project: Reuse the stronger hook format."]
  },
  "channel_name": "Creator Lab",
  "target_platform": "youtube_shorts",
  "objective": "Prepare a worker-ready prompt pack",
  "script_status": "draft",
  "version_number": 1,
  "source_idea_title": "3 ways solo founders can apply Build a daily content loop this week",
  "scenes": [
    {
      "scene_id": "uuid",
      "scene_order": 1,
      "narration_input": "What if build a daily content loop could save solo founders hours this week?",
      "narration_direction": "Read in a direct tone for solo founders...",
      "image_generation_prompt": "Screen recordings. High-contrast cover frame...",
      "video_generation_prompt": "Screen recordings. Start with a punchy first-person clip..."
    }
  ]
}
```

### `POST /api/projects/:id/generate/audio`
```json
{
  "voice_label": "Warm guide"
}
```

Response excerpt:
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "script_id": "uuid",
  "job_type": "generate_audio_browser",
  "provider_name": "elevenlabs_web",
  "state": "queued",
  "progress_percent": 0,
  "payload_json": {
    "script_version": 1,
    "voice_label": "Warm guide",
    "scene_count": 4
  }
}
```

Behavior note:
- queueing narration promotes the project into `asset_generation` automatically when successful
- the API blocks duplicate active audio jobs for the same current script

### `POST /api/projects/:id/generate/visuals`
```json
{
  "scene_ids": ["uuid-optional", "uuid-optional"]
}
```

Response excerpt:
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "script_id": "uuid",
  "job_type": "generate_visuals_browser",
  "provider_name": "flow_web",
  "state": "queued",
  "payload_json": {
    "script_version": 1,
    "scene_count": 4,
    "scene_ids": ["uuid", "uuid"]
  }
}
```

Behavior note:
- omitting `scene_ids` queues every scene from the current approved script
- the API blocks duplicate active visual jobs for the same current script

### `GET /api/projects/:id/jobs`
- returns persisted queued generation jobs for the project, newest first

### `GET /api/projects/:id/activity`
Response excerpt:
```json
[
  {
    "source_id": "uuid",
    "source_type": "job_log",
    "activity_type": "job_failed",
    "title": "Job Failed",
    "description": "Provider timed out.",
    "level": "error",
    "metadata_json": {
      "background_job_id": "uuid",
      "generation_attempt_id": "uuid"
    },
    "created_at": "2026-04-19T06:00:00Z"
  }
]
```

Behavior note:
- returns the newest approval, job-log, and project-event activity for the project
- job-log entries include a `background_job_id` in metadata so the web app can link to the job detail screen

### `GET /api/projects/:id/export`
Response excerpt:
```json
{
  "exported_at": "2026-04-20T09:00:00Z",
  "project": {},
  "brand_profile": {},
  "ideas": [],
  "scripts": [],
  "approvals": [],
  "assets": [],
  "background_jobs": [],
  "publish_jobs": [],
  "analytics_snapshots": [],
  "insights": [],
  "project_events": []
}
```

Behavior note:
- export bundles are intended for local backup, debugging, and handoff
- generated artifact files are referenced by path; binary media is not embedded in the JSON response

### `GET /api/jobs/:id`
Response excerpt:
```json
{
  "job": {
    "id": "uuid",
    "project_id": "uuid",
    "script_id": "uuid",
    "job_type": "generate_audio_browser",
    "state": "failed",
    "progress_percent": 25,
    "error_message": "Provider timed out."
  },
  "generation_attempts": [
    {
      "id": "uuid",
      "background_job_id": "uuid",
      "scene_id": null,
      "state": "failed",
      "provider_name": "elevenlabs_web"
    }
  ],
  "related_assets": [
    {
      "id": "uuid",
      "asset_type": "narration_audio",
      "status": "failed",
      "generation_attempt_id": "uuid"
    }
  ],
  "job_logs": [
    {
      "id": "uuid",
      "event_type": "job_failed",
      "level": "error",
      "message": "Provider timed out.",
      "metadata_json": {}
    }
  ]
}
```

Behavior note:
- the route returns the job plus its generation attempts and related assets
- browser jobs resolve related assets through their generation attempts
- media jobs also resolve planned output assets from the job payload ids

### `POST /api/jobs/:id/cancel`
Behavior note:
- only `queued` and `waiting_external` jobs can be cancelled safely
- unfinished attempts move to `cancelled`
- unfinished related assets move to `failed`
- `running`, `completed`, `failed`, and already `cancelled` jobs return `409 Conflict`

### `POST /api/jobs/:id/retry`
Behavior note:
- only `failed` and `cancelled` jobs can be retried
- retry is available for worker-backed browser, media, publish, and analytics jobs; inline idea/script planning jobs should be re-run from the project action
- retry reuses the existing job, attempts, and related asset records
- retry resets job state to `queued`, clears job errors, clears stale timestamps, and resets related assets to `planned`
- retry enforces per-type execution attempt budgets: browser 4 total attempts, media 3, publish 2, analytics 2
- retry is blocked if another active job of the same type already exists for the same script
- completed jobs cannot be retried

### `POST /api/jobs/:id/resume`
Query parameters:
- `stale_after_minutes` defaults to `30`

Behavior note:
- only stale `running` browser and media jobs can be resumed
- recent running jobs return `409 Conflict` so an active worker is not interrupted accidentally
- resume resets the existing job to `queued`, clears stale running timestamps and errors, and preserves completed attempts and ready/rejected assets
- unfinished attempts return to `queued`; unfinished related assets return to `planned`
- resume writes a `job_resumed` warning log with the stale threshold and previous update timestamp

### `POST /api/jobs/:id/manual-intervention`
```json
{
  "reason": "Provider login expired and needs a browser session refresh."
}
```

Behavior note:
- marks the job `waiting_external`
- preserves the human-readable reason in `error_message`
- writes a `manual_intervention_required` job log entry for project activity and recovery queues

### `GET /api/operations/recovery`
Query parameters:
- `stale_after_minutes` defaults to `30`
- `limit` defaults to `20`

Response excerpt:
```json
{
  "failed_jobs": [
    {
      "job": {
        "id": "uuid",
        "state": "failed",
        "job_type": "generate_audio_browser"
      },
      "project_title": "3 AI automations I use daily",
      "project_status": "asset_generation",
      "latest_log_event_type": "job_failed",
      "latest_log_message": "Provider timed out."
    }
  ],
  "waiting_jobs": [],
  "stale_running_jobs": [],
  "quarantined_downloads": [],
  "duplicate_asset_warnings": [],
  "summary": {
    "failed_jobs": 1,
    "waiting_jobs": 0,
    "stale_running_jobs": 0,
    "quarantined_downloads": 0,
    "duplicate_asset_warnings": 0,
    "total_attention_items": 1
  }
}
```

Behavior note:
- failed jobs are jobs in `failed`
- waiting jobs are jobs in `waiting_external`
- stale running jobs are `running` jobs whose `updated_at` is older than `stale_after_minutes`
- quarantined downloads come from `downloads_quarantined` job logs
- duplicate asset warnings come from `duplicate_asset_detected` job logs

### `GET /api/operations/artifacts/retention-plan`
Query parameters:
- `limit` defaults to `50`

Response excerpt:
```json
{
  "candidates": [
    {
      "asset_id": "uuid",
      "project_id": "uuid",
      "project_title": "3 AI automations I use daily",
      "script_id": "uuid",
      "asset_type": "narration_audio",
      "status": "rejected",
      "file_path": "storage/projects/{project_id}/audio/rejected.wav",
      "file_exists": true,
      "size_bytes": 1048576,
      "reason": "Asset is rejected and can be moved to retention with a manifest.",
      "recommended_action": "move_to_retention",
      "safe_to_cleanup": true,
      "retention_manifest_path": "storage/projects/{project_id}/retention/asset-abcd1234-retention.json"
    }
  ],
  "summary": {
    "candidate_count": 1,
    "safe_candidate_count": 1,
    "total_reclaimable_bytes": 1048576
  }
}
```

Behavior note:
- this endpoint is planning-only and does not delete or move files
- rejected and failed assets with existing files inside the configured storage root are safe candidates for a future retention move
- missing files return `repair_missing_file` so metadata can be corrected before cleanup
- assets outside the configured storage root or attached to superseded scripts require `manual_review`
- safe candidates include a proposed retention manifest path under `storage/projects/{project_id}/retention`

### `GET /api/projects/:id/assets`
- returns planned and produced asset records for the project, including placeholder records created before worker execution starts

### `POST /api/projects/:id/assets/approve`
```json
{
  "feedback_notes": "These are good enough to move into the next stage."
}
```

Behavior note:
- this records an `assets`-stage approval for the current script
- the route requires the project to already be in `asset_pending_approval`

### `POST /api/projects/:id/assets/reject`
```json
{
  "feedback_notes": "The visuals need a clearer direction."
}
```

Behavior note:
- this records an `assets`-stage rejection for the current script
- ready assets from the current script are marked `rejected`
- the project moves back into `asset_generation` so you can queue another pass

### `GET /api/assets/:id`
- returns one owned asset record, including file path, mime type, duration, dimensions, checksum, scene id, and generation attempt id

### `POST /api/assets/:id/approve`
```json
{
  "feedback_notes": "This scene visual is approved."
}
```

Behavior note:
- records an `assets`-stage approval targeted at the individual asset
- requires the project to be in `asset_pending_approval` and the asset to be `ready`
- writes a project event so the asset decision appears in project activity

### `POST /api/assets/:id/reject`
```json
{
  "feedback_notes": "Regenerate this scene with clearer UI detail."
}
```

Behavior note:
- records an `assets`-stage rejection targeted at the individual asset
- marks the selected asset `rejected`
- moves the project back into `asset_generation` so a replacement can be queued

### `POST /api/assets/:id/regenerate`
```json
{
  "feedback_notes": "Try a more specific visual direction."
}
```

Behavior note:
- supports narration and scene image assets from the current script
- rejects the selected ready asset when needed, then queues a new browser generation job for the matching asset scope
- regeneration creates new generation attempts and new planned asset paths instead of overwriting the rejected artifact

### `GET /api/assets/:id/content`
- streams the stored asset file for preview
- access is limited to files inside the configured storage root

### `POST /api/projects/:id/compose/rough-cut`
Response excerpt:
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "script_id": "uuid",
  "job_type": "compose_rough_cut",
  "provider_name": "local_media",
  "state": "queued",
  "payload_json": {
    "script_version": 1,
    "scene_count": 4,
    "output_asset_id": "uuid",
    "subtitle_asset_id": "uuid",
    "preview_path": "storage/projects/{project_id}/rough-cuts/script-v1-rough-cut-abcd1234.html",
    "manifest_path": "storage/projects/{project_id}/rough-cuts/script-v1-rough-cut-abcd1234-manifest.json",
    "subtitle_path": "storage/projects/{project_id}/subtitles/script-v1-rough-cut-abcd1234.srt",
    "video_path": "storage/projects/{project_id}/rough-cuts/script-v1-rough-cut-abcd1234.mp4",
    "ffmpeg_command_path": "storage/projects/{project_id}/rough-cuts/script-v1-rough-cut-abcd1234-ffmpeg-command.json",
    "video_asset_id": "uuid-when-rendered",
    "ffmpeg_rendered": true
  }
}
```

Behavior note:
- the route requires the current asset set to have an approved `assets` review
- every scene must have a ready visual asset and the script must have a ready narration asset
- the media worker marks the rough-cut and subtitle assets ready, then promotes the project to `rough_cut_ready`

### `POST /api/projects/:id/final-video/approve`
Behavior note:
- requires the project to be in `final_pending_approval`
- uses the ready rough-cut artifact as the v1 final-review asset until final exports are implemented
- records a `final_video` approval against the asset
- moves the project to `ready_to_publish`

### `POST /api/projects/:id/final-video/reject`
Behavior note:
- requires the project to be in `final_pending_approval`
- records a `final_video` rejection against the review asset
- moves the project back to `rough_cut_ready`

### `POST /api/projects/:id/publish-jobs/prepare`
```json
{
  "platform": "youtube_shorts",
  "title": "Final publish title",
  "description": "Approved metadata for publishing.",
  "hashtags": ["#CreatorOS", "#Workflow"],
  "scheduled_for": null,
  "idempotency_key": "project-script-publish-prep"
}
```

Behavior note:
- requires `ready_to_publish` and an approved final-video review
- creates a `pending_approval` publish job linked to the final-review asset
- blocks duplicate active publish jobs for the current script
- returns the existing publish job when the same idempotency key is reused

### `GET /api/projects/:id/publish-jobs`
- returns publish jobs for the project, newest first

### `POST /api/publish-jobs/:id/approve`
Behavior note:
- records a `publish` approval against the publish job
- moves the publish job from `pending_approval` to `approved`
- does not publish or schedule content by itself

### `PATCH /api/publish-jobs/:id/metadata`
```json
{
  "title": "Sharper publish title",
  "description": "Updated publish description.",
  "hashtags": ["CreatorOS", "#Workflow"],
  "scheduled_for": "2030-01-02T03:00:00+00:00",
  "thumbnail_asset_id": "uuid-or-null",
  "platform_settings": {
    "privacy": "private",
    "playlist_id": "optional"
  },
  "change_notes": "Tightened the hook before publish approval."
}
```

Behavior note:
- allows edits only while a publish job is `pending_approval` or `approved`
- normalizes hashtags by adding missing `#` prefixes and dropping blanks/duplicates
- stores selected ready thumbnail or scene-image asset IDs from the same script in `metadata_json.thumbnail_asset_id`
- stores platform-specific upload settings in `metadata_json.platform_settings`
- records a project activity event for metadata edits
- moves an already `approved` publish job back to `pending_approval` when posted metadata changes
- blocks metadata edits after the job is `scheduled`, `published`, `failed`, or `cancelled`

### `POST /api/publish-jobs/:id/queue`
Behavior note:
- requires the publish job to be `approved` or `scheduled`
- requires the linked final-review asset to still be ready
- creates a `publish_content` background job using the v1 `manual_publish_handoff` adapter
- blocks duplicate queued, running, or waiting-external publish handoff jobs for the same publish job
- writes the planned handoff path to the job payload under `handoff_path`
- the publisher worker generates the handoff JSON and moves the job to `waiting_external`
- the job is completed only after the user records manual publish completion with `mark-published`

### `POST /api/publish-jobs/:id/schedule`
```json
{
  "scheduled_for": "2030-01-01T00:00:00+00:00"
}
```

Behavior note:
- requires an approved publish job
- moves the publish job to `scheduled`
- moves the project to `scheduled`

### `POST /api/publish-jobs/:id/mark-published`
```json
{
  "external_post_id": "yt-short-123",
  "manual_publish_notes": "Published manually after final approval."
}
```

Behavior note:
- records manual publish completion after explicit publish approval
- moves the publish job to `published`
- moves the project to `published`

### `POST /api/publish-jobs/:id/sync-analytics`
```json
{
  "views": 1000,
  "likes": 90,
  "comments": 12,
  "shares": 8,
  "saves": 5,
  "watch_time_seconds": 18500,
  "ctr": 0.041,
  "avg_view_duration": 18.5,
  "retention_json": {
    "three_second_hold": 0.76
  }
}
```

Behavior note:
- requires the publish job to already be marked `published`
- stores a traceable analytics snapshot for the project and publish job
- generates first-pass insights from engagement and average-view-duration signals
- retained as a direct compatibility path; the project UI uses the queued analytics endpoint

### `POST /api/publish-jobs/:id/analytics/queue`
```json
{
  "views": 1000,
  "likes": 90,
  "comments": 12,
  "shares": 8,
  "saves": 5,
  "watch_time_seconds": 18500,
  "ctr": 0.041,
  "avg_view_duration": 18.5,
  "retention_json": {
    "three_second_hold": 0.76
  }
}
```

Behavior note:
- requires the publish job to already be marked `published`
- creates a `sync_analytics` background job with the supplied metric payload
- blocks duplicate queued, running, or waiting-external analytics sync jobs for the same publish job
- the analytics worker persists the snapshot, generates insights, and stores `analytics_snapshot_id` in the completed job payload

### `GET /api/projects/:id/analytics`
Response excerpt:
```json
{
  "snapshots": [
    {
      "id": "uuid",
      "publish_job_id": "uuid",
      "views": 1000,
      "likes": 90,
      "comments": 12,
      "shares": 8,
      "avg_view_duration": 18.5
    }
  ],
  "insights": [
    {
      "id": "uuid",
      "insight_type": "engagement_rate",
      "summary": "Engagement is strong for this post...",
      "confidence_score": 0.78
    }
  ]
}
```

### `GET /api/analytics/account`
Response excerpt:
```json
{
  "overview": {
    "published_posts": 4,
    "total_views": 12500,
    "total_engagements": 930,
    "average_engagement_rate": 0.0744,
    "average_view_duration": 18.2,
    "top_platform": "youtube_shorts"
  },
  "top_posts": [
    {
      "project_id": "uuid",
      "publish_job_id": "uuid",
      "title": "Account analytics source",
      "views": 1500,
      "engagement_rate": 0.1067
    }
  ],
  "duration_buckets": [
    {
      "key": "20_to_34s",
      "label": "20-34 seconds",
      "publish_count": 3,
      "average_engagement_rate": 0.08
    }
  ]
}
```

Behavior note:
- uses the latest analytics snapshot per publish job so repeated syncs do not double-count totals
- groups performance by hook, duration bucket, posting window, voice label, and platform/content type
- powers the account-level analytics cards on the dashboard

## Planned Next Endpoints
- `POST /api/scripts/:id/regenerate`

### Rough Cut / Final Video
- `POST /api/projects/:id/finalize`
- `GET /api/projects/:id/exports`

## Example Project State Machine
`draft -> idea_pending_approval -> script_pending_approval -> asset_generation -> asset_pending_approval -> rough_cut_ready -> final_pending_approval -> ready_to_publish -> scheduled|published|archived`

## Current Guarded Transition Rules
- the API only allows explicit transitions between known adjacent states
- invalid jumps return `409 Conflict`
- moving into `script_pending_approval` requires a generated script to exist
- moving into `asset_generation` now requires the current script version to be explicitly approved
- scene edits are only allowed while the current script is in `draft` or `rejected` state during script approval
- scene reorders follow the same script approval gate and prompt packs reject non-contiguous scene order data
- moving into `rough_cut_ready` requires an approved asset set and a ready rough-cut artifact
- moving into `ready_to_publish` requires final-video approval
- moving into `scheduled` requires a scheduled publish job
- moving into `published` requires a publish job marked as published
- archived projects cannot transition further in the current implementation

## Error Model
All API errors now return a stable envelope, and the same request ID is also returned as the `X-Request-ID` response header:
```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human readable message",
    "details": {},
    "request_id": "request-id-or-null"
  }
}
```

Common error codes:
- `NOT_FOUND` for missing resources
- `CONFLICT` for invalid workflow transitions or blocked operations
- `VALIDATION_ERROR` for request body, path, or query validation failures
- `INTERNAL_SERVER_ERROR` for unexpected failures

Validation errors include FastAPI/Pydantic field diagnostics in `error.details.validation_errors`.

## Idempotency Rules
- publish preparation supports idempotency keys
- asset registration should be file-hash aware
- regeneration actions create a new attempt, never overwrite previous attempts
