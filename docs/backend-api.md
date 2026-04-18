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
- queue-backed job submission for generation steps is still planned, but the persisted workflow path is already live

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
- `POST /api/projects/:id/ideas/generate`
- `GET /api/projects/:id/scripts/current`
- `POST /api/projects/:id/scripts/generate`

### Ideas
- `POST /api/ideas/:id/approve`

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

## Planned Next Endpoints
- `POST /api/ideas/:id/reject`
- `POST /api/scripts/:id/approve`
- `POST /api/scripts/:id/reject`
- `POST /api/scripts/:id/regenerate`
- `GET /api/scripts/:id/scenes`
- `PATCH /api/scenes/:id`

### Generation Jobs
- `POST /api/projects/:id/generate/audio`
- `POST /api/projects/:id/generate/visuals`
- `GET /api/jobs/:id`

### Assets
- `GET /api/projects/:id/assets`
- `POST /api/assets/:id/approve`
- `POST /api/assets/:id/reject`
- `POST /api/assets/:id/regenerate`

### Rough Cut / Final Video
- `POST /api/projects/:id/compose/rough-cut`
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
- moving into `script_pending_approval` or `asset_generation` now requires a generated script to exist
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
