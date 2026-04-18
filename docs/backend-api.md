# Backend API Design

## API Style
- REST for v1
- JSON request/response
- background jobs returned as task references
- explicit status enums

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
