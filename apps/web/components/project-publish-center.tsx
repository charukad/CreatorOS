"use client";

import { approvalDecisionLabels, publishJobStatusLabels } from "@creatoros/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";
import {
  approveFinalVideo,
  approvePublishJob,
  markPublishJobPublished,
  preparePublishJob,
  queuePublishJob,
  rejectFinalVideo,
  schedulePublishJob,
  updatePublishJobMetadata,
} from "../lib/api";
import type {
  ApprovalRecord,
  Asset,
  BackgroundJob,
  Project,
  ProjectScript,
  PublishJob,
} from "../types/api";

type ProjectPublishCenterProps = {
  approvals: ApprovalRecord[];
  assets: Asset[];
  currentScript: ProjectScript | null;
  jobs: BackgroundJob[];
  project: Project;
  publishJobs: PublishJob[];
};

type PublishJobMetadataDraft = {
  title: string;
  description: string;
  hashtags: string;
  scheduledFor: string;
  thumbnailAssetId: string;
  platformSettingsJson: string;
  changeNotes: string;
};

type PublishCommandRow = {
  activeHandoffJob: BackgroundJob | null;
  calendarLabel: string;
  handoffPath: string | null;
  job: PublishJob;
  laneClassName: string;
  laneDescription: string;
  laneLabel: string;
  latestHandoffJob: BackgroundJob | null;
};

function formatTimestamp(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "Not set";
}

function fromIsoDateTime(value: string | null): string {
  return value ? new Date(value).toISOString().slice(0, 16) : "";
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

function formatHashtags(hashtags: string[]): string {
  return hashtags.join(", ");
}

function parseHashtags(value: string): string[] {
  return value
    .split(/[,\n]+/)
    .map((hashtag) => hashtag.trim())
    .filter(Boolean);
}

function parsePlatformSettings(value: string): Record<string, unknown> | null {
  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return null;
  }

  const parsedValue = JSON.parse(trimmedValue) as unknown;
  if (
    parsedValue === null ||
    typeof parsedValue !== "object" ||
    Array.isArray(parsedValue)
  ) {
    throw new Error("Platform settings must be a JSON object.");
  }

  return parsedValue as Record<string, unknown>;
}

function createPublishJobMetadataDraft(job: PublishJob): PublishJobMetadataDraft {
  const thumbnailAssetId =
    typeof job.metadata_json.thumbnail_asset_id === "string"
      ? job.metadata_json.thumbnail_asset_id
      : "";
  const platformSettings =
    job.metadata_json.platform_settings &&
    typeof job.metadata_json.platform_settings === "object"
      ? JSON.stringify(job.metadata_json.platform_settings, null, 2)
      : "";

  return {
    title: job.title,
    description: job.description,
    hashtags: formatHashtags(job.hashtags_json),
    scheduledFor: fromIsoDateTime(job.scheduled_for),
    thumbnailAssetId,
    platformSettingsJson: platformSettings,
    changeNotes: "",
  };
}

function getPayloadString(job: BackgroundJob, key: string): string | null {
  const value = job.payload_json[key];
  return typeof value === "string" ? value : null;
}

function isActiveHandoffJob(job: BackgroundJob): boolean {
  return ["queued", "running", "waiting_external"].includes(job.state);
}

function sortByNewestJob(left: BackgroundJob, right: BackgroundJob): number {
  return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
}

function sortByPublishCalendar(left: PublishJob, right: PublishJob): number {
  const statusPriority: Record<PublishJob["status"], number> = {
    pending_approval: 0,
    approved: 1,
    scheduled: 2,
    published: 4,
    failed: 5,
    cancelled: 5,
  };
  const priorityDelta = statusPriority[left.status] - statusPriority[right.status];
  if (priorityDelta !== 0) {
    return priorityDelta;
  }

  const leftTime = left.scheduled_for
    ? new Date(left.scheduled_for).getTime()
    : Number.MAX_SAFE_INTEGER;
  const rightTime = right.scheduled_for
    ? new Date(right.scheduled_for).getTime()
    : Number.MAX_SAFE_INTEGER;
  if (leftTime !== rightTime) {
    return leftTime - rightTime;
  }

  return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
}

