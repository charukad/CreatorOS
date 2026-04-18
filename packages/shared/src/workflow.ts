export const projectStatuses = [
  "draft",
  "idea_pending_approval",
  "script_pending_approval",
  "asset_generation",
  "asset_pending_approval",
  "rough_cut_ready",
  "final_pending_approval",
  "ready_to_publish",
  "scheduled",
  "published",
  "failed",
  "archived",
] as const;

export type ProjectStatus = (typeof projectStatuses)[number];

export const approvalStages = [
  "idea",
  "script",
  "assets",
  "final_video",
  "publish",
] as const;

export type ApprovalStage = (typeof approvalStages)[number];

export const assetTypes = [
  "script_doc",
  "narration_audio",
  "scene_image",
  "scene_video",
  "rough_cut",
  "final_video",
  "subtitle_file",
  "thumbnail",
] as const;

export type AssetType = (typeof assetTypes)[number];

export const providerNames = ["elevenlabs_web", "flow_web"] as const;
export type ProviderName = (typeof providerNames)[number];

export const backgroundJobStates = [
  "queued",
  "running",
  "waiting_external",
  "completed",
  "failed",
  "cancelled",
] as const;

export type BackgroundJobState = (typeof backgroundJobStates)[number];

export const projectStatusLabels: Record<ProjectStatus, string> = {
  draft: "Draft",
  idea_pending_approval: "Idea Approval",
  script_pending_approval: "Script Approval",
  asset_generation: "Asset Generation",
  asset_pending_approval: "Asset Approval",
  rough_cut_ready: "Rough Cut Ready",
  final_pending_approval: "Final Approval",
  ready_to_publish: "Ready to Publish",
  scheduled: "Scheduled",
  published: "Published",
  failed: "Failed",
  archived: "Archived",
};

export const workflowMilestones = [
  {
    id: "brand",
    title: "Brand Setup",
    description: "Define the creator profile, tone, audience, and content preferences.",
  },
  {
    id: "idea",
    title: "Idea and Script Approval",
    description: "Generate ideas and scripts, then keep a human approval gate before any asset work starts.",
  },
  {
    id: "assets",
    title: "Browser-Based Asset Generation",
    description: "Use ElevenLabs and Flow through resilient Playwright workers with traceable attempts.",
  },
  {
    id: "media",
    title: "Rough Cut and Final Export",
    description: "Assemble approved assets into a rough cut, collect feedback, and export final deliverables.",
  },
  {
    id: "publish",
    title: "Publishing and Analytics",
    description: "Prepare metadata, schedule only after approval, then sync analytics and learn from performance.",
  },
] as const;

