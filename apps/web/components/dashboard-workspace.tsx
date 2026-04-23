"use client";

import { projectStatusLabels, type ProjectStatus } from "@creatoros/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useDeferredValue, useState } from "react";
import { BrandProfileForm } from "./brand-profile-form";
import { ProjectForm } from "./project-form";
import { StatusBadge } from "./status-badge";
import { createBrandProfile, createProject } from "../lib/api";
import type {
  AccountAnalytics,
  AccountAnalyticsSummaryItem,
  ApprovalRecord,
  BackgroundJob,
  BrandProfile,
  BrandProfilePayload,
  OperationsRecovery,
  Project,
  ProjectActivity,
  ProjectPayload,
} from "../types/api";

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString();
}

function formatNumber(value: number): string {
  return value.toLocaleString();
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatDuration(value: number | null): string {
  return value === null ? "Not tracked" : `${value.toFixed(1)}s`;
}

function getStatusCount(projects: Project[], status: ProjectStatus): number {
  return projects.filter((project) => project.status === status).length;
}

const approvalInboxStatuses = new Set<ProjectStatus>([
  "idea_pending_approval",
  "script_pending_approval",
  "asset_pending_approval",
  "final_pending_approval",
  "ready_to_publish",
]);

type DashboardWorkspaceProps = {
  initialActivity: ProjectActivity[];
  initialAccountAnalytics: AccountAnalytics | null;
  initialApprovals: ApprovalRecord[];
  initialBrandProfiles: BrandProfile[];
  initialError: string | null;
  initialJobs: BackgroundJob[];
  initialOperationsRecovery: OperationsRecovery | null;
  initialProjects: Project[];
};

export function DashboardWorkspace({
  initialActivity,
  initialAccountAnalytics,
  initialApprovals,
  initialBrandProfiles,
  initialError,
  initialJobs,
  initialOperationsRecovery,
  initialProjects,
}: DashboardWorkspaceProps) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search.trim().toLowerCase());
  const brandProfiles = initialBrandProfiles;
  const jobs = initialJobs;
  const projects = initialProjects;

  const filteredBrandProfiles = !deferredSearch
    ? brandProfiles
    : brandProfiles.filter((brandProfile) =>
        [brandProfile.channel_name, brandProfile.niche, brandProfile.target_audience]
          .join(" ")
          .toLowerCase()
          .includes(deferredSearch),
      );

  const filteredProjects = !deferredSearch
    ? projects
    : projects.filter((project) =>
        [project.title, project.target_platform, project.objective, project.notes ?? ""]
          .join(" ")
          .toLowerCase()
          .includes(deferredSearch),
      );
  const approvalInboxProjects = projects.filter((project) =>
    approvalInboxStatuses.has(project.status),
  );
  const recentProjects = [...projects]
    .sort((first, second) => Date.parse(second.updated_at) - Date.parse(first.updated_at))
    .slice(0, 5);
  const activeJobs = jobs.filter((job) =>
    ["queued", "running", "waiting_external"].includes(job.state),
  );
  const failedJobs = jobs.filter((job) => job.state === "failed");
  const attentionItemCount = initialOperationsRecovery?.summary.total_attention_items ?? 0;
  const accountAnalytics = initialAccountAnalytics;
  const strongestSummary =
    accountAnalytics?.hook_patterns[0] ??
    accountAnalytics?.duration_buckets[0] ??
    accountAnalytics?.content_types[0] ??
    null;

  async function handleCreateBrandProfile(payload: BrandProfilePayload) {
    await createBrandProfile(payload);
    router.refresh();
  }

  async function handleCreateProject(payload: ProjectPayload) {
    await createProject(payload);
    router.refresh();
  }

  const brandProfileNameById = new Map(
    brandProfiles.map((brandProfile) => [brandProfile.id, brandProfile.channel_name]),
  );

  return (
    <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
      <div className="grid gap-6">
        <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">
                Workspace
              </p>
              <h2 className="mt-2 text-2xl font-semibold text-white">
                Manage brand profiles and active content projects
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                This dashboard now talks to the FastAPI backend, so you can create and edit the
                core records the rest of the pipeline depends on.
              </p>
            </div>
            <label className="grid gap-2 text-sm text-slate-200">
              Search
              <input
                className="min-w-72 rounded-full border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search channels, niches, titles, objectives..."
                value={search}
              />
            </label>
          </div>

          {approvalInboxProjects.length > 0 ? (
            <div className="mt-6 rounded-2xl border border-amber-300/20 bg-amber-400/10 p-5">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-100">
                Approval inbox
              </p>
              <p className="mt-2 text-sm leading-6 text-amber-50/80">
                {approvalInboxProjects.length} project
                {approvalInboxProjects.length === 1 ? " needs" : "s need"} a human decision before
                automation can continue.
              </p>
              <div className="mt-4 grid gap-3">
                {approvalInboxProjects.slice(0, 4).map((project) => (
                  <Link
                    className="rounded-2xl border border-amber-200/20 bg-slate-950/40 px-4 py-3 text-sm text-amber-50 transition hover:bg-amber-300/10"
                    href={`/projects/${project.id}`}
                    key={`approval-${project.id}`}
                  >
                    <span className="font-semibold">{project.title}</span>
                    <span className="ml-2 text-amber-100/70">
                      {projectStatusLabels[project.status]}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          ) : null}

          <div className="mt-6 grid gap-4 md:grid-cols-4">
            <article className="rounded-2xl border border-white/8 bg-white/4 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                Brand profiles
              </p>
              <p className="mt-3 text-3xl font-semibold text-white">{brandProfiles.length}</p>
            </article>
            <article className="rounded-2xl border border-white/8 bg-white/4 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                Draft projects
              </p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {getStatusCount(projects, "draft")}
              </p>
            </article>
            <article className="rounded-2xl border border-white/8 bg-white/4 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                Script approval
              </p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {getStatusCount(projects, "script_pending_approval")}
              </p>
            </article>
            <article className="rounded-2xl border border-white/8 bg-white/4 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                Open jobs
              </p>
              <p className="mt-3 text-3xl font-semibold text-white">{activeJobs.length}</p>
            </article>
          </div>
        </section>

        {initialError ? (
          <section className="rounded-[1.5rem] border border-rose-400/30 bg-rose-500/10 p-5 text-sm text-rose-100">
            <p className="font-semibold">Unable to sync the dashboard.</p>
            <p className="mt-2">{initialError}</p>
            <button
              className="mt-4 rounded-full border border-rose-300/30 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-rose-50 transition hover:bg-rose-400/10"
              onClick={() => router.refresh()}
              type="button"
            >
              Retry
            </button>
          </section>
        ) : null}

        <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="text-xl font-semibold text-white">Brand profiles</h3>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Define each creator voice once, then attach projects to the right profile.
              </p>
            </div>
            <span className="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100">
              {filteredBrandProfiles.length} visible
            </span>
          </div>

          {filteredBrandProfiles.length === 0 ? (
            <div className="mt-6 rounded-2xl border border-dashed border-white/10 bg-white/4 p-6 text-sm text-slate-300">
              <p className="font-semibold text-white">No brand profiles yet.</p>
              <p className="mt-2">
                Start by adding one creator profile so projects can inherit tone, audience, and
                style preferences.
              </p>
            </div>
          ) : null}

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {filteredBrandProfiles.map((brandProfile) => (
              <article
                key={brandProfile.id}
                className="rounded-2xl border border-white/8 bg-white/4 p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
                      {brandProfile.niche}
                    </p>
                    <h4 className="mt-2 text-lg font-semibold text-white">
                      {brandProfile.channel_name}
                    </h4>
                  </div>
                  <Link
                    className="rounded-full border border-white/10 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-200 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
                    href={`/brand-profiles/${brandProfile.id}`}
                  >
                    Edit
                  </Link>
                </div>
                <p className="mt-4 text-sm leading-6 text-slate-300">
                  {brandProfile.target_audience}
                </p>
                <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-300">
                  <span className="rounded-full border border-white/10 px-3 py-1">
                    Tone: {brandProfile.tone}
                  </span>
                  <span className="rounded-full border border-white/10 px-3 py-1">
                    Hook: {brandProfile.hook_style}
                  </span>
                  <span className="rounded-full border border-white/10 px-3 py-1">
                    CTA: {brandProfile.cta_style}
                  </span>
                </div>
                <p className="mt-4 text-xs uppercase tracking-[0.16em] text-slate-500">
                  Updated {formatDate(brandProfile.updated_at)}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="text-xl font-semibold text-white">Projects</h3>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Create projects against a brand profile so the next pipeline steps can inherit the
                right context.
              </p>
            </div>
            <span className="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100">
              {filteredProjects.length} visible
            </span>
          </div>

          {filteredProjects.length === 0 ? (
            <div className="mt-6 rounded-2xl border border-dashed border-white/10 bg-white/4 p-6 text-sm text-slate-300">
              <p className="font-semibold text-white">No projects yet.</p>
              <p className="mt-2">
                Create the first content project once a brand profile exists.
              </p>
            </div>
          ) : null}

          <div className="mt-6 grid gap-4">
            {filteredProjects.map((project) => (
              <article
                key={project.id}
                className="rounded-2xl border border-white/8 bg-white/4 p-5"
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-3">
                      <h4 className="text-lg font-semibold text-white">{project.title}</h4>
                      <StatusBadge label={project.status.replaceAll("_", " ")} status={project.status} />
                    </div>
                    <p className="text-sm leading-6 text-slate-300">{project.objective}</p>
                    <div className="flex flex-wrap gap-2 text-xs text-slate-300">
                      <span className="rounded-full border border-white/10 px-3 py-1">
                        Platform: {project.target_platform}
                      </span>
                      <span className="rounded-full border border-white/10 px-3 py-1">
                        Brand: {brandProfileNameById.get(project.brand_profile_id) ?? "Unknown"}
                      </span>
                    </div>
                  </div>
                  <Link
                    className="rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-200 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
                    href={`/projects/${project.id}`}
                  >
                    Edit project
                  </Link>
                </div>

                {project.notes ? (
                  <p className="mt-4 rounded-2xl border border-white/8 bg-slate-950/40 px-4 py-3 text-sm text-slate-300">
                    {project.notes}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      </div>

      <div className="grid gap-6">
        <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-xl font-semibold text-white">Account analytics</h3>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Cross-project patterns from published posts, grouped by hook, duration, posting
                window, voice, and content type.
              </p>
            </div>
            <span className="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100">
              {accountAnalytics?.overview.published_posts ?? 0} posts
            </span>
          </div>

          {accountAnalytics && accountAnalytics.overview.published_posts > 0 ? (
            <div className="mt-5 grid gap-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <article className="rounded-2xl border border-white/8 bg-white/4 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Views</p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {formatNumber(accountAnalytics.overview.total_views)}
                  </p>
                </article>
                <article className="rounded-2xl border border-white/8 bg-white/4 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Engagement</p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {formatPercent(accountAnalytics.overview.average_engagement_rate)}
                  </p>
                </article>
                <article className="rounded-2xl border border-white/8 bg-white/4 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Avg view</p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {formatDuration(accountAnalytics.overview.average_view_duration)}
                  </p>
                </article>
              </div>

              {accountAnalytics.top_posts[0] ? (
                <Link
                  className="rounded-2xl border border-emerald-300/20 bg-emerald-400/10 p-4 transition hover:bg-emerald-400/20"
                  href={`/projects/${accountAnalytics.top_posts[0].project_id}`}
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-100">
                    Top post
                  </p>
                  <p className="mt-2 text-sm font-semibold text-white">
                    {accountAnalytics.top_posts[0].title}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-emerald-50/80">
                    {formatNumber(accountAnalytics.top_posts[0].views)} views /{" "}
                    {formatPercent(accountAnalytics.top_posts[0].engagement_rate)} engagement
                  </p>
                </Link>
              ) : null}

              {strongestSummary ? <SummaryCard item={strongestSummary} /> : null}

              <div className="grid gap-3">
                {accountAnalytics.recommendations.slice(0, 2).map((recommendation) => (
                  <Link
                    className="rounded-2xl border border-white/8 bg-slate-950/40 p-4 transition hover:border-cyan-300/30 hover:bg-cyan-400/10"
                    href={`/projects/${recommendation.project_id}`}
                    key={recommendation.insight_id}
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
                      {recommendation.insight_type.replaceAll("_", " ")}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-slate-100">
                      {recommendation.summary}
                    </p>
                  </Link>
                ))}
              </div>
            </div>
          ) : (
            <p className="mt-5 rounded-2xl border border-dashed border-white/10 bg-white/4 p-4 text-sm leading-6 text-slate-300">
              Publish a post and sync analytics to unlock account-level summaries.
            </p>
          )}
        </section>

        <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
          <h3 className="text-xl font-semibold text-white">Recent activity pulse</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            The newest project updates stay close to the inbox so blocked work is easy to spot.
          </p>
          <div className="mt-5 grid gap-3">
            {recentProjects.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-white/10 bg-white/4 p-4 text-sm text-slate-300">
                No project activity yet. Create a project to start the pulse.
              </p>
            ) : (
              recentProjects.map((project) => (
                <Link
                  className="rounded-2xl border border-white/8 bg-white/4 p-4 transition hover:border-cyan-300/30 hover:bg-cyan-400/10"
                  href={`/projects/${project.id}`}
                  key={`recent-${project.id}`}
                >
                  <p className="text-sm font-semibold text-white">{project.title}</p>
                  <p className="mt-2 text-xs uppercase tracking-[0.16em] text-slate-500">
                    {projectStatusLabels[project.status]} · Updated {formatDate(project.updated_at)}
                  </p>
                </Link>
              ))
            )}
          </div>
        </section>

        <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
          <h3 className="text-xl font-semibold text-white">Operations snapshot</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Jobs, approvals, and recent activity are pulled into the dashboard so recovery work
            does not hide on individual project pages.
          </p>
          <div className="mt-5 grid gap-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <article className="rounded-2xl border border-white/8 bg-white/4 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Approvals</p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  {initialApprovals.length}
                </p>
              </article>
              <article className="rounded-2xl border border-white/8 bg-white/4 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Active jobs</p>
                <p className="mt-2 text-2xl font-semibold text-white">{activeJobs.length}</p>
              </article>
              <article className="rounded-2xl border border-white/8 bg-white/4 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Failed jobs</p>
                <p className="mt-2 text-2xl font-semibold text-white">{failedJobs.length}</p>
              </article>
            </div>
            <Link
              className={`rounded-2xl border p-4 transition ${
                attentionItemCount > 0
                  ? "border-amber-300/30 bg-amber-400/10 hover:bg-amber-400/20"
                  : "border-emerald-300/20 bg-emerald-400/10 hover:bg-emerald-400/20"
              }`}
              href="/operations"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-semibold text-white">Operations recovery center</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    Failed jobs, manual-intervention jobs, stale running work, quarantined
                    downloads, and duplicate warnings now have one recovery view.
                  </p>
                </div>
                <span className="rounded-full border border-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100">
                  {attentionItemCount} attention item{attentionItemCount === 1 ? "" : "s"}
                </span>
              </div>
            </Link>
            {initialActivity.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-white/10 bg-white/4 p-4 text-sm text-slate-300">
                Recent approval, job, and project-event activity will appear here.
              </p>
            ) : (
              initialActivity.slice(0, 5).map((activity) => (
                <article
                  className="rounded-2xl border border-white/8 bg-slate-950/40 p-4"
                  key={`${activity.source_type}-${activity.source_id}-${activity.created_at}`}
                >
                  <p className="text-sm font-semibold text-white">{activity.title}</p>
                  {activity.description ? (
                    <p className="mt-2 text-sm leading-6 text-slate-300">
                      {activity.description}
                    </p>
                  ) : null}
                  <p className="mt-2 text-xs uppercase tracking-[0.16em] text-slate-500">
                    {activity.source_type.replaceAll("_", " ")} ·{" "}
                    {formatDate(activity.created_at)}
                  </p>
                </article>
              ))
            )}
          </div>
        </section>

        <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
          <h3 className="text-xl font-semibold text-white">Add brand profile</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Add the positioning and style rules that future ideas and scripts should follow.
          </p>
          <div className="mt-6">
            <BrandProfileForm
              key={brandProfiles.length}
              onSubmit={handleCreateBrandProfile}
              resetOnSuccess
              submitLabel="Create brand profile"
            />
          </div>
        </section>

        <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
          <h3 className="text-xl font-semibold text-white">Add project</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Attach the project to a brand profile so the workflow can inherit the right voice and
            objectives from the start.
          </p>
          <div className="mt-6">
            <ProjectForm
              key={brandProfiles.map((brandProfile) => brandProfile.id).join(":")}
              brandProfiles={brandProfiles}
              disabled={brandProfiles.length === 0}
              onSubmit={handleCreateProject}
              resetOnSuccess
              submitLabel="Create project"
            />
          </div>
        </section>
      </div>
    </section>
  );
}

function SummaryCard({ item }: { item: AccountAnalyticsSummaryItem }) {
  return (
    <Link
      className="rounded-2xl border border-cyan-300/20 bg-cyan-400/10 p-4 transition hover:bg-cyan-400/20"
      href={`/projects/${item.sample_project_id}`}
    >
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-100">
        Strongest pattern
      </p>
      <p className="mt-2 text-sm font-semibold text-white">{item.label}</p>
      <p className="mt-2 text-xs leading-5 text-cyan-50/80">
        {item.publish_count} post{item.publish_count === 1 ? "" : "s"} /{" "}
        {formatNumber(item.total_views)} views / {formatPercent(item.average_engagement_rate)}
      </p>
    </Link>
  );
}
