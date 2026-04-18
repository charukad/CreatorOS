"use client";

import type { ProjectStatus } from "@creatoros/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useDeferredValue, useState } from "react";
import { BrandProfileForm } from "./brand-profile-form";
import { ProjectForm } from "./project-form";
import { StatusBadge } from "./status-badge";
import { createBrandProfile, createProject } from "../lib/api";
import type { BrandProfile, BrandProfilePayload, Project, ProjectPayload } from "../types/api";

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString();
}

function getStatusCount(projects: Project[], status: ProjectStatus): number {
  return projects.filter((project) => project.status === status).length;
}

type DashboardWorkspaceProps = {
  initialBrandProfiles: BrandProfile[];
  initialError: string | null;
  initialProjects: Project[];
};

export function DashboardWorkspace({
  initialBrandProfiles,
  initialError,
  initialProjects,
}: DashboardWorkspaceProps) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search.trim().toLowerCase());
  const brandProfiles = initialBrandProfiles;
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
                Ready to publish
              </p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {getStatusCount(projects, "ready_to_publish")}
              </p>
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
