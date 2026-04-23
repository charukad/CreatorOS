import type {
  ArtifactTraceability,
  ComposeRoughCutQueuePayload,
  GenerateAudioQueuePayload,
  GenerateIdeasQueuePayload,
  GenerateScriptQueuePayload,
  GenerateVisualsQueuePayload,
  ScriptPromptPackContract,
  TimelineManifestContract,
} from "./contracts";
import {
  validateArtifactTraceability,
  validatePromptPackContract,
  validateQueuePayload,
  validateTimelineManifestContract,
} from "./contracts";

const now = "2026-04-20T00:00:00.000Z";

export const sampleArtifactTraceability = {
  project_id: "project-123",
  script_id: "script-123",
  scene_id: "scene-001",
  generation_attempt_id: "attempt-123",
  background_job_id: "job-123",
  asset_id: "asset-123",
  asset_type: "scene_image",
  provider_name: "flow_web",
  file_path: "storage/projects/project-123/scenes/scene-01-attempt-123.svg",
} satisfies ArtifactTraceability;

export const sampleGenerateIdeasPayload = {
  job_type: "generate_ideas",
  project_id: "project-123",
  correlation_id: "correlation-ideas",
  brand_profile_id: "brand-123",
  target_platform: "youtube_shorts",
  objective: "Turn a workflow into a short-form content system",
  source_feedback_notes: "Make it more tactical.",
  idea_count: 3,
  idea_ids: ["idea-1", "idea-2", "idea-3"],
} satisfies GenerateIdeasQueuePayload;

export const sampleGenerateScriptPayload = {
  job_type: "generate_script",
  project_id: "project-123",
  correlation_id: "correlation-script",
  approved_idea_id: "idea-1",
  brand_profile_id: "brand-123",
  source_feedback_notes: "Make the hook sharper.",
  script_id: "script-123",
  script_version: 1,
  scene_count: 2,
} satisfies GenerateScriptQueuePayload;

export const sampleGenerateAudioPayload = {
  job_type: "generate_audio_browser",
  project_id: "project-123",
  correlation_id: "correlation-audio",
  script_id: "script-123",
  script_version: 1,
  voice_label: "Warm guide",
  estimated_duration_seconds: 24,
  scene_count: 2,
  narration_segments: [
    {
      scene_id: "scene-001",
      scene_order: 1,
      title: "Hook",
      narration_input: "What if your content workflow could become daily shorts?",
      narration_direction: "Read in a direct tone.",
      estimated_duration_seconds: 10,
    },
    {
      scene_id: "scene-002",
      scene_order: 2,
      title: "Proof",
      narration_input: "Start with one promise, one proof point, and one CTA.",
      narration_direction: "Read in a direct tone.",
      estimated_duration_seconds: 14,
    },
  ],
} satisfies GenerateAudioQueuePayload;

export const sampleGenerateVisualsPayload = {
  job_type: "generate_visuals_browser",
  project_id: "project-123",
  correlation_id: "correlation-visuals",
  script_id: "script-123",
  script_version: 1,
  scene_count: 2,
  scene_ids: ["scene-001", "scene-002"],
  scenes: [
    {
      scene_id: "scene-001",
      scene_order: 1,
      title: "Hook",
      estimated_duration_seconds: 10,
      image_generation_prompt: "High contrast workflow dashboard cover frame.",
      video_generation_prompt: "Fast screen recording intro with bold overlay.",
    },
    {
      scene_id: "scene-002",
      scene_order: 2,
      title: "Proof",
      estimated_duration_seconds: 14,
      image_generation_prompt: "Clean proof-point workspace visual.",
      video_generation_prompt: "Zoom through a three-step workflow board.",
    },
  ],
} satisfies GenerateVisualsQueuePayload;

export const sampleComposeRoughCutPayload = {
  job_type: "compose_rough_cut",
  project_id: "project-123",
  correlation_id: "correlation-media",
  script_id: "script-123",
  script_version: 1,
  scene_count: 2,
  preview_path: "storage/projects/project-123/rough-cuts/script-v1-preview.html",
  manifest_path: "storage/projects/project-123/rough-cuts/script-v1-manifest.json",
  subtitle_path: "storage/projects/project-123/subtitles/script-v1.srt",
  output_asset_id: "asset-rough-cut",
  subtitle_asset_id: "asset-subtitle",
  video_path: "storage/projects/project-123/rough-cuts/script-v1.mp4",
  video_asset_id: "asset-video",
  ffmpeg_command_path: "storage/projects/project-123/rough-cuts/script-v1-command.json",
} satisfies ComposeRoughCutQueuePayload;

