import type {
  AssetStatus,
  AssetType,
  ApprovalDecision,
  ApprovalStage,
  ApprovalTargetType,
  BackgroundJobState,
  BackgroundJobType,
  ContentIdeaStatus,
  ProjectStatus,
  PublishJobStatus,
  ProviderName,
  ScriptStatus,
} from "@creatoros/shared";

export type BrandProfile = {
  id: string;
  user_id: string;
  channel_name: string;
  niche: string;
  target_audience: string;
  tone: string;
  hook_style: string;
  cta_style: string;
  visual_style: string;
  posting_preferences_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type BrandProfilePayload = {
  channel_name: string;
  niche: string;
  target_audience: string;
  tone: string;
  hook_style: string;
  cta_style: string;
  visual_style: string;
  posting_preferences_json: Record<string, unknown>;
};

export type Project = {
  id: string;
  user_id: string;
  brand_profile_id: string;
  title: string;
  target_platform: string;
  objective: string;
  notes: string | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
};

export type ProjectPayload = {
  brand_profile_id: string;
  title: string;
  target_platform: string;
  objective: string;
  notes: string | null;
};

export type ContentIdea = {
  id: string;
  user_id: string;
  project_id: string;
  suggested_title: string;
  hook: string;
  angle: string;
  rationale: string;
  score: number;
  status: ContentIdeaStatus;
  feedback_notes: string | null;
  created_at: string;
  updated_at: string;
};

export type IdeaApprovalPayload = {
  feedback_notes?: string | null;
};

export type ScriptScene = {
  id: string;
  script_id: string;
  scene_order: number;
  title: string;
  narration_text: string;
  overlay_text: string;
  image_prompt: string;
  video_prompt: string;
  estimated_duration_seconds: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectScript = {
  id: string;
  user_id: string;
  project_id: string;
  content_idea_id: string;
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
  source_feedback_notes: string | null;
  created_at: string;
  updated_at: string;
  scenes: ScriptScene[];
};

export type ScriptGeneratePayload = {
  source_feedback_notes?: string | null;
};

export type SceneUpdatePayload = {
  title?: string;
  narration_text?: string;
  overlay_text?: string;
  image_prompt?: string;
  video_prompt?: string;
  estimated_duration_seconds?: number;
  notes?: string | null;
};

export type ScenePromptPack = {
  scene_id: string;
  scene_order: number;
  title: string;
  estimated_duration_seconds: number;
  overlay_text: string;
  narration_input: string;
  narration_direction: string;
  image_generation_prompt: string;
  video_generation_prompt: string;
  notes: string | null;
};

export type ScriptPromptPack = {
  script_id: string;
  project_id: string;
  brand_profile_id: string;
  channel_name: string;
  target_platform: string;
  objective: string;
  script_status: ScriptStatus;
  version_number: number;
  source_idea_title: string;
  caption: string;
  hashtags: string[];
  title_options: string[];
  scenes: ScenePromptPack[];
};

export type ApprovalRecord = {
  id: string;
  user_id: string;
  project_id: string;
  target_type: ApprovalTargetType;
  target_id: string;
  stage: ApprovalStage;
  decision: ApprovalDecision;
  feedback_notes: string | null;
  created_at: string;
};

export type ApprovalDecisionPayload = {
  feedback_notes?: string | null;
};

export type AudioGenerationPayload = {
  voice_label?: string | null;
};

export type VisualGenerationPayload = {
  scene_ids?: string[];
};

export type PublishJobPreparePayload = {
  platform: string;
  title: string;
  description: string;
  hashtags: string[];
  scheduled_for?: string | null;
  idempotency_key?: string | null;
};

export type PublishJobSchedulePayload = {
  scheduled_for: string;
};

export type ManualPublishCompletePayload = {
  external_post_id?: string | null;
  manual_publish_notes?: string | null;
};

export type BackgroundJob = {
  id: string;
  user_id: string;
  project_id: string;
  script_id: string;
  job_type: BackgroundJobType;
  provider_name: ProviderName | null;
  state: BackgroundJobState;
  payload_json: Record<string, unknown>;
  attempts: number;
  progress_percent: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PublishJob = {
  id: string;
  user_id: string;
  project_id: string;
  script_id: string;
  final_asset_id: string;
  platform: string;
  title: string;
  description: string;
  hashtags_json: string[];
  scheduled_for: string | null;
  status: PublishJobStatus;
  idempotency_key: string | null;
  external_post_id: string | null;
  manual_publish_notes: string | null;
  error_message: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type GenerationAttempt = {
  id: string;
  user_id: string;
  project_id: string;
  script_id: string;
  background_job_id: string;
  scene_id: string | null;
  provider_name: ProviderName;
  state: BackgroundJobState;
  input_payload_json: Record<string, unknown>;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Asset = {
  id: string;
  user_id: string;
  project_id: string;
  script_id: string;
  scene_id: string | null;
  generation_attempt_id: string | null;
  asset_type: AssetType;
  status: AssetStatus;
  provider_name: ProviderName | null;
  file_path: string | null;
  mime_type: string | null;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  checksum: string | null;
  created_at: string;
  updated_at: string;
};

export type JobLog = {
  id: string;
  user_id: string;
  project_id: string;
  script_id: string;
  background_job_id: string;
  generation_attempt_id: string | null;
  level: string;
  event_type: string;
  message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type BackgroundJobDetail = {
  job: BackgroundJob;
  generation_attempts: GenerationAttempt[];
  related_assets: Asset[];
  job_logs: JobLog[];
};

export type ProjectActivity = {
  source_id: string;
  source_type: string;
  activity_type: string;
  title: string;
  description: string | null;
  level: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
};
