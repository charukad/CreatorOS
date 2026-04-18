import type { ProjectStatus } from "@creatoros/shared";

const statusClassNames: Record<ProjectStatus, string> = {
  draft: "border-slate-400/30 bg-slate-400/10 text-slate-200",
  idea_pending_approval: "border-sky-400/30 bg-sky-400/10 text-sky-200",
  script_pending_approval: "border-blue-400/30 bg-blue-400/10 text-blue-200",
  asset_generation: "border-cyan-400/30 bg-cyan-400/10 text-cyan-200",
  asset_pending_approval: "border-teal-400/30 bg-teal-400/10 text-teal-200",
  rough_cut_ready: "border-indigo-400/30 bg-indigo-400/10 text-indigo-200",
  final_pending_approval: "border-violet-400/30 bg-violet-400/10 text-violet-200",
  ready_to_publish: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  scheduled: "border-orange-400/30 bg-orange-400/10 text-orange-200",
  published: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  failed: "border-rose-400/30 bg-rose-400/10 text-rose-200",
  archived: "border-slate-500/30 bg-slate-500/10 text-slate-300",
};

type StatusBadgeProps = {
  label: string;
  status: ProjectStatus;
};

export function StatusBadge({ label, status }: StatusBadgeProps) {
  return (
    <span
      className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${statusClassNames[status]}`}
    >
      {label}
    </span>
  );
}

