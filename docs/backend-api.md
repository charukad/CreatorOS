# Backend API Design

## API Style
- REST for v1
- JSON request/response
- background jobs returned as task references
- explicit status enums

## Personal-Use Bootstrap Note
- until auth/session is implemented, v1 local development can attach brand profiles and projects to a single configured default user

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

## Implemented v0 Foundation Payloads
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

### Ideas
- `POST /api/projects/:id/ideas/generate`
- `POST /api/ideas/:id/approve`
- `POST /api/ideas/:id/reject`

### Scripts
- `POST /api/projects/:id/scripts/generate`
- `GET /api/projects/:id/scripts/current`
- `POST /api/scripts/:id/approve`
- `POST /api/scripts/:id/reject`
- `POST /api/scripts/:id/regenerate`

### Scenes
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
