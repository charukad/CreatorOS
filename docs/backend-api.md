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
- after asset approval, `compose_rough_cut` queues a media-worker job that writes a timeline manifest and rough-cut preview artifact
- Redis-backed execution, retries, and worker progress updates are still planned

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
- `GET /api/projects/:id/approvals`
- `GET /api/projects/:id/jobs`
- `GET /api/projects/:id/assets`
- `POST /api/projects/:id/assets/approve`
- `POST /api/projects/:id/assets/reject`
- `POST /api/projects/:id/compose/rough-cut`
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
    "preview_path": "storage/projects/{project_id}/rough-cuts/script-v1-rough-cut-abcd1234.html",
    "manifest_path": "storage/projects/{project_id}/rough-cuts/script-v1-rough-cut-abcd1234-manifest.json"
  }
}
```

Behavior note:
- the route requires the current asset set to have an approved `assets` review
- every scene must have a ready visual asset and the script must have a ready narration asset
- the media worker marks the rough-cut asset ready and promotes the project to `rough_cut_ready`

## Planned Next Endpoints
- `POST /api/scripts/:id/regenerate`

### Generation Jobs
- `GET /api/jobs/:id`

### Assets
- `GET /api/projects/:id/assets`
- `POST /api/assets/:id/approve`
- `POST /api/assets/:id/reject`
- `POST /api/assets/:id/regenerate`

### Rough Cut / Final Video
- `POST /api/projects/:id/finalize`
- `GET /api/projects/:id/exports`

### Publishing
- `POST /api/projects/:id/publish/prepare`
- `POST /api/publish-jobs/:id/approve`
- `POST /api/publish-jobs/:id/schedule`
- `POST /api/publish-jobs/:id/publish-now`
- `GET /api/publish-jobs/:id`

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
