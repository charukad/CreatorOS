# Media Pipeline

## Goal
Turn approved script + generated assets into an automatically assembled short-form video.

## Current Implementation Note
- after asset approval, the API can queue a `compose_rough_cut` background job
- the media worker resolves the latest ready narration asset and one ready visual per scene
- the media worker probes WAV narration duration and uses it as the timeline timing anchor
- the worker writes a deterministic audio-anchored timeline manifest sidecar file
- the timeline manifest contract is defined in `packages/shared/src/contracts.ts`
- the first rough-cut output is an HTML preview artifact registered as a `rough_cut` asset
- the worker also writes an SRT subtitle sidecar registered as a `subtitle_file` asset
- the worker writes a JSON FFmpeg command-plan sidecar for the future MP4 render
- optional FFmpeg-based MP4 rendering is available behind `MEDIA_ENABLE_FFMPEG_RENDER=true`
- timeout-style FFmpeg render failures are retried once inline before the media job fails
- real local FFmpeg install/manual MP4 QA, transitions, and final export are still pending

## Inputs
- approved script
- ordered scene records
- narration audio
- approved video/image assets
- overlay text
- subtitle preferences
- export profile (9:16, 16:9, etc.)

## Pipeline Steps
1. Load project manifest.
2. Resolve approved assets for each scene.
3. Build timeline using scene order and target durations.
4. Align narration audio with scene durations.
5. Generate subtitles/captions if enabled.
6. Add overlays/transitions.
7. Export rough cut.
8. Export final cut after approval.

## Scene Manifest Example
The shared TypeScript contract is `TimelineManifestContract`. The worker-side Python validator
continues to enforce the same core rules at runtime.

```json
{
  "project_id": "uuid",
  "audio_asset_id": "uuid",
  "scenes": [
    {
      "scene_id": "uuid-1",
      "start": 0,
      "end": 4.2,
      "asset_id": "asset-1",
      "overlay_text": "Hook text"
    }
  ]
}
```

## Rough Cut Rules
- use only approved assets by default
- trim/loop scene visuals if duration mismatch occurs
- preserve audio as primary timing anchor
- render a preview quickly before final export
- v1 preview jobs require a ready narration asset and a ready visual asset for every scene
- `rough_cut_ready` should only be reached after the media worker creates a rough-cut artifact
- SRT subtitles are derived from ordered scene narration and scene duration boundaries
- when WAV duration is available, scene durations are proportionally scaled to match narration
- timeline manifests are validated for contiguous scene timing and valid visual paths before artifacts are marked ready

## Final Export Rules
- selectable aspect ratio
- H.264 mp4 in v1
- save subtitles as separate artifact where possible
- preserve timeline manifest for later edits/regeneration

## FFmpeg Responsibilities
- concat scene media
- overlay narration
- draw scene overlay text into each visual segment
- burn subtitles when requested
- normalize audio levels if needed
- export preview/final deliverables

## Current FFmpeg Command Plan
- command builders live under `workers/media/ffmpeg`
- rough-cut jobs write an auditable command plan beside the manifest
- the planned command loops static images, trims/loops video clips to the timeline duration, draws scene overlay text, applies first-pass fade in/out transitions, concats the video streams, maps the narration audio, and applies the generated SRT subtitle file
- command-plan sidecars include export profile settings, inputs, outputs, and the full FFmpeg argv list for audit/debugging
- actual execution remains disabled until FFmpeg is installed and `MEDIA_ENABLE_FFMPEG_RENDER=true`
- when execution succeeds, the worker registers a separate `video/mp4` rough-cut asset
