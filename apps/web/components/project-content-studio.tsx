"use client";

import {
  approvalDecisionLabels,
  approvalStageLabels,
  contentIdeaStatusLabels,
  scriptStatusLabels,
} from "@creatoros/shared";
import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";
import {
  approveIdea,
  approveScript,
  generateProjectIdeas,
  generateProjectScript,
  rejectIdea,
  rejectScript,
  updateScene,
} from "../lib/api";
import { SceneEditorCard } from "./scene-editor-card";
import type {
  ApprovalRecord,
  ContentIdea,
  Project,
  ProjectScript,
  SceneUpdatePayload,
  ScriptPromptPack,
} from "../types/api";

type ProjectContentStudioProps = {
  approvals: ApprovalRecord[];
  currentScript: ProjectScript | null;
  ideas: ContentIdea[];
  promptPack: ScriptPromptPack | null;
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

function decisionBadgeClassName(decision: ApprovalRecord["decision"]): string {
  return decision === "approved"
    ? "border-emerald-300/30 bg-emerald-400/10 text-emerald-100"
    : "border-rose-300/30 bg-rose-400/10 text-rose-100";
}

export function ProjectContentStudio({
  approvals,
  currentScript,
  ideas,
  promptPack,
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
  const canReviewScript =
    currentScript !== null &&
    project.status === "script_pending_approval" &&
    currentScript.status !== "superseded";
  const canEditScenes =
    currentScript !== null &&
    project.status === "script_pending_approval" &&
    (currentScript.status === "draft" || currentScript.status === "rejected");
  const canApproveCurrentScript =
    canReviewScript && currentScript !== null && currentScript.status !== "approved";
  const canRejectCurrentScript =
    canReviewScript && currentScript !== null && currentScript.status !== "rejected";

  function runAction(actionKey: string, callback: () => Promise<unknown>) {
    setError(null);
    setPendingAction(actionKey);

    startTransition(() => {
      void callback()
        .then(() => {
          router.refresh();
          setPendingAction(null);
        })
        .catch((actionError) => {
          setError(
            actionError instanceof Error ? actionError.message : "Workflow action failed.",
          );
          setPendingAction(null);
        });
    });
  }

  async function handleSceneSave(sceneId: string, payload: SceneUpdatePayload) {
    setError(null);
    setPendingAction(`scene-${sceneId}`);

    try {
      await updateScene(sceneId, payload);
      router.refresh();
      setPendingAction(null);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Unable to save scene.");
      setPendingAction(null);
      throw actionError;
    }
  }

  return (
    <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Idea and Script Studio</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
            This workflow now includes explicit approval decisions, so the project cannot slide
            into asset generation until the current script is intentionally approved.
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
                Ideas are stored and reviewable, so you can pick one angle deliberately instead of
                losing the earlier passes.
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
              {ideas.map((idea) => {
                const canReviewIdea =
                  project.status === "idea_pending_approval" && idea.status === "proposed";

                return (
                  <article
                    key={idea.id}
                    className={`rounded-2xl border p-5 ${ideaCardClassName(idea.status)}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                          Score {idea.score}
                        </p>
                        <h4 className="mt-2 text-lg font-semibold text-white">
                          {idea.suggested_title}
                        </h4>
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
                      {canReviewIdea ? (
                        <div className="flex flex-wrap gap-2">
                          <button
                            className="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-100 transition hover:border-emerald-200/50 hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={pendingAction !== null}
                            onClick={() =>
                              runAction(`approve-${idea.id}`, () => approveIdea(idea.id, {}))
                            }
                            type="button"
                          >
                            {pendingAction === `approve-${idea.id}` ? "Approving..." : "Approve"}
                          </button>
                          <button
                            className="rounded-full border border-rose-300/30 bg-rose-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-rose-100 transition hover:border-rose-200/50 hover:bg-rose-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={pendingAction !== null}
                            onClick={() =>
                              runAction(`reject-${idea.id}`, () => rejectIdea(idea.id, {}))
                            }
                            type="button"
                          >
                            {pendingAction === `reject-${idea.id}` ? "Rejecting..." : "Reject"}
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </article>
                );
              })}
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
          ) : (
            <div className="rounded-2xl border border-emerald-300/20 bg-emerald-400/10 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-100/70">
                Approved source idea
              </p>
              <h4 className="mt-2 text-lg font-semibold text-white">
                {approvedIdea.suggested_title}
              </h4>
              <p className="mt-3 text-sm leading-6 text-slate-100">{approvedIdea.hook}</p>
            </div>
          )}

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

                {currentScript.status === "approved" ? (
                  <div className="mt-5 rounded-2xl border border-emerald-300/20 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-100">
                    This script is approved and can move into asset generation when you are ready.
                  </div>
                ) : null}

                {currentScript.status === "rejected" ? (
                  <div className="mt-5 rounded-2xl border border-rose-300/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
                    This script is currently rejected. Regenerate it or revise the idea direction
                    before moving forward.
                  </div>
                ) : null}

                {canApproveCurrentScript || canRejectCurrentScript ? (
                  <div className="mt-5 flex flex-wrap gap-3">
                    {canApproveCurrentScript ? (
                      <button
                        className="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-100 transition hover:border-emerald-200/50 hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={pendingAction !== null}
                        onClick={() =>
                          runAction(`approve-script-${currentScript.id}`, () =>
                            approveScript(currentScript.id, {}),
                          )
                        }
                        type="button"
                      >
                        {pendingAction === `approve-script-${currentScript.id}`
                          ? "Approving..."
                          : "Approve script"}
                      </button>
                    ) : null}
                    {canRejectCurrentScript ? (
                      <button
                        className="rounded-full border border-rose-300/30 bg-rose-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-rose-100 transition hover:border-rose-200/50 hover:bg-rose-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={pendingAction !== null}
                        onClick={() =>
                          runAction(`reject-script-${currentScript.id}`, () =>
                            rejectScript(currentScript.id, {}),
                          )
                        }
                        type="button"
                      >
                        {pendingAction === `reject-script-${currentScript.id}`
                          ? "Rejecting..."
                          : "Reject script"}
                      </button>
                    ) : null}
                  </div>
                ) : null}

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
                      <p className="mt-3 text-sm leading-6 text-slate-100">
                        {currentScript.caption}
                      </p>
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
                      Edit scene wording and prompts before you lock the script in. Once the script
                      is approved, these edits are intentionally blocked.
                    </p>
                  </div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Updated {formatTimestamp(currentScript.updated_at)}
                  </p>
                </div>

                {!canEditScenes ? (
                  <div className="mt-5 rounded-2xl border border-white/8 bg-white/4 px-4 py-3 text-sm text-slate-300">
                    Scene editing is only available while the current script is in draft or rejected
                    state during script approval.
                  </div>
                ) : null}

                <div className="mt-5 grid gap-4">
                  {currentScript.scenes.map((scene) => (
                    <SceneEditorCard
                      canEdit={canEditScenes}
                      isSaving={pendingAction === `scene-${scene.id}`}
                      key={`${scene.id}-${scene.updated_at}`}
                      onSave={(payload) => handleSceneSave(scene.id, payload)}
                      scene={scene}
                    />
                  ))}
                </div>
              </article>

              {promptPack ? (
                <article className="rounded-2xl border border-white/8 bg-white/4 p-5">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <h4 className="text-lg font-semibold text-white">Prompt pack preview</h4>
                      <p className="mt-2 text-sm leading-6 text-slate-300">
                        This is the downstream-ready handoff for narration and visual workers. It
                        updates from the saved scene data.
                      </p>
                    </div>
                    <div className="rounded-2xl border border-cyan-300/20 bg-cyan-400/10 px-4 py-3 text-sm text-cyan-50">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200/80">
                        Source
                      </p>
                      <p className="mt-2 font-medium">{promptPack.channel_name}</p>
                      <p className="mt-1 text-xs text-cyan-100/80">
                        {promptPack.target_platform.replaceAll("_", " ")}
                      </p>
                    </div>
                  </div>

                  <div className="mt-5 grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
                    <div className="rounded-2xl border border-white/8 bg-slate-950/40 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                        Top-level metadata
                      </p>
                      <div className="mt-3 grid gap-3 text-sm text-slate-100">
                        <p>Idea: {promptPack.source_idea_title}</p>
                        <p>Objective: {promptPack.objective}</p>
                        <p>Caption: {promptPack.caption}</p>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {promptPack.hashtags.map((hashtag) => (
                          <span
                            className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-100"
                            key={hashtag}
                          >
                            {hashtag}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-2xl border border-white/8 bg-slate-950/40 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                        Title options
                      </p>
                      <div className="mt-3 grid gap-2 text-sm text-slate-100">
                        {promptPack.title_options.map((title) => (
                          <p key={title}>{title}</p>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="mt-5 grid gap-4">
                    {promptPack.scenes.map((scenePack) => (
                      <article
                        className="rounded-2xl border border-white/8 bg-slate-950/40 p-4"
                        key={scenePack.scene_id}
                      >
                        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
                              Scene {scenePack.scene_order}
                            </p>
                            <h5 className="mt-2 text-lg font-semibold text-white">
                              {scenePack.title}
                            </h5>
                          </div>
                          <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-100">
                            {scenePack.estimated_duration_seconds}s
                          </span>
                        </div>

                        <div className="mt-4 grid gap-4 lg:grid-cols-2">
                          <div className="space-y-4">
                            <div>
                              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                                Narration input
                              </p>
                              <p className="mt-2 text-sm leading-6 text-slate-100">
                                {scenePack.narration_input}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                                Narration direction
                              </p>
                              <p className="mt-2 text-sm leading-6 text-slate-100">
                                {scenePack.narration_direction}
                              </p>
                            </div>
                          </div>

                          <div className="space-y-4">
                            <div>
                              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                                Image generation prompt
                              </p>
                              <p className="mt-2 text-sm leading-6 text-slate-100">
                                {scenePack.image_generation_prompt}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                                Video generation prompt
                              </p>
                              <p className="mt-2 text-sm leading-6 text-slate-100">
                                {scenePack.video_generation_prompt}
                              </p>
                            </div>
                          </div>
                        </div>

                        {scenePack.notes ? (
                          <p className="mt-4 rounded-2xl border border-white/10 bg-white/4 px-4 py-3 text-sm text-slate-300">
                            {scenePack.notes}
                          </p>
                        ) : null}
                      </article>
                    ))}
                  </div>
                </article>
              ) : null}
            </div>
          ) : null}
        </section>

        <section className="grid gap-5">
          <div>
            <h3 className="text-lg font-semibold text-white">Approval history</h3>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Every explicit decision is saved here so the workflow stays traceable.
            </p>
          </div>

          {approvals.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/10 bg-white/4 p-5 text-sm text-slate-300">
              <p className="font-semibold text-white">No approvals recorded yet.</p>
              <p className="mt-2">
                Approve or reject an idea or script and the decision history will appear here.
              </p>
            </div>
          ) : (
            <div className="grid gap-4">
              {approvals.map((approval) => (
                <article
                  key={approval.id}
                  className="rounded-2xl border border-white/8 bg-white/4 p-4"
                >
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex flex-wrap gap-2">
                        <span
                          className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${decisionBadgeClassName(approval.decision)}`}
                        >
                          {approvalDecisionLabels[approval.decision]}
                        </span>
                        <span className="rounded-full border border-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100">
                          {approvalStageLabels[approval.stage]}
                        </span>
                      </div>
                      <p className="mt-3 text-sm text-slate-200">
                        {approval.target_type === "content_idea"
                          ? "Content idea review"
                          : "Script review"}
                      </p>
                    </div>
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                      {formatTimestamp(approval.created_at)}
                    </p>
                  </div>

                  {approval.feedback_notes ? (
                    <p className="mt-4 rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-slate-300">
                      {approval.feedback_notes}
                    </p>
                  ) : (
                    <p className="mt-4 text-sm text-slate-400">No feedback notes recorded.</p>
                  )}
                </article>
              ))}
            </div>
          )}
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
