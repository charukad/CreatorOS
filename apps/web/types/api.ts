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

export type BrandProfileReadiness = {
  brand_profile_id: string;
  is_ready: boolean;
  missing_fields: string[];
  warnings: string[];
  recommended_next_steps: string[];
};

export type BrandPromptContext = {
  brand_profile_id: string;
  readiness: BrandProfileReadiness;
  context_markdown: string;
  context_json: Record<string, unknown>;
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

export type ProjectArchivePayload = {
  reason?: string | null;
};

export type ProjectManualOverridePayload = {
  target_status: ProjectStatus;
  reason: string;
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
  brand_context: Record<string, unknown>;
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

export type AnalyticsSnapshotPayload = {
  views: number;
  likes?: number;
  comments?: number;
  shares?: number;
  saves?: number | null;
  watch_time_seconds?: number | null;
  ctr?: number | null;
  avg_view_duration?: number | null;
  retention_json?: Record<string, unknown> | null;
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

export type RecoveryJob = {
  job: BackgroundJob;
  project_title: string;
  project_status: ProjectStatus;
  latest_log_event_type: string | null;
  latest_log_message: string | null;
  latest_log_created_at: string | null;
};

export type RecoveryLog = {
  id: string;
  project_id: string;
  project_title: string;
  background_job_id: string;
  generation_attempt_id: string | null;
  event_type: string;
  level: string;
  message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type OperationsRecovery = {
  failed_jobs: RecoveryJob[];
  waiting_jobs: RecoveryJob[];
  stale_running_jobs: RecoveryJob[];
  quarantined_downloads: RecoveryLog[];
  duplicate_asset_warnings: RecoveryLog[];
  summary: {
    failed_jobs: number;
    waiting_jobs: number;
    stale_running_jobs: number;
    quarantined_downloads: number;
    duplicate_asset_warnings: number;
    total_attention_items: number;
  };
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

export type AnalyticsSnapshot = {
  id: string;
  user_id: string;
  project_id: string;
  publish_job_id: string;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  saves: number | null;
  watch_time_seconds: number | null;
  ctr: number | null;
  avg_view_duration: number | null;
  retention_json: Record<string, unknown> | null;
  fetched_at: string;
};

export type Insight = {
  id: string;
  user_id: string;
  project_id: string;
  publish_job_id: string;
  analytics_snapshot_id: string;
  insight_type: string;
  summary: string;
  evidence_json: Record<string, unknown>;
  confidence_score: number;
  created_at: string;
};

export type ProjectAnalytics = {
  snapshots: AnalyticsSnapshot[];
  insights: Insight[];
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

export type ManualInterventionPayload = {
  reason: string;
};

export type ProjectExport = {
  exported_at: string;
  project: Record<string, unknown>;
  brand_profile: Record<string, unknown>;
  ideas: Record<string, unknown>[];
  scripts: Record<string, unknown>[];
  approvals: Record<string, unknown>[];
  assets: Record<string, unknown>[];
  background_jobs: Record<string, unknown>[];
  publish_jobs: Record<string, unknown>[];
  analytics_snapshots: Record<string, unknown>[];
  insights: Record<string, unknown>[];
  project_events: Record<string, unknown>[];
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

export type ApiErrorEnvelope = {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
    request_id: string | null;
  };
};
