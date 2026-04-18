"use client";

import {
  getAvailableProjectStatusTransitions,
  projectStatusDescriptions,
  projectStatusLabels,
} from "@creatoros/shared";
import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";
import { transitionProjectStatus } from "../lib/api";
import type { Project } from "../types/api";

type ProjectStatusActionsProps = {
  project: Project;
};

function buttonClassName(status: Project["status"]): string {
  switch (status) {
    case "idea_pending_approval":
    case "script_pending_approval":
    case "asset_generation":
    case "asset_pending_approval":
    case "rough_cut_ready":
    case "final_pending_approval":
      return "border-cyan-300/30 bg-cyan-400/10 text-cyan-100 hover:border-cyan-200/50 hover:bg-cyan-400/20";
    case "ready_to_publish":
    case "scheduled":
    case "published":
      return "border-amber-300/30 bg-amber-400/10 text-amber-100 hover:border-amber-200/50 hover:bg-amber-400/20";
    case "failed":
      return "border-rose-300/30 bg-rose-400/10 text-rose-100 hover:border-rose-200/50 hover:bg-rose-400/20";
    case "archived":
      return "border-slate-300/20 bg-slate-400/10 text-slate-100 hover:border-slate-200/40 hover:bg-slate-400/20";
    default:
      return "border-white/10 bg-white/5 text-slate-100 hover:border-cyan-300/40 hover:bg-cyan-400/10";
  }
}

export function ProjectStatusActions({ project }: ProjectStatusActionsProps) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pendingTarget, setPendingTarget] = useState<Project["status"] | null>(null);

  const availableTransitions = getAvailableProjectStatusTransitions(project.status);

  function handleTransition(targetStatus: Project["status"]) {
    setError(null);
    setPendingTarget(targetStatus);

    startTransition(() => {
      void transitionProjectStatus(project.id, { target_status: targetStatus })
        .then(() => {
          router.refresh();
        })
        .catch((transitionError) => {
          setError(
            transitionError instanceof Error
              ? transitionError.message
              : "Unable to update project status.",
          );
          setPendingTarget(null);
        });
    });
  }

  return (
    <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Workflow actions</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
            Move the project through the guarded workflow. Invalid jumps are blocked by the API and
            should stay blocked here too.
          </p>
        </div>
        <div className="rounded-2xl border border-white/8 bg-white/4 px-4 py-3 text-sm text-slate-300">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            Current stage
          </p>
          <p className="mt-2 font-medium text-white">{projectStatusLabels[project.status]}</p>
          <p className="mt-2 max-w-xs text-xs leading-5 text-slate-400">
            {projectStatusDescriptions[project.status]}
          </p>
        </div>
      </div>

      {availableTransitions.length === 0 ? (
        <p className="mt-6 rounded-2xl border border-white/8 bg-white/4 px-4 py-3 text-sm text-slate-300">
          This project has no further transitions from its current status.
        </p>
      ) : (
        <div className="mt-6 flex flex-wrap gap-3">
          {availableTransitions.map((status) => (
            <button
              key={status}
              className={`rounded-full border px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] transition disabled:cursor-not-allowed disabled:opacity-50 ${buttonClassName(status)}`}
              disabled={pendingTarget !== null}
              onClick={() => handleTransition(status)}
              type="button"
            >
              {pendingTarget === status ? "Updating..." : `Move to ${projectStatusLabels[status]}`}
            </button>
          ))}
        </div>
      )}

      <div className="mt-6 grid gap-3 md:grid-cols-2">
        {availableTransitions.map((status) => (
          <article
            key={`description-${status}`}
            className="rounded-2xl border border-white/8 bg-white/4 p-4"
          >
            <p className="text-sm font-semibold text-white">{projectStatusLabels[status]}</p>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              {projectStatusDescriptions[status]}
            </p>
          </article>
        ))}
      </div>

      {error ? (
        <p className="mt-6 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          {error}
        </p>
      ) : null}
    </section>
  );
}
