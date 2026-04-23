# Shared Contracts

CreatorOS keeps cross-service handoff contracts in `packages/shared/src/contracts.ts`.
These contracts are TypeScript-first because the web app and shared package already consume
`@creatoros/shared`, while the API mirrors the same shapes with Pydantic response models.

## Contract Groups

### Core Resource Contracts
- `BrandProfileContract`
- `ProjectContract`
- `ContentIdeaContract`
- `ProjectScriptContract`
- `SceneContract`
- `GenerationAttemptContract`
- `AssetContract`
- `ApprovalContract`
- `BackgroundJobContract`
- `PublishJobContract`
- `AnalyticsSnapshotContract`
- `AnalyticsLearningContextContract`

### Traceability Contracts
- `TraceabilityFields` carries shared IDs for project, script, scene, generation attempt, job,
  and asset relationships.
- `ArtifactTraceability` is the minimum artifact-level traceability shape.
- Scene-level visual artifacts must include `scene_id`.
- Generated artifacts must include `generation_attempt_id`.

### Queue Payload Contracts
- `GenerateIdeasQueuePayload`
- `GenerateScriptQueuePayload`
- `GenerateAudioQueuePayload`
- `GenerateVisualsQueuePayload`
- `ComposeRoughCutQueuePayload`
- `IngestDownloadQueuePayload`
- `FinalExportQueuePayload`
- `PublishContentQueuePayload`
- `SyncAnalyticsQueuePayload`

The implemented job types are the current `BackgroundJobType` union. Planned payloads are included
so queue and worker boundaries do not need to be redesigned when final export is added. `publish_content`
is implemented in v1 as a manual publish handoff job, and `sync_analytics` is implemented in v1
as a queued manual metric snapshot job. Live platform upload and analytics polling adapters are still
planned.

### Prompt Pack Contracts
- `ScriptPromptPackContract` is the worker-ready script handoff.
- `ScenePromptPackContract` is the per-scene narration and visual generation input.
- Prompt packs include `analytics_learning_context` so browser/media workers and future provider
  adapters can see the performance learnings that shaped the generated script.
- Prompt packs must include contiguous `scene_order` values starting at `1`.

### Timeline Manifest Contracts
- `TimelineManifestContract` documents the rough-cut manifest sidecar produced by the media worker.
- `TimelineSceneManifest` captures scene order, timeline boundaries, narration, overlay text, and
  resolved visual asset references.
- Timeline scenes must be contiguous, positive-duration, and end exactly at
  `total_duration_seconds`.

## Validation Helpers

`packages/shared/src/contracts.ts` includes lightweight runtime validators:
- `validateArtifactTraceability`
- `validateQueuePayload`
- `validatePromptPackContract`
- `validateTimelineManifestContract`

These helpers are intentionally dependency-free. They are not a replacement for Pydantic or
database constraints, but they give the shared package a stable contract sanity check for UI and
worker handoffs.

## Fixtures

`packages/shared/src/contract-fixtures.ts` exports valid sample payloads for:
- artifact traceability
- idea/script/audio/visual/media queue jobs
- prompt packs
- timeline manifests

Run `pnpm --filter @creatoros/shared typecheck` to validate that fixtures and shared contracts
remain type-compatible.