function describePublishLane(
  job: PublishJob,
  activeHandoffJob: BackgroundJob | null,
): Pick<PublishCommandRow, "laneClassName" | "laneDescription" | "laneLabel"> {
  if (job.status === "published") {
    return {
      laneClassName: "border-emerald-300/30 bg-emerald-400/10 text-emerald-100",
      laneDescription: "Manual completion has been recorded.",
      laneLabel: "Published",
    };
  }

  if (activeHandoffJob?.state === "waiting_external") {
    return {
      laneClassName: "border-amber-300/30 bg-amber-400/10 text-amber-100",
      laneDescription: "Upload manually, then mark the job as published.",
      laneLabel: "Manual upload waiting",
    };
  }

  if (activeHandoffJob) {
    return {
      laneClassName: "border-cyan-300/30 bg-cyan-400/10 text-cyan-100",
      laneDescription: "Publisher worker is preparing the handoff package.",
      laneLabel: "Handoff in progress",
    };
  }

  if (job.status === "scheduled") {
    return {
      laneClassName: "border-cyan-300/30 bg-cyan-400/10 text-cyan-100",
      laneDescription: "Scheduled and ready for the handoff worker.",
      laneLabel: "Scheduled",
    };
  }

  if (job.status === "approved") {
    return {
      laneClassName: "border-emerald-300/30 bg-emerald-400/10 text-emerald-100",
      laneDescription: "Approved and ready to queue a publish handoff.",
      laneLabel: "Ready to handoff",
    };
  }

  if (job.status === "pending_approval") {
    return {
      laneClassName: "border-amber-300/30 bg-amber-400/10 text-amber-100",
      laneDescription: "Review the exact metadata before publishing.",
      laneLabel: "Needs approval",
    };
  }

  return {
    laneClassName: "border-rose-300/30 bg-rose-400/10 text-rose-100",
    laneDescription: "This publish job needs manual recovery.",
    laneLabel: publishJobStatusLabels[job.status],
  };
}

function buildPublishCommandRows(
  publishJobs: PublishJob[],
  jobs: BackgroundJob[],
): PublishCommandRow[] {
  return [...publishJobs].sort(sortByPublishCalendar).map((job) => {
    const handoffJobs = jobs
      .filter(
        (workflowJob) =>
          workflowJob.job_type === "publish_content" &&
          getPayloadString(workflowJob, "publish_job_id") === job.id,
      )
      .sort(sortByNewestJob);
    const activeHandoffJob = handoffJobs.find(isActiveHandoffJob) ?? null;
    const latestHandoffJob = handoffJobs[0] ?? null;
    const lane = describePublishLane(job, activeHandoffJob);

    return {
      ...lane,
      activeHandoffJob,
      calendarLabel: job.scheduled_for ? formatTimestamp(job.scheduled_for) : "No publish time",
      handoffPath: latestHandoffJob ? getPayloadString(latestHandoffJob, "handoff_path") : null,
      job,
      latestHandoffJob,
    };
  });
}

