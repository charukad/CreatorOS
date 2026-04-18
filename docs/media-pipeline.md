# Media Pipeline

## Goal
Turn approved script + generated assets into an automatically assembled short-form video.

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

## Final Export Rules
- selectable aspect ratio
- H.264 mp4 in v1
- save subtitles as separate artifact where possible
- preserve timeline manifest for later edits/regeneration

## FFmpeg Responsibilities
- concat scene media
- overlay narration
- burn subtitles when requested
- normalize audio levels if needed
- export preview/final deliverables
