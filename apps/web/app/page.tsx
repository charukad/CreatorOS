import {
  buildProjectStoragePath,
  projectStatuses,
  projectStatusLabels,
  workflowMilestones,
} from "@creatoros/shared";
import { DashboardWorkspace } from "../components/dashboard-workspace";
import { StatusBadge } from "../components/status-badge";
import { listBrandProfiles, listProjects } from "../lib/api";
import { apiBaseUrl } from "../lib/env";
import type { BrandProfile, Project } from "../types/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let initialError: string | null = null;
  let brandProfiles: BrandProfile[] = [];
  let projects: Project[] = [];

  try {
    [brandProfiles, projects] = await Promise.all([listBrandProfiles(), listProjects()]);
  } catch (loadError) {
    initialError = loadError instanceof Error ? loadError.message : "Unable to load dashboard data.";
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-10 px-6 py-10">
      <section className="rounded-[2rem] border border-white/10 bg-white/5 p-8 shadow-2xl shadow-cyan-950/30 backdrop-blur">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-4">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-cyan-300">
              CreatorOS foundation
            </p>
            <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
              Build the content pipeline with approvals at every critical step.
            </h1>
            <p className="max-w-2xl text-base leading-7 text-slate-300 sm:text-lg">
              This starter dashboard anchors the workflow around project state, browser-based
              asset generation, human approvals, and traceable storage paths.
            </p>
          </div>
          <div className="rounded-2xl border border-cyan-400/20 bg-slate-950/50 p-5 text-sm text-slate-300">
            <p className="font-medium text-white">API endpoint</p>
            <p className="mt-2 break-all text-cyan-300">{apiBaseUrl}</p>
            <p className="mt-4 font-medium text-white">Example storage path</p>
            <p className="mt-2 break-all text-amber-300">
              {buildProjectStoragePath("project-123", "audio", "narration-v1.mp3")}
            </p>
          </div>
        </div>
      </section>

      <DashboardWorkspace
        initialBrandProfiles={brandProfiles}
        initialError={initialError}
        initialProjects={projects}
      />

      <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
          <h2 className="text-xl font-semibold text-white">Core milestones</h2>
          <div className="mt-5 grid gap-4">
            {workflowMilestones.map((milestone) => (
              <article
                key={milestone.id}
                className="rounded-2xl border border-white/8 bg-white/4 p-5"
              >
                <p className="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-200">
                  {milestone.title}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-300">{milestone.description}</p>
              </article>
            ))}
          </div>
        </div>

        <div className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
          <h2 className="text-xl font-semibold text-white">Project states</h2>
          <div className="mt-5 flex flex-wrap gap-3">
            {projectStatuses.map((status) => (
              <StatusBadge key={status} label={projectStatusLabels[status]} status={status} />
            ))}
          </div>
          <p className="mt-6 text-sm leading-6 text-slate-300">
            These states are shared workspace contracts and will be reused by the API, dashboard,
            jobs, and approval engine as the implementation grows.
          </p>
        </div>
      </section>
    </main>
  );
}
