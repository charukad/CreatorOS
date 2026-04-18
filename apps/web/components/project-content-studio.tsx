"use client";

import { contentIdeaStatusLabels, scriptStatusLabels } from "@creatoros/shared";
import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";
import { approveIdea, generateProjectIdeas, generateProjectScript } from "../lib/api";
import type { ContentIdea, Project, ProjectScript } from "../types/api";

type ProjectContentStudioProps = {
  currentScript: ProjectScript | null;
  ideas: ContentIdea[];
  project: Project;
};

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

function ideaCardClassName(status: ContentIdea["status"]): string {
  switch (status) {
    case "approved":
      return "border-emerald-300/30 bg-emerald-400/10";
    case "rejected":
      return "border-rose-300/20 bg-rose-500/5";
    default:
      return "border-white/8 bg-white/4";
  }
}

export function ProjectContentStudio({
  currentScript,
  ideas,
  project,
}: ProjectContentStudioProps) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const approvedIdea = ideas.find((idea) => idea.status === "approved") ?? null;
  const canGenerateIdeas =
    project.status === "draft" || project.status === "idea_pending_approval";
  const canGenerateScript =
    approvedIdea !== null &&
    (project.status === "idea_pending_approval" || project.status === "script_pending_approval");

  function runAction(actionKey: string, callback: () => Promise<unknown>) {
    setError(null);
    setPendingAction(actionKey);

    startTransition(() => {
      void callback()
        .then(() => {
          router.refresh();
        })
        .catch((actionError) => {
          setError(
            actionError instanceof Error ? actionError.message : "Workflow action failed.",
          );
          setPendingAction(null);
        });
    });
  }

  return (
    <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Idea and Script Studio</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
            This is the first real vertical workflow in CreatorOS: generate ideas from the brand
            and project context, approve one, then turn it into a stored script draft with scene
            prompts.
          </p>
        </div>
        <div className="rounded-2xl border border-cyan-300/20 bg-cyan-400/10 px-4 py-3 text-sm text-cyan-50">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200/80">
            Current output
          </p>
          <p className="mt-2 font-medium">
            {currentScript
              ? `Script v${currentScript.version_number}`
              : approvedIdea
                ? "Approved idea selected"
                : "No content draft yet"}
          </p>
        </div>
      </div>

      <div className="mt-8 grid gap-8">
        <section className="grid gap-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">1. Generate and review ideas</h3>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Each idea is saved so we can keep experimenting without losing the earlier passes.
              </p>
            </div>
            <button
              className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100 transition hover:border-cyan-200/50 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!canGenerateIdeas || pendingAction !== null}
              onClick={() => runAction("generate-ideas", () => generateProjectIdeas(project.id))}
              type="button"
            >
              {pendingAction === "generate-ideas"
                ? "Generating..."
                : ideas.length === 0
                  ? "Generate ideas"
                  : "Regenerate ideas"}
            </button>
          </div>

          {ideas.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/10 bg-white/4 p-5 text-sm text-slate-300">
              <p className="font-semibold text-white">No saved ideas yet.</p>
              <p className="mt-2">
                Generate the first batch to turn this project into something you can actually
                evaluate and refine.
              </p>
            </div>
          ) : (
            <div className="grid gap-4 xl:grid-cols-3">
              {ideas.map((idea) => (
                <article
                  key={idea.id}
                  className={`rounded-2xl border p-5 ${ideaCardClassName(idea.status)}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                        Score {idea.score}
                      </p>
                      <h4 className="mt-2 text-lg font-semibold text-white">{idea.suggested_title}</h4>
                    </div>
                    <span className="rounded-full border border-white/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-100">
                      {contentIdeaStatusLabels[idea.status]}
                    </span>
                  </div>
                  <p className="mt-4 text-sm font-medium text-cyan-100">{idea.hook}</p>
                  <p className="mt-4 text-sm leading-6 text-slate-200">{idea.angle}</p>
                  <p className="mt-4 text-sm leading-6 text-slate-300">{idea.rationale}</p>

                  {idea.feedback_notes ? (
                    <p className="mt-4 rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-slate-300">
                      {idea.feedback_notes}
                    </p>
                  ) : null}

                  <div className="mt-5 flex items-center justify-between gap-3">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                      Saved {formatTimestamp(idea.updated_at)}
                    </p>
                    {idea.status !== "approved" ? (
                      <button
                        className="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-100 transition hover:border-emerald-200/50 hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={pendingAction !== null || project.status !== "idea_pending_approval"}
                        onClick={() =>
                          runAction(`approve-${idea.id}`, () => approveIdea(idea.id, {}))
                        }
                        type="button"
                      >
                        {pendingAction === `approve-${idea.id}` ? "Approving..." : "Approve idea"}
                      </button>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="grid gap-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">2. Generate a script and scene plan</h3>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Once one idea is approved, CreatorOS turns it into a reusable short-form script
                with prompts for later narration and visual generation steps.
              </p>
            </div>
            <button
              className="rounded-full border border-amber-300/30 bg-amber-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-amber-100 transition hover:border-amber-200/50 hover:bg-amber-400/20 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!canGenerateScript || pendingAction !== null}
              onClick={() => runAction("generate-script", () => generateProjectScript(project.id))}
              type="button"
            >
              {pendingAction === "generate-script"
                ? "Generating..."
                : currentScript
                  ? "Regenerate script"
                  : "Generate script"}
            </button>
          </div>

          {!approvedIdea ? (
            <div className="rounded-2xl border border-dashed border-white/10 bg-white/4 p-5 text-sm text-slate-300">
              <p className="font-semibold text-white">Approve one idea to unlock script generation.</p>
              <p className="mt-2">
                The approved idea becomes the source for the saved script draft and scene prompts.
              </p>
            </div>
          ) : null}

          {approvedIdea ? (
            <div className="rounded-2xl border border-emerald-300/20 bg-emerald-400/10 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-100/70">
                Approved source idea
              </p>
              <h4 className="mt-2 text-lg font-semibold text-white">{approvedIdea.suggested_title}</h4>
              <p className="mt-3 text-sm leading-6 text-slate-100">{approvedIdea.hook}</p>
            </div>
          ) : null}

          {currentScript ? (
            <div className="grid gap-5">
              <article className="rounded-2xl border border-white/8 bg-white/4 p-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                      Script version
                    </p>
                    <h4 className="mt-2 text-2xl font-semibold text-white">
                      v{currentScript.version_number}
                    </h4>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <span className="rounded-full border border-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100">
                      {scriptStatusLabels[currentScript.status]}
                    </span>
                    <span className="rounded-full border border-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100">
                      {currentScript.estimated_duration_seconds}s
                    </span>
                  </div>
                </div>

                <div className="mt-6 grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
                  <div className="grid gap-4">
                    <div className="rounded-2xl border border-white/8 bg-slate-950/40 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                        Hook
                      </p>
                      <p className="mt-3 text-sm leading-6 text-slate-100">{currentScript.hook}</p>
                    </div>
                    <div className="rounded-2xl border border-white/8 bg-slate-950/40 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                        Body
                      </p>
                      <p className="mt-3 text-sm leading-6 text-slate-100">{currentScript.body}</p>
                    </div>
                    <div className="rounded-2xl border border-white/8 bg-slate-950/40 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                        CTA
                      </p>
                      <p className="mt-3 text-sm leading-6 text-slate-100">{currentScript.cta}</p>
                    </div>
                  </div>

                  <div className="grid gap-4">
                    <div className="rounded-2xl border border-white/8 bg-slate-950/40 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                        Title options
                      </p>
                      <div className="mt-3 grid gap-2 text-sm text-slate-100">
                        {currentScript.title_options.map((title) => (
                          <p key={title}>{title}</p>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-white/8 bg-slate-950/40 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                        Caption
                      </p>
                      <p className="mt-3 text-sm leading-6 text-slate-100">{currentScript.caption}</p>
                    </div>
                    <div className="rounded-2xl border border-white/8 bg-slate-950/40 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                        Hashtags
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {currentScript.hashtags.map((hashtag) => (
                          <span
                            key={hashtag}
                            className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-100"
                          >
                            {hashtag}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </article>

              <article className="rounded-2xl border border-white/8 bg-white/4 p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h4 className="text-lg font-semibold text-white">Scene plan</h4>
                    <p className="mt-2 text-sm leading-6 text-slate-300">
                      These prompts are ready to feed the later narration and visual-generation
                      stages.
                    </p>
                  </div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Updated {formatTimestamp(currentScript.updated_at)}
                  </p>
                </div>

                <div className="mt-5 grid gap-4">
                  {currentScript.scenes.map((scene) => (
                    <article
                      key={scene.id}
                      className="rounded-2xl border border-white/8 bg-slate-950/40 p-4"
                    >
                      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
                            Scene {scene.scene_order}
                          </p>
                          <h5 className="mt-2 text-lg font-semibold text-white">{scene.title}</h5>
                        </div>
                        <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-100">
                          {scene.estimated_duration_seconds}s
                        </span>
                      </div>

                      <div className="mt-4 grid gap-4 lg:grid-cols-2">
                        <div className="space-y-4">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                              Narration
                            </p>
                            <p className="mt-2 text-sm leading-6 text-slate-100">
                              {scene.narration_text}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                              Overlay
                            </p>
                            <p className="mt-2 text-sm leading-6 text-slate-100">
                              {scene.overlay_text}
                            </p>
                          </div>
                        </div>

                        <div className="space-y-4">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                              Image prompt
                            </p>
                            <p className="mt-2 text-sm leading-6 text-slate-100">
                              {scene.image_prompt}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                              Video prompt
                            </p>
                            <p className="mt-2 text-sm leading-6 text-slate-100">
                              {scene.video_prompt}
                            </p>
                          </div>
                        </div>
                      </div>

                      {scene.notes ? (
                        <p className="mt-4 rounded-2xl border border-white/10 bg-white/4 px-4 py-3 text-sm text-slate-300">
                          {scene.notes}
                        </p>
                      ) : null}
                    </article>
                  ))}
                </div>
              </article>
            </div>
          ) : null}
        </section>
      </div>

      {error ? (
        <p className="mt-6 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          {error}
        </p>
      ) : null}
    </section>
  );
}
