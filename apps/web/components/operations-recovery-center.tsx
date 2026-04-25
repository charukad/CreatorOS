"use client";

import {
  assetStatusLabels,
  backgroundJobStateLabels,
  backgroundJobTypeLabels,
  projectStatusLabels,
} from "@creatoros/shared";
import Link from "next/link";
import type { ReactNode } from "react";
import { useAutoRefresh } from "./use-auto-refresh";
import type {
  ArtifactRetentionCandidate,
  ArtifactRetentionPlan,
  OperationsRecovery,
  RecoveryJob,
  RecoveryLog,
  WorkerPresence,
  WorkerStatus,
} from "../types/api";

type OperationsRecoveryCenterProps = {
  recovery: OperationsRecovery;
  retentionPlan: ArtifactRetentionPlan;
  workerPresence: WorkerPresence;
};

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatLabel(value: string): string {
  return value
    .split("_")
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function formatMetadata(metadata: Record<string, unknown>): string {
  return JSON.stringify(metadata, null, 2);
}

function workerStatusClassName(status: string): string {
  switch (status) {
    case "processing":
      return "border-emerald-300/30 bg-emerald-400/10 text-emerald-100";
    case "wakeup_received":
      return "border-cyan-300/30 bg-cyan-400/10 text-cyan-100";
    case "listening":
    case "polling":
      return "border-sky-300/30 bg-sky-400/10 text-sky-100";
    default:
      return "border-white/10 bg-white/5 text-slate-100";
  }
}

function JobRecoveryCard({ item }: { item: RecoveryJob }) {
  return (
    <article className="rounded-2xl border border-white/8 bg-slate-950/40 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full border border-rose-300/30 bg-rose-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-rose-100">
              {backgroundJobStateLabels[item.job.state]}
            </span>
            <span className="rounded-full border border-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100">
              {backgroundJobTypeLabels[item.job.job_type]}
            </span>
            <span className="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100">
              {projectStatusLabels[item.project_status]}
            </span>
          </div>
          <h3 className="mt-4 text-lg font-semibold text-white">{item.project_title}</h3>
          {item.job.error_message ? (
            <p className="mt-3 text-sm leading-6 text-rose-100">{item.job.error_message}</p>
          ) : item.latest_log_message ? (
            <p className="mt-3 text-sm leading-6 text-slate-300">{item.latest_log_message}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-3 lg:justify-end">
          <Link
            className="rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
            href={`/jobs/${item.job.id}`}
          >
            Open job
          </Link>
          <Link
            className="rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
            href={`/projects/${item.job.project_id}`}
          >
            Open project
          </Link>
        </div>
      </div>

      <div className="mt-4 grid gap-3 text-sm text-slate-300 md:grid-cols-3">
        <p>Progress: {item.job.progress_percent}%</p>
        <p>Attempts: {item.job.attempts}</p>
        <p>Updated: {formatTimestamp(item.job.updated_at)}</p>
      </div>
      {item.latest_log_event_type ? (
        <p className="mt-3 text-xs uppercase tracking-[0.16em] text-slate-500">
          Latest log: {item.latest_log_event_type.replaceAll("_", " ")}
          {item.latest_log_created_at ? ` at ${formatTimestamp(item.latest_log_created_at)}` : ""}
        </p>
      ) : null}
    </article>
  );
}

function RecoveryLogCard({ item }: { item: RecoveryLog }) {
  return (
    <article className="rounded-2xl border border-white/8 bg-slate-950/40 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full border border-amber-300/30 bg-amber-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-amber-100">
              {item.event_type.replaceAll("_", " ")}
            </span>
            <span className="rounded-full border border-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100">
              {item.level}
            </span>
          </div>
          <h3 className="mt-4 text-lg font-semibold text-white">{item.project_title}</h3>
          <p className="mt-3 text-sm leading-6 text-slate-300">{item.message}</p>
        </div>
        <div className="flex flex-wrap gap-3 lg:justify-end">
          <Link
            className="rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
            href={`/jobs/${item.background_job_id}`}
          >
            Open job
          </Link>
          <Link
            className="rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
            href={`/projects/${item.project_id}`}
          >
            Open project
          </Link>
        </div>
      </div>
      <pre className="mt-4 max-h-64 overflow-auto rounded-2xl border border-white/8 bg-black/30 p-4 text-xs leading-5 text-slate-300">
        {formatMetadata(item.metadata_json)}
      </pre>
      <p className="mt-3 text-xs uppercase tracking-[0.16em] text-slate-500">
        Logged {formatTimestamp(item.created_at)}
      </p>
    </article>
  );
}

function RetentionCandidateCard({ item }: { item: ArtifactRetentionCandidate }) {
  return (
    <article className="rounded-2xl border border-white/8 bg-slate-950/40 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap gap-2">
            <span
              className={
                item.safe_to_cleanup
                  ? "rounded-full border border-emerald-300/30 bg-emerald-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-100"
                  : "rounded-full border border-amber-300/30 bg-amber-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-amber-100"
              }
            >
              {item.safe_to_cleanup ? "Safe retention move" : "Manual check"}
            </span>
            <span className="rounded-full border border-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100">
              {assetStatusLabels[item.status]}
            </span>
            <span className="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100">
              {formatLabel(item.asset_type)}
            </span>
          </div>
          <h3 className="mt-4 text-lg font-semibold text-white">{item.project_title}</h3>
          <p className="mt-3 text-sm leading-6 text-slate-300">{item.reason}</p>
        </div>
        <div className="flex flex-wrap gap-3 lg:justify-end">
          <Link
            className="rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
            href={`/projects/${item.project_id}`}
          >
            Open project
          </Link>
        </div>
      </div>

      <div className="mt-4 grid gap-3 text-sm text-slate-300 md:grid-cols-3">
        <p>Action: {item.recommended_action.replaceAll("_", " ")}</p>
        <p>File: {item.file_exists ? "found" : "missing"}</p>
        <p>Size: {item.size_bytes === null ? "Not available" : formatBytes(item.size_bytes)}</p>
      </div>
      <p className="mt-3 break-all rounded-2xl border border-white/8 bg-black/30 p-4 text-xs leading-5 text-slate-300">
        {item.file_path}
      </p>
      {item.retention_manifest_path ? (
        <p className="mt-3 break-all text-xs uppercase tracking-[0.16em] text-slate-500">
          Retention manifest: {item.retention_manifest_path}
        </p>
      ) : null}
    </article>
  );
}

function WorkerStatusCard({ worker }: { worker: WorkerStatus }) {
  return (
    <article className="rounded-2xl border border-white/8 bg-slate-950/40 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap gap-2">
            <span
              className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${workerStatusClassName(worker.status)}`}
            >
              {formatLabel(worker.status)}
            </span>
            <span className="rounded-full border border-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100">
              {formatLabel(worker.worker_type)}
            </span>
            <span className="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100">
              {worker.redis_listener_enabled ? "Redis listener" : "Polling only"}
            </span>
          </div>
          <h3 className="mt-4 text-lg font-semibold text-white">{worker.worker_name}</h3>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            Last seen {formatTimestamp(worker.last_seen_at)}.
            {worker.last_event_type ? ` Latest event: ${formatLabel(worker.last_event_type)}.` : ""}
          </p>
        </div>
        <div className="text-sm text-slate-300 lg:text-right">
          <p>Processed jobs: {worker.processed_total}</p>
          <p>Wake-ups: {worker.wakeups_seen}</p>
          <p>Active jobs in loop: {worker.active_job_count}</p>
        </div>
      </div>
      <div className="mt-4 grid gap-3 text-sm text-slate-300 md:grid-cols-3">
        <p>Started: {formatTimestamp(worker.started_at)}</p>
        <p>Poll interval: {worker.poll_interval_seconds}s</p>
        <p>Listen timeout: {worker.listen_timeout_seconds}s</p>
      </div>
      {worker.last_job_id || worker.last_job_type ? (
        <p className="mt-3 text-xs uppercase tracking-[0.16em] text-slate-500">
          Last job: {worker.last_job_type ? formatLabel(worker.last_job_type) : "Unknown"}
          {worker.last_job_id ? ` · ${worker.last_job_id}` : ""}
        </p>
      ) : null}
    </article>
  );
}

function RecoverySection({
  children,
  count,
  description,
  title,
}: {
  children: ReactNode;
  count: number;
  description: string;
  title: string;
}) {
  return (
    <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">{title}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">{description}</p>
        </div>
        <span className="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100">
          {count} item{count === 1 ? "" : "s"}
        </span>
      </div>
      <div className="mt-5 grid gap-4">{children}</div>
    </section>
  );
}

function EmptyRecoveryState({ label }: { label: string }) {
  return (
    <p className="rounded-2xl border border-dashed border-white/10 bg-white/4 p-5 text-sm text-slate-300">
      No {label} need attention right now.
    </p>
  );
}

export function OperationsRecoveryCenter({
  recovery,
  retentionPlan,
  workerPresence,
}: OperationsRecoveryCenterProps) {
  const totalAttentionItems = recovery.summary.total_attention_items;
  const retentionSummary = retentionPlan.summary;
  useAutoRefresh({ enabled: workerPresence.summary.active_workers > 0, intervalMs: 8000 });

  return (
    <section className="grid gap-6">
      <section className="rounded-[2rem] border border-white/10 bg-white/5 p-8 shadow-2xl shadow-cyan-950/30 backdrop-blur">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-cyan-300">
              Operations recovery
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white sm:text-5xl">
              Keep blocked automation visible and recoverable.
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300">
              This page collects failed jobs, manual-intervention jobs, stale running work,
              quarantined downloads, duplicate asset warnings, and live worker presence into one
              operator view.
            </p>
          </div>
          <div className="rounded-2xl border border-amber-300/20 bg-amber-400/10 p-5 text-sm text-amber-50">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/70">
              Attention items
            </p>
            <p className="mt-3 text-4xl font-semibold text-white">{totalAttentionItems}</p>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-5">
        {Object.entries(recovery.summary).map(([key, value]) => (
          <article className="rounded-2xl border border-white/8 bg-white/4 p-4" key={key}>
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
              {key.replaceAll("_", " ")}
            </p>
            <p className="mt-2 text-3xl font-semibold text-white">{value}</p>
          </article>
        ))}
      </section>

      {workerPresence.summary.active_workers > 0 ? (
        <section className="rounded-2xl border border-cyan-300/20 bg-cyan-400/10 p-4 text-sm text-cyan-100">
          Auto-refresh is on while {workerPresence.summary.active_workers} worker
          {workerPresence.summary.active_workers === 1 ? "" : "s"} are actively listening,
          polling, or processing jobs.
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-6">
        {Object.entries(workerPresence.summary).map(([key, value]) => (
          <article className="rounded-2xl border border-white/8 bg-white/4 p-4" key={key}>
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
              {key.replaceAll("_", " ")}
            </p>
            <p className="mt-2 text-3xl font-semibold text-white">{value}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded-2xl border border-emerald-300/20 bg-emerald-400/10 p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-emerald-100/70">
            Safe retention candidates
          </p>
          <p className="mt-2 text-3xl font-semibold text-white">
            {retentionSummary.safe_candidate_count}
          </p>
        </article>
        <article className="rounded-2xl border border-white/8 bg-white/4 p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
            Total retention candidates
          </p>
          <p className="mt-2 text-3xl font-semibold text-white">
            {retentionSummary.candidate_count}
          </p>
        </article>
        <article className="rounded-2xl border border-white/8 bg-white/4 p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
            Reclaimable after approval
          </p>
          <p className="mt-2 text-3xl font-semibold text-white">
            {formatBytes(retentionSummary.total_reclaimable_bytes)}
          </p>
        </article>
      </section>

      <RecoverySection
        count={workerPresence.workers.length}
        description="Worker presence comes from Redis heartbeats written by the long-lived browser, media, publisher, and analytics service loops."
        title="Worker Status"
      >
        {workerPresence.workers.length === 0 ? (
          <EmptyRecoveryState label="worker heartbeats" />
        ) : (
          workerPresence.workers.map((worker) => (
            <WorkerStatusCard key={worker.worker_id} worker={worker} />
          ))
        )}
      </RecoverySection>

      <RecoverySection
        count={recovery.failed_jobs.length}
        description="Failed jobs are safe candidates for review and retry once the root cause is understood."
        title="Failed Jobs"
      >
        {recovery.failed_jobs.length === 0 ? (
          <EmptyRecoveryState label="failed jobs" />
        ) : (
          recovery.failed_jobs.map((item) => <JobRecoveryCard item={item} key={item.job.id} />)
        )}
      </RecoverySection>

      <RecoverySection
        count={recovery.waiting_jobs.length}
        description="Manual-intervention jobs usually need login, captcha, provider setup, or an operator note before they can continue."
        title="Manual Intervention"
      >
        {recovery.waiting_jobs.length === 0 ? (
          <EmptyRecoveryState label="manual-intervention jobs" />
        ) : (
          recovery.waiting_jobs.map((item) => <JobRecoveryCard item={item} key={item.job.id} />)
        )}
      </RecoverySection>

      <RecoverySection
        count={recovery.stale_running_jobs.length}
        description="Running jobs older than the configured threshold may need a worker restart or manual investigation."
        title="Stale Running Jobs"
      >
        {recovery.stale_running_jobs.length === 0 ? (
          <EmptyRecoveryState label="stale running jobs" />
        ) : (
          recovery.stale_running_jobs.map((item) => (
            <JobRecoveryCard item={item} key={item.job.id} />
          ))
        )}
      </RecoverySection>

      <RecoverySection
        count={recovery.quarantined_downloads.length}
        description="Quarantined downloads were intentionally kept out of approved asset paths because the worker could not safely map them."
        title="Quarantined Downloads"
      >
        {recovery.quarantined_downloads.length === 0 ? (
          <EmptyRecoveryState label="quarantined downloads" />
        ) : (
          recovery.quarantined_downloads.map((item) => (
            <RecoveryLogCard item={item} key={item.id} />
          ))
        )}
      </RecoverySection>

      <RecoverySection
        count={recovery.duplicate_asset_warnings.length}
        description="Duplicate checksum warnings help spot repeated outputs or accidental reuse before assets are approved."
        title="Duplicate Asset Warnings"
      >
        {recovery.duplicate_asset_warnings.length === 0 ? (
          <EmptyRecoveryState label="duplicate asset warnings" />
        ) : (
          recovery.duplicate_asset_warnings.map((item) => (
            <RecoveryLogCard item={item} key={item.id} />
          ))
        )}
      </RecoverySection>

      <RecoverySection
        count={retentionPlan.candidates.length}
        description="This is a planning-only view. Files are not deleted here; safe candidates should be moved with a retention manifest, while missing or superseded artifacts need a manual check first."
        title="Artifact Retention Plan"
      >
        {retentionPlan.candidates.length === 0 ? (
          <EmptyRecoveryState label="artifact retention candidates" />
        ) : (
          retentionPlan.candidates.map((item) => (
            <RetentionCandidateCard item={item} key={item.asset_id} />
          ))
        )}
      </RecoverySection>
    </section>
  );
}
