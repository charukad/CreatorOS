import type {
  AssetStatus,
  ApprovalDecision,
  BackgroundJobState,
  ProjectStatus,
  PublishJobStatus,
} from "@creatoros/shared";

type StatusTone = "neutral" | "info" | "active" | "success" | "warning" | "danger" | "archived";

const toneClassNames: Record<StatusTone, string> = {
  neutral: "border-slate-400/30 bg-slate-400/10 text-slate-200",
  info: "border-sky-400/30 bg-sky-400/10 text-sky-200",
  active: "border-cyan-400/30 bg-cyan-400/10 text-cyan-200",
  success: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  warning: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  danger: "border-rose-400/30 bg-rose-400/10 text-rose-200",
  archived: "border-slate-500/30 bg-slate-500/10 text-slate-300",
};

export const projectStatusTones: Record<ProjectStatus, StatusTone> = {
  draft: "neutral",
  idea_pending_approval: "info",
  script_pending_approval: "info",
  asset_generation: "active",
  asset_pending_approval: "active",
  rough_cut_ready: "info",
  final_pending_approval: "warning",
  ready_to_publish: "warning",
  scheduled: "warning",
  published: "success",
  failed: "danger",
  archived: "archived",
};

export const assetStatusTones: Record<AssetStatus, StatusTone> = {
  planned: "neutral",
  generating: "active",
  ready: "success",
  failed: "danger",
  rejected: "warning",
};

export const backgroundJobStateTones: Record<BackgroundJobState, StatusTone> = {
  queued: "neutral",
  running: "active",
  waiting_external: "warning",
  completed: "success",
  failed: "danger",
  cancelled: "archived",
};

export const approvalDecisionTones: Record<ApprovalDecision, StatusTone> = {
  approved: "success",
  rejected: "warning",
};

export const publishJobStatusTones: Record<PublishJobStatus, StatusTone> = {
  pending_approval: "warning",
  approved: "success",
  scheduled: "warning",
  published: "success",
  failed: "danger",
  cancelled: "archived",
};

export function statusClassName(tone: StatusTone): string {
  return toneClassNames[tone];
}
