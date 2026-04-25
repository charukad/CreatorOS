"use client";

import {
  assetStatusLabels,
  backgroundJobStateLabels,
  backgroundJobTypeLabels,
} from "@creatoros/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";
import { useToast } from "./toast-provider";
import { useAutoRefresh } from "./use-auto-refresh";
import { cancelJob, markJobManualIntervention, resumeJob, retryJob } from "../lib/api";
import type { BackgroundJob, BackgroundJobDetail } from "../types/api";

type JobDetailProps = {
  detail: BackgroundJobDetail;
};

const retryPolicyMaxAttempts: Partial<Record<BackgroundJob["job_type"], number>> = {
  generate_audio_browser: 4,
  generate_visuals_browser: 4,
  compose_rough_cut: 3,
  final_export: 3,
  publish_content: 2,
  sync_analytics: 2,
};

function formatTimestamp(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "Not recorded";
}

function formatWorkflowValue(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function canCancelJobState(state: BackgroundJob["state"]): boolean {
  return state === "queued" || state === "waiting_external";
}

function canRetryJob(job: BackgroundJob): boolean {
  const maxAttempts = retryPolicyMaxAttempts[job.job_type];
  return (
    (job.state === "failed" || job.state === "cancelled") &&
    maxAttempts !== undefined &&
    job.attempts < maxAttempts
  );
}

function canResumeJob(job: BackgroundJob): boolean {
  return (
    job.state === "running" &&
    ["generate_audio_browser", "generate_visuals_browser", "compose_rough_cut", "final_export"].includes(
      job.job_type,
    )
  );
}

function logLevelClassName(level: string): string {
  switch (level) {
    case "error":
      return "border-rose-300/30 bg-rose-400/10 text-rose-100";
    case "warning":
      return "border-amber-300/30 bg-amber-400/10 text-amber-100";
    default:
      return "border-cyan-300/30 bg-cyan-400/10 text-cyan-100";
  }
}

function retryPolicyLabel(job: BackgroundJob): string {
  const maxAttempts = retryPolicyMaxAttempts[job.job_type];
  if (maxAttempts === undefined) {
    return "Manual retry is not available for this job type.";
  }
  return `${job.attempts}/${maxAttempts} execution attempt${maxAttempts === 1 ? "" : "s"} used`;
}

export function JobDetail({ detail }: JobDetailProps) {
  const router = useRouter();
  const { pushToast } = useToast();
  const [error, setError] = useState<string | null>(null);
  const [manualReason, setManualReason] = useState("");
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const { job } = detail;
  const isActiveJob = ["queued", "running", "waiting_external"].includes(job.state);
  useAutoRefresh({ enabled: isActiveJob, intervalMs: 6000 });

  function successMessage(actionKey: string): string {
    switch (actionKey) {
      case "cancel":
        return "The job moved to cancelled and will not continue without an explicit retry.";
      case "retry":
        return "A fresh attempt was queued using the persisted retry policy.";
      case "resume":
        return "The stale running job was reset so a worker can pick it up again.";
      case "manual-intervention":
        return "The job now waits for operator recovery with the note saved in its audit trail.";
      default:
        return "The job action completed successfully.";
    }
  }

  function runAction(actionKey: string, callback: () => Promise<unknown>) {
    setError(null);
    setPendingAction(actionKey);
    startTransition(() => {
      void callback()
        .then(() => {
          pushToast({
            title: "Job updated",
            description: successMessage(actionKey),
            tone: "success",
          });
          router.refresh();
          setPendingAction(null);
        })
        .catch((actionError) => {
          const message =
            actionError instanceof Error ? actionError.message : "Job action failed.";
          setError(message);
          pushToast({
            title: "Job action failed",
            description: message,
            tone: "error",
          });
          setPendingAction(null);
        });
    });
  }

  function handleManualIntervention() {
    if (manualReason.trim().length === 0) {
      const message = "Add a reason before marking this job for manual intervention.";
      setError(message);
      pushToast({
        title: "Manual intervention needs a reason",
        description: message,
        tone: "error",
      });
      return;
    }

    runAction("manual-intervention", () =>
      markJobManualIntervention(job.id, { reason: manualReason.trim() }),
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-8 px-6 py-10">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">
            Job detail
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-white">
            {backgroundJobTypeLabels[job.job_type]}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
            This screen shows the persisted job plan, linked attempts, related assets, and
            lifecycle logs so failed automation can be diagnosed without reading raw worker output.
          </p>
        </div>
        <Link
          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
          href={`/projects/${job.project_id}`}
        >
          Back to project
        </Link>
      </div>

      {error ? (
        <section className="rounded-2xl border border-rose-300/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          {error}
        </section>
      ) : null}

      {isActiveJob ? (
        <section className="rounded-2xl border border-cyan-300/20 bg-cyan-400/10 p-4 text-sm text-cyan-100">
          Auto-refresh is on while this job is active, so progress changes and worker state
          updates stay visible without reloading the page.
        </section>
      ) : null}

      <section className="grid gap-5 rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6 lg:grid-cols-4">
        <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">State</p>
          <p className="mt-3 text-lg font-semibold text-white">
            {backgroundJobStateLabels[job.state]}
          </p>
        </div>
        <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Provider
          </p>
          <p className="mt-3 text-lg font-semibold text-white">
            {job.provider_name ? formatWorkflowValue(job.provider_name) : "Manual"}
          </p>
        </div>
        <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Progress
          </p>
          <p className="mt-3 text-lg font-semibold text-white">{job.progress_percent}%</p>
        </div>
        <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Attempts
          </p>
          <p className="mt-3 text-lg font-semibold text-white">{job.attempts}</p>
        </div>
      </section>

      <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-white">Safe operations</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Cancel only before active execution; retry only after failed or cancelled states.
              Resume is for stale running browser/media jobs after a worker interruption.{" "}
              {retryPolicyLabel(job)}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-full border border-amber-300/30 bg-amber-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-amber-100 transition hover:border-amber-200/50 hover:bg-amber-400/20 disabled:cursor-not-allowed disabled:opacity-45"
              disabled={!canCancelJobState(job.state) || pendingAction !== null}
              onClick={() => runAction("cancel", () => cancelJob(job.id))}
              type="button"
            >
              {pendingAction === "cancel" ? "Cancelling..." : "Cancel job"}
            </button>
            <button
              className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100 transition hover:border-cyan-200/50 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-45"
              disabled={!canRetryJob(job) || pendingAction !== null}
              onClick={() => runAction("retry", () => retryJob(job.id))}
              type="button"
            >
              {pendingAction === "retry" ? "Retrying..." : "Retry job"}
            </button>
            <button
              className="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-100 transition hover:border-emerald-200/50 hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-45"
              disabled={!canResumeJob(job) || pendingAction !== null}
              onClick={() => runAction("resume", () => resumeJob(job.id))}
              type="button"
            >
              {pendingAction === "resume" ? "Resuming..." : "Resume stale job"}
            </button>
          </div>
        </div>
        <div className="mt-5 rounded-2xl border border-amber-300/20 bg-amber-400/10 p-4">
          <label className="grid gap-2 text-sm font-semibold text-amber-50">
            Manual intervention note
            <textarea
              className="min-h-20 rounded-2xl border border-amber-200/20 bg-slate-950/60 px-4 py-3 text-sm font-normal text-white outline-none transition placeholder:text-slate-500 focus:border-amber-200/50"
              onChange={(event) => setManualReason(event.target.value)}
              placeholder="What should the operator check before this job can continue?"
              value={manualReason}
            />
          </label>
          <button
            className="mt-3 rounded-full border border-amber-200/30 bg-amber-300/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-amber-50 transition hover:bg-amber-300/20 disabled:cursor-not-allowed disabled:opacity-45"
            disabled={job.state === "completed" || pendingAction !== null}
            onClick={handleManualIntervention}
            type="button"
          >
            {pendingAction === "manual-intervention"
              ? "Marking..."
              : "Mark manual intervention required"}
          </button>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <article className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
          <h2 className="text-xl font-semibold text-white">Generation attempts</h2>
          <div className="mt-5 grid gap-3">
            {detail.generation_attempts.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-white/10 bg-white/4 p-4 text-sm text-slate-300">
                This job does not use per-scene generation attempts.
              </p>
            ) : (
              detail.generation_attempts.map((attempt) => (
                <div className="rounded-2xl border border-white/8 bg-white/4 p-4" key={attempt.id}>
                  <p className="text-sm font-semibold text-white">
                    {attempt.scene_id ? `Scene ${attempt.scene_id.slice(0, 8)}` : "Script level"}
                  </p>
                  <p className="mt-2 text-sm text-slate-300">
                    {backgroundJobStateLabels[attempt.state]} via{" "}
                    {formatWorkflowValue(attempt.provider_name)}
                  </p>
                  {attempt.error_message ? (
                    <p className="mt-3 rounded-xl border border-rose-300/20 bg-rose-400/10 px-3 py-2 text-sm text-rose-100">
                      {attempt.error_message}
                    </p>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </article>

        <article className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
          <h2 className="text-xl font-semibold text-white">Related assets</h2>
          <div className="mt-5 grid gap-3">
            {detail.related_assets.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-white/10 bg-white/4 p-4 text-sm text-slate-300">
                No asset placeholders are linked to this job yet.
              </p>
            ) : (
              detail.related_assets.map((asset) => (
                <div className="rounded-2xl border border-white/8 bg-white/4 p-4" key={asset.id}>
                  <p className="text-sm font-semibold text-white">
                    {formatWorkflowValue(asset.asset_type)}
                  </p>
                  <p className="mt-2 text-sm text-slate-300">
                    {assetStatusLabels[asset.status]} · {asset.file_path ?? "No file yet"}
                  </p>
                </div>
              ))
            )}
          </div>
        </article>
      </section>

      <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
        <h2 className="text-xl font-semibold text-white">Job timeline</h2>
        <div className="mt-5 grid gap-3">
          {detail.job_logs.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-white/10 bg-white/4 p-4 text-sm text-slate-300">
              No lifecycle logs have been recorded for this job yet.
            </p>
          ) : (
            detail.job_logs.map((log) => (
              <article className="rounded-2xl border border-white/8 bg-white/4 p-4" key={log.id}>
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <span
                      className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${logLevelClassName(log.level)}`}
                    >
                      {log.level}
                    </span>
                    <h3 className="mt-3 text-base font-semibold text-white">
                      {formatWorkflowValue(log.event_type)}
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-slate-300">{log.message}</p>
                  </div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    {formatTimestamp(log.created_at)}
                  </p>
                </div>
              </article>
            ))
          )}
        </div>
      </section>
    </main>
  );
}
