"use client";

import { approvalDecisionLabels } from "@creatoros/shared";
import type { ApprovalRecord } from "../types/api";

type ApprovalFeedbackPanelProps = {
  approval: ApprovalRecord | null;
  applyFeedbackLabel?: string;
  emptyDescription: string;
  emptyTitle: string;
  onApplyFeedback?: (feedbackNotes: string) => void;
  title: string;
};

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

function decisionClassName(decision: ApprovalRecord["decision"]): string {
  return decision === "approved"
    ? "border-emerald-300/20 bg-emerald-500/10 text-emerald-100"
    : "border-rose-300/20 bg-rose-500/10 text-rose-100";
}

export function ApprovalFeedbackPanel({
  approval,
  applyFeedbackLabel = "Use feedback",
  emptyDescription,
  emptyTitle,
  onApplyFeedback,
  title,
}: ApprovalFeedbackPanelProps) {
  if (approval === null) {
    return (
      <div className="rounded-2xl border border-dashed border-white/10 bg-white/4 p-4 text-sm text-slate-300">
        <p className="font-semibold text-white">{emptyTitle}</p>
        <p className="mt-2 leading-6">{emptyDescription}</p>
      </div>
    );
  }

  return (
    <div
      className={`rounded-2xl border p-4 text-sm ${decisionClassName(approval.decision)}`}
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/70">
            {title}
          </p>
          <p className="mt-2 font-semibold">
            {approvalDecisionLabels[approval.decision]}
          </p>
        </div>
        <p className="text-xs uppercase tracking-[0.16em] text-white/60">
          {formatTimestamp(approval.created_at)}
        </p>
      </div>

      {approval.feedback_notes ? (
        <p className="mt-3 leading-6">{approval.feedback_notes}</p>
      ) : (
        <p className="mt-3 text-white/70">No feedback notes were saved for this review.</p>
      )}

      {onApplyFeedback && approval.feedback_notes ? (
        <button
          className="mt-4 rounded-full border border-white/15 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-white transition hover:border-white/25 hover:bg-white/10"
          onClick={() => onApplyFeedback(approval.feedback_notes ?? "")}
          type="button"
        >
          {applyFeedbackLabel}
        </button>
      ) : null}
    </div>
  );
}
