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

export const approvalDecisions = ["approved", "rejected"] as const;

export type ApprovalDecision = (typeof approvalDecisions)[number];

export const approvalTargetTypes = ["content_idea", "script"] as const;

export type ApprovalTargetType = (typeof approvalTargetTypes)[number];

export const contentIdeaStatuses = ["proposed", "approved", "rejected"] as const;

export type ContentIdeaStatus = (typeof contentIdeaStatuses)[number];

export const scriptStatuses = ["draft", "approved", "rejected", "superseded"] as const;

export type ScriptStatus = (typeof scriptStatuses)[number];

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

export const projectStatusDescriptions: Record<ProjectStatus, string> = {
  draft: "Project setup is still being refined before idea generation begins.",
  idea_pending_approval: "Ideas are ready for human review and one must be approved.",
  script_pending_approval: "A script draft exists and is waiting for approval before asset work starts.",
  asset_generation: "The browser workers are generating narration and visual assets.",
  asset_pending_approval: "Generated assets are ready for human review and approval.",
  rough_cut_ready: "The rough cut is assembled and can move into final review.",
  final_pending_approval: "The final video is waiting for explicit approval.",
  ready_to_publish: "The project is approved and ready for scheduling or publishing.",
  scheduled: "The publish job has been scheduled but not yet published.",
  published: "The content has been published and can move into analytics sync.",
  failed: "A critical step failed and needs manual recovery before continuing.",
  archived: "The project is archived and should not continue through the workflow.",
};

export const contentIdeaStatusLabels: Record<ContentIdeaStatus, string> = {
  proposed: "Proposed",
  approved: "Approved",
  rejected: "Rejected",
};

export const scriptStatusLabels: Record<ScriptStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  rejected: "Rejected",
  superseded: "Superseded",
};

export const approvalStageLabels: Record<ApprovalStage, string> = {
  idea: "Idea",
  script: "Script",
  assets: "Assets",
  final_video: "Final Video",
  publish: "Publish",
};

export const approvalDecisionLabels: Record<ApprovalDecision, string> = {
  approved: "Approved",
  rejected: "Rejected",
};

export const projectStatusTransitions: Record<ProjectStatus, ProjectStatus[]> = {
  draft: ["idea_pending_approval", "archived"],
  idea_pending_approval: ["draft", "script_pending_approval", "archived"],
  script_pending_approval: ["idea_pending_approval", "asset_generation", "archived"],
  asset_generation: ["script_pending_approval", "asset_pending_approval", "failed", "archived"],
  asset_pending_approval: ["asset_generation", "rough_cut_ready", "archived"],
  rough_cut_ready: ["asset_pending_approval", "final_pending_approval", "archived"],
  final_pending_approval: ["rough_cut_ready", "ready_to_publish", "archived"],
  ready_to_publish: ["final_pending_approval", "scheduled", "published", "archived"],
  scheduled: ["ready_to_publish", "published", "archived"],
  published: ["archived"],
  failed: ["draft", "asset_generation", "archived"],
  archived: [],
};

export function getAvailableProjectStatusTransitions(status: ProjectStatus): ProjectStatus[] {
  return projectStatusTransitions[status];
}

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