export function ProjectPublishCenter({
  approvals,
  assets,
  currentScript,
  jobs,
  project,
  publishJobs,
}: ProjectPublishCenterProps) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [scheduledFor, setScheduledFor] = useState(defaultScheduleValue);
  const [externalPostId, setExternalPostId] = useState("");
  const [manualPublishNotes, setManualPublishNotes] = useState("");
  const [metadataDrafts, setMetadataDrafts] = useState<Record<string, PublishJobMetadataDraft>>(
    {},
  );

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
  const publishCommandRows = buildPublishCommandRows(publishJobs, jobs);
  const waitingHandoffCount = publishCommandRows.filter(
    (row) => row.activeHandoffJob?.state === "waiting_external",
  ).length;
  const scheduledPublishCount = publishCommandRows.filter(
    (row) => row.job.status === "scheduled",
  ).length;
  const readyHandoffCount = publishCommandRows.filter(
    (row) => row.job.status === "approved" && row.activeHandoffJob === null,
  ).length;
  const publishedCount = publishCommandRows.filter((row) => row.job.status === "published").length;

  function runAction(actionKey: string, callback: () => Promise<unknown>) {
    setError(null);
    setPendingAction(actionKey);
    startTransition(() => {
      void Promise.resolve()
        .then(callback)
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

  function getMetadataDraft(job: PublishJob): PublishJobMetadataDraft {
    return metadataDrafts[job.id] ?? createPublishJobMetadataDraft(job);
  }

  function updateMetadataDraft(job: PublishJob, patch: Partial<PublishJobMetadataDraft>) {
    setMetadataDrafts((currentDrafts) => ({
      ...currentDrafts,
      [job.id]: {
        ...createPublishJobMetadataDraft(job),
        ...currentDrafts[job.id],
        ...patch,
      },
    }));
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

      <div className="mt-6 rounded-[1.5rem] border border-white/10 bg-slate-950/40 p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Publishing calendar and queue</h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              A single command board for approval, schedule, handoff, and manual upload status.
              This keeps queued publish work visible before anything is marked live.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
            <div className="rounded-2xl border border-emerald-300/20 bg-emerald-400/10 px-3 py-2">
              <p className="text-lg font-semibold text-emerald-50">{readyHandoffCount}</p>
              <p className="text-[10px] uppercase tracking-[0.16em] text-emerald-100/80">
                Ready
              </p>
            </div>
            <div className="rounded-2xl border border-cyan-300/20 bg-cyan-400/10 px-3 py-2">
              <p className="text-lg font-semibold text-cyan-50">{scheduledPublishCount}</p>
              <p className="text-[10px] uppercase tracking-[0.16em] text-cyan-100/80">
                Scheduled
              </p>
            </div>
            <div className="rounded-2xl border border-amber-300/20 bg-amber-400/10 px-3 py-2">
              <p className="text-lg font-semibold text-amber-50">{waitingHandoffCount}</p>
              <p className="text-[10px] uppercase tracking-[0.16em] text-amber-100/80">
                Waiting
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
              <p className="text-lg font-semibold text-white">{publishedCount}</p>
              <p className="text-[10px] uppercase tracking-[0.16em] text-slate-300">
                Published
              </p>
            </div>
          </div>
        </div>

        {publishCommandRows.length === 0 ? (
          <div className="mt-5 rounded-2xl border border-dashed border-white/10 bg-white/4 p-4 text-sm text-slate-300">
            No publish calendar entries yet. Prepare a publish job after final approval to create
            the first queue item.
          </div>
        ) : (
          <div className="mt-5 grid gap-3">
            {publishCommandRows.map((row) => (
              <article
                className="rounded-2xl border border-white/8 bg-white/4 p-4"
                key={`calendar-${row.job.id}`}
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap gap-2">
                      <span
                        className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${row.laneClassName}`}
                      >
                        {row.laneLabel}
                      </span>
                      <span className="rounded-full border border-white/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-100">
                        {row.job.platform}
                      </span>
                    </div>
                    <h4 className="mt-3 text-base font-semibold text-white">{row.job.title}</h4>
                    <p className="mt-1 text-sm leading-6 text-slate-300">
                      {row.laneDescription}
                    </p>
                  </div>
                  <div className="text-left text-xs uppercase tracking-[0.16em] text-slate-500 lg:text-right">
                    <p>{row.calendarLabel}</p>
                    {row.latestHandoffJob ? (
                      <Link
                        className="mt-2 inline-flex rounded-full border border-white/10 px-3 py-1 text-[11px] text-slate-200 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
                        href={`/jobs/${row.latestHandoffJob.id}`}
                      >
                        Open handoff job
                      </Link>
                    ) : null}
                  </div>
                </div>
                {row.handoffPath ? (
                  <p className="mt-3 break-all rounded-2xl border border-white/8 bg-slate-950/50 px-3 py-2 text-xs text-slate-300">
                    Handoff package: {row.handoffPath}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </div>

      <div className="mt-6 grid gap-4">
        {publishJobs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 bg-slate-950/40 p-4 text-sm text-slate-300">
            No publish jobs prepared yet.
          </div>
        ) : (
          publishCommandRows.map((row) => {
            const { activeHandoffJob, job, latestHandoffJob } = row;
            const metadataDraft = getMetadataDraft(job);
            const canEditMetadata = ["pending_approval", "approved"].includes(job.status);
            const canQueueHandoff =
              ["approved", "scheduled"].includes(job.status) && activeHandoffJob === null;
            const thumbnailOptions = assets.filter(
              (asset) =>
                asset.script_id === job.script_id &&
                ["thumbnail", "scene_image"].includes(asset.asset_type) &&
                asset.status === "ready",
            );

            return (
              <article
                className="rounded-2xl border border-white/8 bg-slate-950/40 p-5"
                key={job.id}
              >
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

              <div className="mt-5 rounded-2xl border border-cyan-300/10 bg-cyan-400/5 p-4">
                <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-cyan-50">Metadata editor</p>
                    <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-400">
                      This is the approval-safe draft of what will be posted. Saving changes to an
                      approved job sends it back to pending approval.
                    </p>
                  </div>
                  {!canEditMetadata ? (
                    <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">
                      Locked after scheduling
                    </span>
                  ) : null}
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <label className="grid gap-2 text-sm text-slate-300">
                    Title
                    <input
                      className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50 disabled:opacity-50"
                      disabled={!canEditMetadata || pendingAction !== null}
                      onChange={(event) =>
                        updateMetadataDraft(job, { title: event.target.value })
                      }
                      value={metadataDraft.title}
                    />
                  </label>
                  <label className="grid gap-2 text-sm text-slate-300">
                    Planned time
                    <input
                      className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50 disabled:opacity-50"
                      disabled={!canEditMetadata || pendingAction !== null}
                      onChange={(event) =>
                        updateMetadataDraft(job, { scheduledFor: event.target.value })
                      }
                      type="datetime-local"
                      value={metadataDraft.scheduledFor}
                    />
                  </label>
                </div>

                <label className="mt-3 grid gap-2 text-sm text-slate-300">
                  Description
                  <textarea
                    className="min-h-28 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50 disabled:opacity-50"
                    disabled={!canEditMetadata || pendingAction !== null}
                    onChange={(event) =>
                      updateMetadataDraft(job, { description: event.target.value })
                    }
                    value={metadataDraft.description}
                  />
                </label>

                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <label className="grid gap-2 text-sm text-slate-300">
                    Hashtags
                    <input
                      className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50 disabled:opacity-50"
                      disabled={!canEditMetadata || pendingAction !== null}
                      onChange={(event) =>
                        updateMetadataDraft(job, { hashtags: event.target.value })
                      }
                      placeholder="#CreatorOS, #Shorts"
                      value={metadataDraft.hashtags}
                    />
                  </label>
                  <label className="grid gap-2 text-sm text-slate-300">
                    Thumbnail asset
                    <select
                      className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50 disabled:opacity-50"
                      disabled={!canEditMetadata || pendingAction !== null}
                      onChange={(event) =>
                        updateMetadataDraft(job, { thumbnailAssetId: event.target.value })
                      }
                      value={metadataDraft.thumbnailAssetId}
                    >
                      <option value="">No thumbnail selected</option>
                      {thumbnailOptions.map((asset) => (
                        <option key={asset.id} value={asset.id}>
                          {asset.asset_type} - {asset.file_path ?? asset.id}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <label className="mt-3 grid gap-2 text-sm text-slate-300">
                  Platform settings JSON
                  <textarea
                    className="min-h-24 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 font-mono text-xs text-white outline-none transition focus:border-cyan-300/50 disabled:opacity-50"
                    disabled={!canEditMetadata || pendingAction !== null}
                    onChange={(event) =>
                      updateMetadataDraft(job, {
                        platformSettingsJson: event.target.value,
                      })
                    }
                    placeholder={'{"privacy": "private", "playlist_id": "optional"}'}
                    value={metadataDraft.platformSettingsJson}
                  />
                </label>

                <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
                  <label className="grid gap-2 text-sm text-slate-300">
                    Change notes
                    <input
                      className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50 disabled:opacity-50"
                      disabled={!canEditMetadata || pendingAction !== null}
                      onChange={(event) =>
                        updateMetadataDraft(job, { changeNotes: event.target.value })
                      }
                      placeholder="Why this metadata changed"
                      value={metadataDraft.changeNotes}
                    />
                  </label>
                  <button
                    className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100 transition hover:border-cyan-200/50 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={!canEditMetadata || pendingAction !== null}
                    onClick={() =>
                      runAction(`update-publish-metadata-${job.id}`, () =>
                        updatePublishJobMetadata(job.id, {
                          change_notes: metadataDraft.changeNotes.trim() || null,
                          description: metadataDraft.description.trim(),
                          hashtags: parseHashtags(metadataDraft.hashtags),
                          platform_settings: parsePlatformSettings(
                            metadataDraft.platformSettingsJson,
                          ),
                          scheduled_for: metadataDraft.scheduledFor
                            ? toIsoDateTime(metadataDraft.scheduledFor)
                            : null,
                          thumbnail_asset_id: metadataDraft.thumbnailAssetId || null,
                          title: metadataDraft.title.trim(),
                        }),
                      )
                    }
                    type="button"
                  >
                    {pendingAction === `update-publish-metadata-${job.id}`
                      ? "Saving..."
                      : "Save metadata"}
                  </button>
                </div>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-[1fr_1fr_auto_auto] md:items-end">
                <label className="grid gap-2 text-sm text-slate-300">
                  Schedule time
                  <input
                    className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50"
                    onChange={(event) => {
                      setScheduledFor(event.target.value);
                      updateMetadataDraft(job, { scheduledFor: event.target.value });
                    }}
                    type="datetime-local"
                    value={metadataDraft.scheduledFor || scheduledFor}
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
                        scheduled_for: toIsoDateTime(metadataDraft.scheduledFor || scheduledFor),
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
              <div className="mt-4 rounded-2xl border border-white/8 bg-white/4 p-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-white">Publish handoff queue</p>
                    <p className="mt-1 text-xs leading-5 text-slate-400">
                      Queue a background handoff that generates the exact manual upload package and
                      waits for your platform confirmation.
                    </p>
                  </div>
                  <button
                    className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100 transition hover:border-cyan-200/50 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={!canQueueHandoff || pendingAction !== null}
                    onClick={() =>
                      runAction(`queue-publish-handoff-${job.id}`, () => queuePublishJob(job.id))
                    }
                    type="button"
                  >
                    {pendingAction === `queue-publish-handoff-${job.id}`
                      ? "Queueing..."
                      : "Queue handoff"}
                  </button>
                </div>
                {latestHandoffJob ? (
                  <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-300">
                    <span className="rounded-full border border-white/10 px-3 py-1 uppercase tracking-[0.16em]">
                      {latestHandoffJob.state.replaceAll("_", " ")}
                    </span>
                    <span>Progress {latestHandoffJob.progress_percent}%</span>
                    <span>
                      Handoff file:{" "}
                      {typeof latestHandoffJob.payload_json.handoff_path === "string"
                        ? latestHandoffJob.payload_json.handoff_path
                        : "Not generated yet"}
                    </span>
                  </div>
                ) : null}
                {!canQueueHandoff && latestHandoffJob === null ? (
                  <p className="mt-3 text-xs leading-5 text-slate-500">
                    Approve or schedule the publish job before queueing a handoff.
                  </p>
                ) : null}
              </div>
              </article>
            );
          })
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
