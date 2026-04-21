"use client";

import { approvalDecisionLabels, publishJobStatusLabels } from "@creatoros/shared";
import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";
import {
  approveFinalVideo,
  approvePublishJob,
  markPublishJobPublished,
  preparePublishJob,
  rejectFinalVideo,
  schedulePublishJob,
} from "../lib/api";
import type {
  ApprovalRecord,
  Asset,
  Project,
  ProjectScript,
  PublishJob,
} from "../types/api";

type ProjectPublishCenterProps = {
  approvals: ApprovalRecord[];
  assets: Asset[];
  currentScript: ProjectScript | null;
  project: Project;
  publishJobs: PublishJob[];
};

function formatTimestamp(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "Not set";
}

function defaultScheduleValue(): string {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setMinutes(0, 0, 0);
  return date.toISOString().slice(0, 16);
}

function toIsoDateTime(value: string): string {
  return new Date(value).toISOString();
}

export function ProjectPublishCenter({
  approvals,
  assets,
  currentScript,
  project,
  publishJobs,
}: ProjectPublishCenterProps) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [scheduledFor, setScheduledFor] = useState(defaultScheduleValue);
  const [externalPostId, setExternalPostId] = useState("");
  const [manualPublishNotes, setManualPublishNotes] = useState("");

  const currentScriptAssets =
    currentScript === null
      ? []
      : assets.filter((asset) => asset.script_id === currentScript.id);
  const readyRoughCutAssets = currentScriptAssets.filter(
    (asset) => asset.asset_type === "rough_cut" && asset.status === "ready",
  );
  const latestReadyRoughCut = readyRoughCutAssets[0] ?? null;
  const latestFinalApproval =
    latestReadyRoughCut === null
      ? null
      : approvals.find(
          (approval) =>
            approval.stage === "final_video" && approval.target_id === latestReadyRoughCut.id,
        ) ?? null;
  const activePublishJob =
    publishJobs.find((job) =>
      ["pending_approval", "approved", "scheduled"].includes(job.status),
    ) ?? null;
  const canReviewFinal =
    project.status === "final_pending_approval" && latestReadyRoughCut !== null;
  const canPreparePublish =
    project.status === "ready_to_publish" &&
    currentScript !== null &&
    latestReadyRoughCut !== null &&
    activePublishJob === null;

  function runAction(actionKey: string, callback: () => Promise<unknown>) {
    setError(null);
    setPendingAction(actionKey);
    startTransition(() => {
      void callback()
        .then(() => {
          router.refresh();
          setPendingAction(null);
        })
        .catch((actionError) => {
          setError(
            actionError instanceof Error ? actionError.message : "Publish workflow action failed.",
          );
          setPendingAction(null);
        });
    });
  }

  return (
    <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Final approval and publishing</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
            The publish path is intentionally gated: approve the final video, prepare metadata,
            approve the publish job, then schedule or record a manual publish.
          </p>
        </div>
        <div className="rounded-2xl border border-amber-300/20 bg-amber-400/10 px-4 py-3 text-sm text-amber-50">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-200/80">
            Safety rule
          </p>
          <p className="mt-2 max-w-xs">
            CreatorOS stores publish intent, but it does not publish without explicit approval.
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <article className="rounded-2xl border border-white/8 bg-slate-950/40 p-5">
          <h3 className="text-lg font-semibold text-white">Final video review</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Use the ready rough cut as the v1 final-review artifact until final export is added.
          </p>

          {latestReadyRoughCut ? (
            <div className="mt-4 rounded-2xl border border-white/8 bg-white/4 p-4 text-sm text-slate-300">
              <p className="font-medium text-white">Ready review asset</p>
              <p className="mt-2 break-all">{latestReadyRoughCut.file_path}</p>
            </div>
          ) : (
            <p className="mt-4 rounded-2xl border border-dashed border-white/10 bg-white/4 p-4 text-sm text-slate-300">
              A ready rough-cut asset is required before final approval.
            </p>
          )}

          {latestFinalApproval ? (
            <p className="mt-4 rounded-2xl border border-white/8 bg-white/4 px-4 py-3 text-sm text-slate-200">
              Latest final decision: {approvalDecisionLabels[latestFinalApproval.decision]}
            </p>
          ) : null}

          <div className="mt-5 flex flex-wrap gap-3">
            <button
              className="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-100 transition hover:border-emerald-200/50 hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!canReviewFinal || pendingAction !== null}
              onClick={() => runAction("approve-final", () => approveFinalVideo(project.id))}
              type="button"
            >
              {pendingAction === "approve-final" ? "Approving..." : "Approve final video"}
            </button>
            <button
              className="rounded-full border border-rose-300/30 bg-rose-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-rose-100 transition hover:border-rose-200/50 hover:bg-rose-400/20 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!canReviewFinal || pendingAction !== null}
              onClick={() => runAction("reject-final", () => rejectFinalVideo(project.id))}
              type="button"
            >
              {pendingAction === "reject-final" ? "Rejecting..." : "Reject final video"}
            </button>
          </div>
        </article>

        <article className="rounded-2xl border border-white/8 bg-slate-950/40 p-5">
          <h3 className="text-lg font-semibold text-white">Prepare publish job</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Metadata is copied from the current script so the publish approval shows exactly what
            will be posted.
          </p>
          <button
            className="mt-5 rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100 transition hover:border-cyan-200/50 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!canPreparePublish || pendingAction !== null || currentScript === null}
            onClick={() =>
              currentScript
                ? runAction("prepare-publish", () =>
                    preparePublishJob(project.id, {
                      description: currentScript.caption,
                      hashtags: currentScript.hashtags,
                      idempotency_key: `project-${project.id}-script-${currentScript.id}`,
                      platform: project.target_platform,
                      scheduled_for: null,
                      title: currentScript.title_options[0] ?? project.title,
                    }),
                  )
                : undefined
            }
            type="button"
          >
            {pendingAction === "prepare-publish" ? "Preparing..." : "Prepare publish job"}
          </button>
          {!canPreparePublish ? (
            <p className="mt-4 text-sm leading-6 text-slate-400">
              Final approval must move the project to ready-to-publish, and only one active publish
              job can exist for the current script.
            </p>
          ) : null}
        </article>
      </div>

      <div className="mt-6 grid gap-4">
        {publishJobs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 bg-slate-950/40 p-4 text-sm text-slate-300">
            No publish jobs prepared yet.
          </div>
        ) : (
          publishJobs.map((job) => (
            <article className="rounded-2xl border border-white/8 bg-slate-950/40 p-5" key={job.id}>
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <span className="rounded-full border border-amber-300/30 bg-amber-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-amber-100">
                    {publishJobStatusLabels[job.status]}
                  </span>
                  <h3 className="mt-3 text-lg font-semibold text-white">{job.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-300">{job.description}</p>
                </div>
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                  {formatTimestamp(job.scheduled_for)}
                </p>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {job.hashtags_json.map((hashtag) => (
                  <span
                    className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-100"
                    key={hashtag}
                  >
                    {hashtag}
                  </span>
                ))}
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-[1fr_1fr_auto_auto] md:items-end">
                <label className="grid gap-2 text-sm text-slate-300">
                  Schedule time
                  <input
                    className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50"
                    onChange={(event) => setScheduledFor(event.target.value)}
                    type="datetime-local"
                    value={scheduledFor}
                  />
                </label>
                <label className="grid gap-2 text-sm text-slate-300">
                  External/manual post id
                  <input
                    className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50"
                    onChange={(event) => setExternalPostId(event.target.value)}
                    placeholder="Optional"
                    value={externalPostId}
                  />
                </label>
                <button
                  className="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-100 transition hover:border-emerald-200/50 hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={job.status !== "pending_approval" || pendingAction !== null}
                  onClick={() =>
                    runAction(`approve-publish-${job.id}`, () => approvePublishJob(job.id))
                  }
                  type="button"
                >
                  Approve
                </button>
                <button
                  className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100 transition hover:border-cyan-200/50 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={job.status !== "approved" || pendingAction !== null}
                  onClick={() =>
                    runAction(`schedule-publish-${job.id}`, () =>
                      schedulePublishJob(job.id, {
                        scheduled_for: toIsoDateTime(scheduledFor),
                      }),
                    )
                  }
                  type="button"
                >
                  Schedule
                </button>
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
                <label className="grid gap-2 text-sm text-slate-300">
                  Manual publish notes
                  <input
                    className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50"
                    onChange={(event) => setManualPublishNotes(event.target.value)}
                    placeholder="Where it was posted, account used, or follow-up notes"
                    value={manualPublishNotes}
                  />
                </label>
                <button
                  className="rounded-full border border-amber-300/30 bg-amber-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-amber-100 transition hover:border-amber-200/50 hover:bg-amber-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={
                    !["approved", "scheduled"].includes(job.status) || pendingAction !== null
                  }
                  onClick={() =>
                    runAction(`mark-published-${job.id}`, () =>
                      markPublishJobPublished(job.id, {
                        external_post_id: externalPostId || null,
                        manual_publish_notes: manualPublishNotes || null,
                      }),
                    )
                  }
                  type="button"
                >
                  Mark published
                </button>
              </div>
            </article>
          ))
        )}
      </div>

      {error ? (
        <p className="mt-5 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          {error}
        </p>
      ) : null}
    </section>
  );
}