export const samplePromptPack = {
  script_id: "script-123",
  project_id: "project-123",
  brand_profile_id: "brand-123",
  brand_context: {
    identity: {
      channel_name: "Creator Lab",
    },
  },
  analytics_learning_context: {
    available: true,
    brand_profile_id: "brand-123",
    target_project_id: "project-123",
    source_count: 1,
    guidance: [
      "engagement rate from Prior project: Reuse the stronger hook format (confidence 78%).",
    ],
    items: [
      {
        insight_id: "insight-123",
        source_project_id: "project-001",
        source_project_title: "Prior project",
        is_current_project: false,
        publish_job_id: "publish-123",
        analytics_snapshot_id: "snapshot-123",
        insight_type: "engagement_rate",
        summary: "Reuse the stronger hook format.",
        evidence: { engagement_rate: 0.12 },
        confidence_score: 0.78,
        created_at: "2026-01-01T00:00:00Z",
      },
    ],
  },
  channel_name: "Creator Lab",
  target_platform: "youtube_shorts",
  objective: "Turn a workflow into a short-form content system",
  script_status: "draft",
  version_number: 1,
  source_idea_title: "3 ways creators can apply the workflow this week",
  caption: "A compact workflow for daily short-form publishing.",
  hashtags: ["#CreatorOS", "#Workflow"],
  title_options: ["The short content workflow", "Turn one workflow into shorts"],
  scenes: [
    {
      scene_id: "scene-001",
      scene_order: 1,
      title: "Hook",
      estimated_duration_seconds: 10,
      overlay_text: "The fast promise",
      narration_input: "What if your content workflow could become daily shorts?",
      narration_direction: "Read in a direct tone.",
      image_generation_prompt: "High contrast workflow dashboard cover frame.",
      video_generation_prompt: "Fast screen recording intro with bold overlay.",
      notes: null,
    },
    {
      scene_id: "scene-002",
      scene_order: 2,
      title: "Proof",
      estimated_duration_seconds: 14,
      overlay_text: "One promise, one proof point, one CTA",
      narration_input: "Start with one promise, one proof point, and one CTA.",
      narration_direction: "Read in a direct tone.",
      image_generation_prompt: "Clean proof-point workspace visual.",
      video_generation_prompt: "Zoom through a three-step workflow board.",
      notes: null,
    },
  ],
} satisfies ScriptPromptPackContract;

export const sampleTimelineManifest = {
  manifest_version: 1,
  project_id: "project-123",
  project_title: "CreatorOS demo",
  script_id: "script-123",
  script_version: 1,
  generated_at: now,
  total_duration_seconds: 24,
  timing_strategy: {
    source: "narration_audio_wav",
    scale_factor: 1,
  },
  narration_asset: {
    asset_id: "asset-audio",
    file_path: "storage/projects/project-123/audio/script-v1.wav",
    asset_type: "narration_audio",
    provider_name: "elevenlabs_web",
    duration_seconds: 24,
    probed_duration_seconds: 24,
  },
  subtitle_asset: {
    asset_id: "asset-subtitle",
    file_path: "storage/projects/project-123/subtitles/script-v1.srt",
    asset_type: "subtitle_file",
    provider_name: "local_media",
    duration_seconds: 24,
  },
  scenes: [
    {
      scene_id: "scene-001",
      scene_order: 1,
      title: "Hook",
      start_seconds: 0,
      end_seconds: 10,
      duration_seconds: 10,
      estimated_duration_seconds: 10,
      narration_text: "What if your content workflow could become daily shorts?",
      overlay_text: "The fast promise",
      visual_asset: {
        asset_id: "asset-scene-1",
        file_path: "storage/projects/project-123/scenes/scene-01.svg",
        asset_type: "scene_image",
        provider_name: "flow_web",
      },
    },
    {
      scene_id: "scene-002",
      scene_order: 2,
      title: "Proof",
      start_seconds: 10,
      end_seconds: 24,
      duration_seconds: 14,
      estimated_duration_seconds: 14,
      narration_text: "Start with one promise, one proof point, and one CTA.",
      overlay_text: "One promise, one proof point, one CTA",
      visual_asset: {
        asset_id: "asset-scene-2",
        file_path: "storage/projects/project-123/scenes/scene-02.svg",
        asset_type: "scene_image",
        provider_name: "flow_web",
      },
    },
  ],
} satisfies TimelineManifestContract;

export function assertValidSharedContractFixtures(): void {
  const errors = [
    ...validateArtifactTraceability(sampleArtifactTraceability),
    ...validateQueuePayload(sampleGenerateIdeasPayload),
    ...validateQueuePayload(sampleGenerateScriptPayload),
    ...validateQueuePayload(sampleGenerateAudioPayload),
    ...validateQueuePayload(sampleGenerateVisualsPayload),
    ...validateQueuePayload(sampleComposeRoughCutPayload),
    ...validatePromptPackContract(samplePromptPack),
    ...validateTimelineManifestContract(sampleTimelineManifest),
  ];

  if (errors.length > 0) {
    throw new Error(`Shared contract fixtures are invalid: ${errors.join("; ")}`);
  }
}
