import type {
  ApprovalDecision,
  ApprovalStage,
  ApprovalTargetType,
  AssetStatus,
  AssetType,
  BackgroundJobState,
  BackgroundJobType,
  ContentIdeaStatus,
  ProjectStatus,
  ProviderName,
  PublishAdapterName,
  PublishJobStatus,
  ScriptStatus,
} from "./workflow";
import { backgroundJobTypes } from "./workflow";

export type UUID = string;
export type ISODateTime = string;
export type StoragePath = string;

export type Nullable<T> = T | null;

export type TraceabilityFields = {
  project_id: UUID;
  script_id?: Nullable<UUID>;
  scene_id?: Nullable<UUID>;
  generation_attempt_id?: Nullable<UUID>;
  background_job_id?: Nullable<UUID>;
  asset_id?: Nullable<UUID>;
};

export type ArtifactTraceability = TraceabilityFields & {
  asset_type: AssetType;
  file_path: StoragePath;
  provider_name?: Nullable<ProviderName>;
};

export type BrandProfileContract = {
  id: UUID;
  user_id: UUID;
  channel_name: string;
  niche: string;
  target_audience: string;
  tone: string;
  hook_style: string;
  cta_style: string;
  visual_style: string;
  posting_preferences_json: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type ProjectContract = {
  id: UUID;
  user_id: UUID;
  brand_profile_id: UUID;
  title: string;
  target_platform: string;
  objective: string;
  notes: Nullable<string>;
  status: ProjectStatus;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type ContentIdeaContract = {
  id: UUID;
  user_id: UUID;
  project_id: UUID;
  topic: string;
  suggested_title: string;
  hook: string;
  angle: string;
  rationale: string;
  score: number;
  source_feedback_notes: Nullable<string>;
  status: ContentIdeaStatus;
  feedback_notes: Nullable<string>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type IdeaResearchSnapshotContract = {
  id: UUID;
  user_id: UUID;
  project_id: UUID;
  focus_topic: Nullable<string>;
  source_feedback_notes: Nullable<string>;
  summary: string;
  trend_observations_json: string[];
  competitor_angles_json: string[];
  posting_strategies_json: string[];
  recommended_topics_json: string[];
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type SceneContract = {
  id: UUID;
  script_id: UUID;
  scene_order: number;
  title: string;
  narration_text: string;
  overlay_text: string;
  image_prompt: string;
  video_prompt: string;
  estimated_duration_seconds: number;
  notes: Nullable<string>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type ProjectScriptContract = {
  id: UUID;
  user_id: UUID;
  project_id: UUID;
  content_idea_id: UUID;
  version_number: number;
  status: ScriptStatus;
  hook: string;
  body: string;
  cta: string;
  full_script: string;
  caption: string;
  title_options: string[];
  hashtags: string[];
  estimated_duration_seconds: number;
  source_feedback_notes: Nullable<string>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  scenes: SceneContract[];
};

export type GenerationAttemptContract = TraceabilityFields & {
  id: UUID;
  user_id: UUID;
  project_id: UUID;
  script_id: UUID;
  background_job_id: UUID;
  scene_id: Nullable<UUID>;
  provider_name: ProviderName;
  state: BackgroundJobState;
  input_payload_json: Record<string, unknown>;
  error_message: Nullable<string>;
  started_at: Nullable<ISODateTime>;
  finished_at: Nullable<ISODateTime>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type AssetContract = TraceabilityFields & {
  id: UUID;
  user_id: UUID;
  project_id: UUID;
  script_id: UUID;
  scene_id: Nullable<UUID>;
  generation_attempt_id: Nullable<UUID>;
  asset_type: AssetType;
  status: AssetStatus;
  provider_name: Nullable<ProviderName>;
  file_path: Nullable<StoragePath>;
  mime_type: Nullable<string>;
  duration_seconds: Nullable<number>;
  width: Nullable<number>;
  height: Nullable<number>;
  checksum: Nullable<string>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type ApprovalContract = {
  id: UUID;
  user_id: UUID;
  project_id: UUID;
  target_type: ApprovalTargetType;
  target_id: UUID;
  stage: ApprovalStage;
  decision: ApprovalDecision;
  feedback_notes: Nullable<string>;
  created_at: ISODateTime;
};

export type BackgroundJobContract = {
  id: UUID;
  user_id: UUID;
  project_id: UUID;
  script_id: Nullable<UUID>;
  job_type: BackgroundJobType;
  provider_name: Nullable<ProviderName>;
  state: BackgroundJobState;
  payload_json: QueueJobPayload;
  attempts: number;
  progress_percent: number;
  error_message: Nullable<string>;
  available_at: Nullable<ISODateTime>;
  started_at: Nullable<ISODateTime>;
  finished_at: Nullable<ISODateTime>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type PublishJobContract = {
  id: UUID;
  user_id: UUID;
  project_id: UUID;
  script_id: UUID;
  final_asset_id: UUID;
  platform: string;
  title: string;
  description: string;
  hashtags_json: string[];
  scheduled_for: Nullable<ISODateTime>;
  status: PublishJobStatus;
  idempotency_key: Nullable<string>;
  external_post_id: Nullable<string>;
  manual_publish_notes: Nullable<string>;
  error_message: Nullable<string>;
  metadata_json: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
};

export type AnalyticsSnapshotContract = {
  id: UUID;
  user_id: UUID;
  project_id: UUID;
  publish_job_id: UUID;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  saves: Nullable<number>;
  watch_time_seconds: Nullable<number>;
  ctr: Nullable<number>;
  avg_view_duration: Nullable<number>;
  retention_json: Nullable<Record<string, unknown>>;
  fetched_at: ISODateTime;
};

export type AnalyticsLearningItemContract = {
  insight_id: UUID;
  source_project_id: UUID;
  source_project_title: string;
  is_current_project: boolean;
  publish_job_id: UUID;
  analytics_snapshot_id: UUID;
  insight_type: string;
  summary: string;
  evidence: Record<string, unknown>;
  confidence_score: number;
  created_at: ISODateTime;
};

export type AnalyticsLearningContextContract = {
  available: boolean;
  brand_profile_id: UUID;
  target_project_id: UUID;
  source_count: number;
  guidance: string[];
  items: AnalyticsLearningItemContract[];
};

export type QueuePayloadBase = {
  job_type: QueueJobType;
  project_id: UUID;
  correlation_id: UUID;
};

export type ImplementedQueueJobType = BackgroundJobType;

export type PlannedQueueJobType =
  | "ingest_download";

export type QueueJobType = ImplementedQueueJobType | PlannedQueueJobType;

export type GenerateIdeasQueuePayload = QueuePayloadBase & {
  job_type: "generate_ideas";
  brand_profile_id: UUID;
  target_platform: string;
  objective: string;
  research_snapshot_id?: UUID;
  source_feedback_notes?: Nullable<string>;
  analytics_learning_context?: AnalyticsLearningContextContract;
  idea_count?: number;
  idea_ids?: UUID[];
};

export type GenerateIdeaResearchQueuePayload = QueuePayloadBase & {
  job_type: "generate_idea_research";
  brand_profile_id: UUID;
  target_platform: string;
  objective: string;
  focus_topic?: Nullable<string>;
  source_feedback_notes?: Nullable<string>;
  analytics_learning_context?: AnalyticsLearningContextContract;
  research_snapshot_id?: UUID;
};

export type GenerateScriptQueuePayload = QueuePayloadBase & {
  job_type: "generate_script";
  approved_idea_id: UUID;
  brand_profile_id: UUID;
  source_feedback_notes?: Nullable<string>;
  analytics_learning_context?: AnalyticsLearningContextContract;
  script_id?: UUID;
  script_version?: number;
  scene_count?: number;
};

export type NarrationSegmentPayload = {
  scene_id: UUID;
  scene_order: number;
  title: string;
  narration_input: string;
  narration_direction: string;
  estimated_duration_seconds: number;
};

export type GenerateAudioQueuePayload = QueuePayloadBase & {
  job_type: "generate_audio_browser";
  script_id: UUID;
  script_version: number;
  voice_label?: Nullable<string>;
  estimated_duration_seconds: number;
  scene_count: number;
  narration_segments: NarrationSegmentPayload[];
};

export type VisualScenePayload = {
  scene_id: UUID;
  scene_order: number;
  title: string;
  estimated_duration_seconds: number;
  image_generation_prompt: string;
  video_generation_prompt: string;
};

export type GenerateVisualsQueuePayload = QueuePayloadBase & {
  job_type: "generate_visuals_browser";
  script_id: UUID;
  script_version: number;
  scene_count: number;
  scene_ids: UUID[];
  scenes: VisualScenePayload[];
};

export type ComposeRoughCutQueuePayload = QueuePayloadBase & {
  job_type: "compose_rough_cut";
  script_id: UUID;
  script_version: number;
  scene_count: number;
  preview_path: StoragePath;
  manifest_path: StoragePath;
  subtitle_path: StoragePath;
  output_asset_id: UUID;
  subtitle_asset_id: UUID;
  video_path?: StoragePath;
  video_asset_id?: UUID;
  ffmpeg_command_path?: StoragePath;
};

export type IngestDownloadQueuePayload = QueuePayloadBase &
  TraceabilityFields & {
    job_type: "ingest_download";
    source_path: StoragePath;
    expected_asset_type: AssetType;
    provider_name: ProviderName;
  };

export type FinalExportQueuePayload = QueuePayloadBase & {
  job_type: "final_export";
  script_id: UUID;
  script_version: number;
  scene_count: number;
  rough_cut_asset_id: UUID;
  source_video_asset_id?: UUID;
  source_video_path?: StoragePath;
  manifest_path: StoragePath;
  subtitle_path: StoragePath;
  output_asset_id: UUID;
  video_path: StoragePath;
  ffmpeg_command_path: StoragePath;
  export_profile: string;
};

export type PublishContentQueuePayload = QueuePayloadBase & {
  job_type: "publish_content";
  adapter_name: PublishAdapterName;
  publish_job_id: UUID;
  approved_publish_job_state: "approved" | "scheduled";
  platform: string;
  final_asset_id: UUID;
  handoff_path: StoragePath;
  scheduled_for?: Nullable<ISODateTime>;
};

export type SyncAnalyticsQueuePayload = QueuePayloadBase & {
  job_type: "sync_analytics";
  publish_job_id: UUID;
  platform: string;
  metrics: {
    views: number;
    likes?: number;
    comments?: number;
    shares?: number;
    saves?: Nullable<number>;
    watch_time_seconds?: Nullable<number>;
    ctr?: Nullable<number>;
    avg_view_duration?: Nullable<number>;
    retention_json?: Nullable<Record<string, unknown>>;
  };
  analytics_snapshot_id?: UUID;
  synced_at?: ISODateTime;
};

export type QueueJobPayload =
  | GenerateIdeaResearchQueuePayload
  | GenerateIdeasQueuePayload
  | GenerateScriptQueuePayload
  | GenerateAudioQueuePayload
  | GenerateVisualsQueuePayload
  | ComposeRoughCutQueuePayload
  | IngestDownloadQueuePayload
  | FinalExportQueuePayload
  | PublishContentQueuePayload
  | SyncAnalyticsQueuePayload;

export type ScenePromptPackContract = {
  scene_id: UUID;
  scene_order: number;
  title: string;
  estimated_duration_seconds: number;
  overlay_text: string;
  narration_input: string;
  narration_direction: string;
  image_generation_prompt: string;
  video_generation_prompt: string;
  notes: Nullable<string>;
};

export type ScriptPromptPackContract = {
  script_id: UUID;
  project_id: UUID;
  brand_profile_id: UUID;
  brand_context: Record<string, unknown>;
  analytics_learning_context: AnalyticsLearningContextContract;
  channel_name: string;
  target_platform: string;
  objective: string;
  script_status: ScriptStatus;
  version_number: number;
  source_idea_title: string;
  caption: string;
  hashtags: string[];
  title_options: string[];
  scenes: ScenePromptPackContract[];
};

export type TimelineAssetReference = {
  asset_id: UUID;
  file_path: StoragePath;
  asset_type: AssetType;
  provider_name?: Nullable<ProviderName>;
  duration_seconds?: Nullable<number>;
  checksum?: Nullable<string>;
};

export type TimelineSceneManifest = {
  scene_id: UUID;
  scene_order: number;
  title: string;
  start_seconds: number;
  end_seconds: number;
  duration_seconds: number;
  estimated_duration_seconds: number;
  narration_text: string;
  overlay_text: string;
  visual_asset: TimelineAssetReference;
};

export type TimelineManifestContract = {
  manifest_version: 1;
  project_id: UUID;
  project_title: string;
  script_id: UUID;
  script_version: number;
  generated_at: ISODateTime;
  total_duration_seconds: number;
  timing_strategy: {
    source: "narration_audio_wav" | "scene_estimates";
    scale_factor: number;
  };
  narration_asset: TimelineAssetReference & {
    probed_duration_seconds?: Nullable<number>;
  };
  subtitle_asset?: TimelineAssetReference;
  scenes: TimelineSceneManifest[];
};

export function validateArtifactTraceability(traceability: ArtifactTraceability): string[] {
  const errors: string[] = [];

  if (!isNonEmptyString(traceability.project_id)) {
    errors.push("project_id is required.");
  }
  if (!isNonEmptyString(traceability.asset_id ?? "")) {
    errors.push("asset_id is required for artifact traceability.");
  }
  if (!isNonEmptyString(traceability.file_path)) {
    errors.push("file_path is required for artifact traceability.");
  }
  if (isSceneLevelAsset(traceability.asset_type) && !isNonEmptyString(traceability.scene_id ?? "")) {
    errors.push("scene_id is required for scene-level visual artifacts.");
  }
  if (
    traceability.asset_type !== "script_doc" &&
    !isNonEmptyString(traceability.generation_attempt_id ?? "")
  ) {
    errors.push("generation_attempt_id is required for generated artifacts.");
  }

  return errors;
}

export function validateQueuePayload(payload: QueueJobPayload): string[] {
  const errors = validateQueuePayloadBase(payload);

  switch (payload.job_type) {
    case "generate_idea_research":
      requireString(payload.brand_profile_id, "brand_profile_id", errors);
      requireString(payload.target_platform, "target_platform", errors);
      requireString(payload.objective, "objective", errors);
      break;
    case "generate_ideas":
      requireString(payload.brand_profile_id, "brand_profile_id", errors);
      requireString(payload.target_platform, "target_platform", errors);
      requireString(payload.objective, "objective", errors);
      break;
    case "generate_script":
      requireString(payload.approved_idea_id, "approved_idea_id", errors);
      requireString(payload.brand_profile_id, "brand_profile_id", errors);
      break;
    case "generate_audio_browser":
      requireScriptPayload(payload, errors);
      requirePositiveNumber(payload.estimated_duration_seconds, "estimated_duration_seconds", errors);
      requireNonEmptyArray(payload.narration_segments, "narration_segments", errors);
      break;
    case "generate_visuals_browser":
      requireScriptPayload(payload, errors);
      requireNonEmptyArray(payload.scene_ids, "scene_ids", errors);
      requireNonEmptyArray(payload.scenes, "scenes", errors);
      break;
    case "compose_rough_cut":
      requireScriptPayload(payload, errors);
      requireString(payload.preview_path, "preview_path", errors);
      requireString(payload.manifest_path, "manifest_path", errors);
      requireString(payload.output_asset_id, "output_asset_id", errors);
      break;
    case "ingest_download":
      requireString(payload.source_path, "source_path", errors);
      requireString(payload.provider_name, "provider_name", errors);
      break;
    case "final_export":
      requireString(payload.script_id, "script_id", errors);
      requirePositiveNumber(payload.script_version, "script_version", errors);
      requirePositiveNumber(payload.scene_count, "scene_count", errors);
      requireString(payload.rough_cut_asset_id, "rough_cut_asset_id", errors);
      requireString(payload.manifest_path, "manifest_path", errors);
      requireString(payload.subtitle_path, "subtitle_path", errors);
      requireString(payload.output_asset_id, "output_asset_id", errors);
      requireString(payload.video_path, "video_path", errors);
      requireString(payload.ffmpeg_command_path, "ffmpeg_command_path", errors);
      requireString(payload.export_profile, "export_profile", errors);
      break;
    case "publish_content":
      requireString(payload.adapter_name, "adapter_name", errors);
      requireString(payload.publish_job_id, "publish_job_id", errors);
      requireString(payload.platform, "platform", errors);
      requireString(payload.final_asset_id, "final_asset_id", errors);
      requireString(payload.handoff_path, "handoff_path", errors);
      break;
    case "sync_analytics":
      requireString(payload.publish_job_id, "publish_job_id", errors);
      requireString(payload.platform, "platform", errors);
      if (!payload.metrics || typeof payload.metrics.views !== "number") {
        errors.push("metrics.views is required.");
      } else if (payload.metrics.views < 0) {
        errors.push("metrics.views must be greater than or equal to zero.");
      }
      break;
  }

  return errors;
}

export function validatePromptPackContract(promptPack: ScriptPromptPackContract): string[] {
  const errors: string[] = [];
  requireString(promptPack.script_id, "script_id", errors);
  requireString(promptPack.project_id, "project_id", errors);
  requireString(promptPack.brand_profile_id, "brand_profile_id", errors);
  requireNonEmptyArray(promptPack.scenes, "scenes", errors);
  validateContiguousOrders(
    promptPack.scenes.map((scene) => scene.scene_order),
    "scene_order",
    errors,
  );

  for (const scene of promptPack.scenes) {
    requireString(scene.scene_id, "scene_id", errors);
    requirePositiveNumber(
      scene.estimated_duration_seconds,
      "estimated_duration_seconds",
      errors,
    );
    requireString(scene.narration_input, "narration_input", errors);
    requireString(scene.image_generation_prompt, "image_generation_prompt", errors);
    requireString(scene.video_generation_prompt, "video_generation_prompt", errors);
  }

  return errors;
}

export function validateTimelineManifestContract(manifest: TimelineManifestContract): string[] {
  const errors: string[] = [];
  requireString(manifest.project_id, "project_id", errors);
  requireString(manifest.script_id, "script_id", errors);
  requirePositiveNumber(manifest.total_duration_seconds, "total_duration_seconds", errors);
  requireNonEmptyArray(manifest.scenes, "scenes", errors);
  validateContiguousOrders(
    manifest.scenes.map((scene) => scene.scene_order),
    "scene_order",
    errors,
  );

  let previousEnd = 0;
  for (const scene of manifest.scenes) {
    requireString(scene.scene_id, "scene_id", errors);
    requireString(scene.visual_asset.file_path, "visual_asset.file_path", errors);
    requirePositiveNumber(scene.duration_seconds, "duration_seconds", errors);
    if (Math.abs(scene.start_seconds - previousEnd) > 0.001) {
      errors.push("Timeline scenes must be contiguous.");
    }
    if (scene.end_seconds <= scene.start_seconds) {
      errors.push("Scene end_seconds must be greater than start_seconds.");
    }
    previousEnd = scene.end_seconds;
  }

  if (Math.abs(previousEnd - manifest.total_duration_seconds) > 0.001) {
    errors.push("Final scene end_seconds must match total_duration_seconds.");
  }

  return errors;
}

function validateQueuePayloadBase(payload: QueueJobPayload): string[] {
  const errors: string[] = [];
  requireString(payload.project_id, "project_id", errors);
  requireString(payload.correlation_id, "correlation_id", errors);

  if (!isKnownQueueJobType(payload.job_type)) {
    errors.push(`Unknown queue job type: ${payload.job_type}.`);
  }

  return errors;
}

function isKnownQueueJobType(jobType: string): jobType is QueueJobType {
  return (
    (backgroundJobTypes as readonly string[]).includes(jobType) ||
    ["ingest_download", "final_export"].includes(jobType)
  );
}

function isSceneLevelAsset(assetType: AssetType): boolean {
  return assetType === "scene_image" || assetType === "scene_video";
}

function requireScriptPayload(
  payload: { script_id: UUID; script_version: number; scene_count?: number },
  errors: string[],
): void {
  requireString(payload.script_id, "script_id", errors);
  requirePositiveNumber(payload.script_version, "script_version", errors);
  if (payload.scene_count !== undefined) {
    requirePositiveNumber(payload.scene_count, "scene_count", errors);
  }
}

function validateContiguousOrders(
  orders: number[],
  label: string,
  errors: string[],
): void {
  const expectedOrders = Array.from({ length: orders.length }, (_, index) => index + 1);
  if (orders.some((order, index) => order !== expectedOrders[index])) {
    errors.push(`${label} values must be contiguous and start at 1.`);
  }
}

function requireString(value: string, label: string, errors: string[]): void {
  if (!isNonEmptyString(value)) {
    errors.push(`${label} is required.`);
  }
}

function requirePositiveNumber(value: number, label: string, errors: string[]): void {
  if (!Number.isFinite(value) || value <= 0) {
    errors.push(`${label} must be a positive number.`);
  }
}

function requireNonEmptyArray<T>(value: T[], label: string, errors: string[]): void {
  if (!Array.isArray(value) || value.length === 0) {
    errors.push(`${label} must include at least one item.`);
  }
}

function isNonEmptyString(value: string): boolean {
  return value.trim().length > 0;
}
