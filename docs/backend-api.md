# Backend API Design

## API Style
- REST for v1
- JSON request/response
- background jobs returned as task references
- explicit status enums

## Personal-Use Bootstrap Note
- until auth/session is implemented, v1 local development can attach brand profiles and projects to a single configured default user

## Current Workflow Note
- the current idea and script workflow runs synchronously inside the API as a local deterministic generator
- asset-generation planning is now persisted through queued job records, generation attempts, and planned assets
- the browser worker can now consume queued narration and visual jobs in local `dry_run` mode and mark assets ready
- when the required assets finish generating, the project moves into `asset_pending_approval` for explicit review
- after asset approval, `compose_rough_cut` queues a media-worker job that probes WAV narration duration and writes an audio-anchored timeline manifest, rough-cut preview artifact, SRT subtitle sidecar asset, FFmpeg command-plan sidecar, and optionally a `video/mp4` rough-cut asset when FFmpeg rendering is enabled
- job detail, project activity, job timeline logs, safe cancel, and safe retry endpoints are implemented for operator recovery
- final-video approval and publish-job preparation are implemented with explicit publish approval before scheduling or manual published completion
- Redis-backed execution, automated retry policy, and live worker progress updates are still planned

## Core Resources
### Brand Profiles
- `POST /api/brand-profiles`
- `GET /api/brand-profiles/:id`
- `PATCH /api/brand-profiles/:id`
- `GET /api/brand-profiles`

### Projects
- `POST /api/projects`
- `GET /api/projects/:id`
- `PATCH /api/projects/:id`
- `GET /api/projects`
- `POST /api/projects/:id/transition`
- `GET /api/projects/:id/ideas`
- `GET /api/projects/:id/activity`
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
- `GET /api/scripts/:id/prompt-pack`

### Scenes
- `PATCH /api/scenes/:id`

### Asset Files
- `GET /api/assets/:id/content`

### Jobs
- `GET /api/jobs/:id`
- `POST /api/jobs/:id/cancel`
- `POST /api/jobs/:id/retry`

### Publish Jobs
- `POST /api/publish-jobs/:id/approve`
- `POST /api/publish-jobs/:id/schedule`
- `POST /api/publish-jobs/:id/mark-published`

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
    "platforms": ["youtube_shorts", "tiktok"]
  }
}
```

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

### `POST /api/projects/:id/ideas/generate`
Request body:
```json
{}
```

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

### `GET /api/scripts/:id/prompt-pack`
Response excerpt:
```json
{
  "script_id": "uuid",
  "project_id": "uuid",
  "brand_profile_id": "uuid",
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
- returns the newest approval and job-log activity for the project
- job-log entries include a `background_job_id` in metadata so the web app can link to the job detail screen

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
- retry reuses the existing job, attempts, and related asset records
- retry resets job state to `queued`, clears job errors, clears stale timestamps, and resets related assets to `planned`
- retry is blocked if another active job of the same type already exists for the same script
- completed jobs cannot be retried

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

## Planned Next Endpoints
- `POST /api/scripts/:id/regenerate`

### Assets
- `GET /api/projects/:id/assets`
- `POST /api/assets/:id/approve`
- `POST /api/assets/:id/reject`
- `POST /api/assets/:id/regenerate`

### Rough Cut / Final Video
- `POST /api/projects/:id/finalize`
- `GET /api/projects/:id/exports`

### Analytics
- `POST /api/publish-jobs/:id/sync-analytics`
- `GET /api/projects/:id/analytics`
- `GET /api/insights`

## Example Project State Machine
`draft -> idea_pending_approval -> script_pending_approval -> asset_generation -> asset_pending_approval -> rough_cut_ready -> final_pending_approval -> ready_to_publish -> scheduled|published|archived`

## Current Guarded Transition Rules
- the API only allows explicit transitions between known adjacent states
- invalid jumps return `409 Conflict`
- moving into `script_pending_approval` requires a generated script to exist
- moving into `asset_generation` now requires the current script version to be explicitly approved
- scene edits are only allowed while the current script is in `draft` or `rejected` state during script approval
- moving into `rough_cut_ready` requires an approved asset set and a ready rough-cut artifact
- archived projects cannot transition further in the current implementation

## Error Model
All errors should return:
```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

## Idempotency Rules
- publish scheduling endpoints should support idempotency keys
- asset registration should be file-hash aware
- regeneration actions create a new attempt, never overwrite previous attempts
