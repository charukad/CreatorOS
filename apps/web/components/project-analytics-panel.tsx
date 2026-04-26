"use client";

import { useRouter } from "next/navigation";
import { startTransition, useState, type Dispatch, type SetStateAction } from "react";
import { useToast } from "./toast-provider";
import { queuePublishJobAnalyticsSync } from "../lib/api";
import type { BackgroundJob, ProjectAnalytics, PublishJob } from "../types/api";

type ProjectAnalyticsPanelProps = {
  analytics: ProjectAnalytics;
  jobs: BackgroundJob[];
  publishJobs: PublishJob[];
};

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

function formatPercent(value: number | null): string {
  return value === null ? "Not tracked" : `${(value * 100).toFixed(1)}%`;
}

export function ProjectAnalyticsPanel({ analytics, jobs, publishJobs }: ProjectAnalyticsPanelProps) {
  const router = useRouter();
  const { pushToast } = useToast();
  const [error, setError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [views, setViews] = useState("1000");
  const [likes, setLikes] = useState("80");
  const [comments, setComments] = useState("12");
  const [shares, setShares] = useState("10");
  const [avgViewDuration, setAvgViewDuration] = useState("18");
  const publishedJob = publishJobs.find((job) => job.status === "published") ?? null;
  const latestSnapshot = analytics.snapshots[0] ?? null;
  const activeAnalyticsJobs = jobs.filter(
    (job) =>
      job.job_type === "sync_analytics" &&
      ["queued", "running", "waiting_external"].includes(job.state),
  );
  const latestAnalyticsJob =
    activeAnalyticsJobs[0] ?? jobs.find((job) => job.job_type === "sync_analytics") ?? null;

  function queueSync() {
    if (!publishedJob) {
      return;
    }

    setError(null);
    setPendingAction("sync-analytics");
    startTransition(() => {
      void queuePublishJobAnalyticsSync(publishedJob.id, {
        avg_view_duration: Number(avgViewDuration),
        comments: Number(comments),
        likes: Number(likes),
        shares: Number(shares),
        views: Number(views),
      })
        .then(() => {
          pushToast({
            title: "Analytics sync queued",
            description: "The latest manual metrics were handed to the analytics worker for persistence and insight generation.",
            tone: "success",
          });
          router.refresh();
          setPendingAction(null);
        })
        .catch((actionError) => {
          const message =
            actionError instanceof Error ? actionError.message : "Unable to queue analytics sync.";
          setError(message);
          pushToast({
            title: "Analytics sync failed",
            description: message,
            tone: "error",
          });
          setPendingAction(null);
        });
    });
  }

  return (
    <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Analytics and learning loop</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
            Record post performance after publishing so future idea and script passes can learn
            from real outcomes instead of guesses.
          </p>
        </div>
        <div className="rounded-2xl border border-cyan-300/20 bg-cyan-400/10 px-4 py-3 text-sm text-cyan-50">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200/80">
            Latest snapshot
          </p>
          <p className="mt-2 font-medium">
            {latestSnapshot ? `${latestSnapshot.views.toLocaleString()} views` : "No data yet"}
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <article className="rounded-2xl border border-white/8 bg-slate-950/40 p-5">
          <h3 className="text-lg font-semibold text-white">Queued analytics sync</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            v1 accepts manual metrics, then sends them through a background worker so the learning
            loop has the same traceable logs and retry path as publishing and media jobs.
          </p>
          {latestAnalyticsJob ? (
            <div className="mt-4 rounded-2xl border border-white/8 bg-white/4 p-4 text-sm text-slate-200">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
                Latest analytics job
              </p>
              <p className="mt-2 font-medium">
                {latestAnalyticsJob.state.replaceAll("_", " ")} /{" "}
                {latestAnalyticsJob.progress_percent}% complete
              </p>
              {latestAnalyticsJob.error_message ? (
                <p className="mt-2 text-xs leading-5 text-slate-400">
                  {latestAnalyticsJob.error_message}
                </p>
              ) : null}
            </div>
          ) : null}
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {[
              ["Views", views, setViews],
              ["Likes", likes, setLikes],
              ["Comments", comments, setComments],
              ["Shares", shares, setShares],
              ["Avg view duration", avgViewDuration, setAvgViewDuration],
            ].map(([label, value, setter]) => (
              <label className="grid gap-2 text-sm text-slate-300" key={String(label)}>
                {String(label)}
                <input
                  className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50"
                  min="0"
                  onChange={(event) =>
                    (setter as Dispatch<SetStateAction<string>>)(event.target.value)
                  }
                  type="number"
                  value={String(value)}
                />
              </label>
            ))}
          </div>
          <button
            className="mt-5 rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100 transition hover:border-cyan-200/50 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={
              publishedJob === null || pendingAction !== null || activeAnalyticsJobs.length > 0
            }
            onClick={queueSync}
            type="button"
          >
            {pendingAction === "sync-analytics" ? "Queueing..." : "Queue analytics sync"}
          </button>
          {publishedJob === null ? (
            <p className="mt-4 text-sm leading-6 text-slate-400">
              Mark a publish job as published before syncing analytics.
            </p>
          ) : null}
          {activeAnalyticsJobs.length > 0 ? (
            <p className="mt-4 text-sm leading-6 text-slate-400">
              An analytics sync job is already active. Let the worker finish or use the job detail
              page to recover it before queueing another snapshot.
            </p>
          ) : null}
          {error ? (
            <p className="mt-4 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
              {error}
            </p>
          ) : null}
        </article>

        <article className="rounded-2xl border border-white/8 bg-slate-950/40 p-5">
          <h3 className="text-lg font-semibold text-white">Insights</h3>
          <div className="mt-5 grid gap-3">
            {analytics.insights.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-white/10 bg-white/4 p-4 text-sm text-slate-300">
                No insights yet. Sync analytics after publishing to generate the first learning.
              </p>
            ) : (
              analytics.insights.map((insight) => (
                <div className="rounded-2xl border border-white/8 bg-white/4 p-4" key={insight.id}>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
                    {insight.insight_type.replaceAll("_", " ")}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-100">{insight.summary}</p>
                  <p className="mt-3 text-xs uppercase tracking-[0.16em] text-slate-500">
                    Confidence {(insight.confidence_score * 100).toFixed(0)}%
                  </p>
                </div>
              ))
            )}
          </div>
        </article>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">CTR</p>
          <p className="mt-3 text-lg font-semibold text-white">
            {formatPercent(latestSnapshot?.ctr ?? null)}
          </p>
        </div>
        <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Avg duration
          </p>
          <p className="mt-3 text-lg font-semibold text-white">
            {latestSnapshot?.avg_view_duration ?? "Not tracked"}s
          </p>
        </div>
        <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Last synced
          </p>
          <p className="mt-3 text-sm font-semibold text-white">
            {latestSnapshot ? formatTimestamp(latestSnapshot.fetched_at) : "Never"}
          </p>
        </div>
      </div>
    </section>
  );
}
