"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ProjectForm } from "./project-form";
import { ProjectStatusActions } from "./project-status-actions";
import { StatusBadge } from "./status-badge";
import { updateProject } from "../lib/api";
import type { BrandProfile, Project, ProjectPayload } from "../types/api";

type ProjectDetailProps = {
  brandProfiles: BrandProfile[];
  error: string | null;
  project: Project | null;
};

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

export function ProjectDetail({ brandProfiles, error, project }: ProjectDetailProps) {
  const router = useRouter();

  async function handleSubmit(payload: ProjectPayload) {
    if (!project) {
      throw new Error("Project data is unavailable.");
    }

    await updateProject(project.id, payload);
    router.refresh();
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-8 px-6 py-10">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">
            Project
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-white">Edit project foundation</h1>
        </div>
        <Link
          href="/"
          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
        >
          Back to dashboard
        </Link>
      </div>

      {error || !project ? (
        <section className="rounded-[1.5rem] border border-rose-400/30 bg-rose-500/10 p-5 text-sm text-rose-100">
          <p className="font-semibold">Could not load this project.</p>
          <p className="mt-2">{error ?? "The requested project could not be found."}</p>
          <button
            className="mt-4 rounded-full border border-rose-300/30 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-rose-50 transition hover:bg-rose-400/10"
            onClick={() => router.refresh()}
            type="button"
          >
            Retry
          </button>
        </section>
      ) : null}

      {project ? (
        <>
          <section className="grid gap-4 rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6 md:grid-cols-4">
            <div className="rounded-2xl border border-white/8 bg-white/4 p-4 md:col-span-2">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                Title
              </p>
              <p className="mt-3 text-lg font-medium text-white">{project.title}</p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                Status
              </p>
              <div className="mt-3">
                <StatusBadge label={project.status.replaceAll("_", " ")} status={project.status} />
              </div>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                Last saved
              </p>
              <p className="mt-3 text-sm text-slate-200">{formatTimestamp(project.updated_at)}</p>
            </div>
          </section>

          <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
            <h2 className="text-xl font-semibold text-white">Project settings</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              Keep the brand profile, target platform, and content objective aligned before the
              project moves into idea and script generation.
            </p>
            <div className="mt-6">
              <ProjectForm
                key={`${project.id}-${project.updated_at}`}
                brandProfiles={brandProfiles}
                initialValue={project}
                onSubmit={handleSubmit}
                submitLabel="Save project"
              />
            </div>
          </section>

          <ProjectStatusActions project={project} />
        </>
      ) : null}
    </main>
  );
}
