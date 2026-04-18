"use client";

import { useState } from "react";
import type { SceneUpdatePayload, ScriptScene } from "../types/api";

type SceneEditorCardProps = {
  canEdit: boolean;
  isSaving: boolean;
  onSave: (payload: SceneUpdatePayload) => Promise<void>;
  scene: ScriptScene;
};

type SceneDraft = {
  title: string;
  narration_text: string;
  overlay_text: string;
  image_prompt: string;
  video_prompt: string;
  estimated_duration_seconds: number;
  notes: string;
};

function buildSceneDraft(scene: ScriptScene): SceneDraft {
  return {
    title: scene.title,
    narration_text: scene.narration_text,
    overlay_text: scene.overlay_text,
    image_prompt: scene.image_prompt,
    video_prompt: scene.video_prompt,
    estimated_duration_seconds: scene.estimated_duration_seconds,
    notes: scene.notes ?? "",
  };
}

export function SceneEditorCard({
  canEdit,
  isSaving,
  onSave,
  scene,
}: SceneEditorCardProps) {
  const [draft, setDraft] = useState<SceneDraft>(() => buildSceneDraft(scene));
  const [isEditing, setIsEditing] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSave({
      title: draft.title,
      narration_text: draft.narration_text,
      overlay_text: draft.overlay_text,
      image_prompt: draft.image_prompt,
      video_prompt: draft.video_prompt,
      estimated_duration_seconds: Number(draft.estimated_duration_seconds),
      notes: draft.notes.trim() ? draft.notes : null,
    });
    setIsEditing(false);
  }

  return (
    <article className="rounded-2xl border border-white/8 bg-slate-950/40 p-4">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
            Scene {scene.scene_order}
          </p>
          <h5 className="mt-2 text-lg font-semibold text-white">{scene.title}</h5>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-100">
            {scene.estimated_duration_seconds}s
          </span>
          {canEdit ? (
            <button
              className="rounded-full border border-white/10 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
              onClick={() => setIsEditing((value) => !value)}
              type="button"
            >
              {isEditing ? "Close editor" : "Edit scene"}
            </button>
          ) : null}
        </div>
      </div>

      {isEditing ? (
        <form className="mt-5 grid gap-4" onSubmit={handleSubmit}>
          <label className="grid gap-2 text-sm text-slate-200">
            Title
            <input
              className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
              onChange={(event) => setDraft((value) => ({ ...value, title: event.target.value }))}
              required
              value={draft.title}
            />
          </label>

          <div className="grid gap-4 lg:grid-cols-2">
            <label className="grid gap-2 text-sm text-slate-200">
              Narration
              <textarea
                className="min-h-28 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
                onChange={(event) =>
                  setDraft((value) => ({ ...value, narration_text: event.target.value }))
                }
                required
                value={draft.narration_text}
              />
            </label>

            <label className="grid gap-2 text-sm text-slate-200">
              Overlay text
              <textarea
                className="min-h-28 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
                onChange={(event) =>
                  setDraft((value) => ({ ...value, overlay_text: event.target.value }))
                }
                required
                value={draft.overlay_text}
              />
            </label>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <label className="grid gap-2 text-sm text-slate-200">
              Image prompt
              <textarea
                className="min-h-32 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
                onChange={(event) =>
                  setDraft((value) => ({ ...value, image_prompt: event.target.value }))
                }
                required
                value={draft.image_prompt}
              />
            </label>

            <label className="grid gap-2 text-sm text-slate-200">
              Video prompt
              <textarea
                className="min-h-32 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
                onChange={(event) =>
                  setDraft((value) => ({ ...value, video_prompt: event.target.value }))
                }
                required
                value={draft.video_prompt}
              />
            </label>
          </div>

          <div className="grid gap-4 lg:grid-cols-[0.35fr_1fr]">
            <label className="grid gap-2 text-sm text-slate-200">
              Duration (seconds)
              <input
                className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
                min={1}
                onChange={(event) =>
                  setDraft((value) => ({
                    ...value,
                    estimated_duration_seconds: Number(event.target.value),
                  }))
                }
                required
                type="number"
                value={draft.estimated_duration_seconds}
              />
            </label>

            <label className="grid gap-2 text-sm text-slate-200">
              Notes
              <textarea
                className="min-h-24 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
                onChange={(event) => setDraft((value) => ({ ...value, notes: event.target.value }))}
                value={draft.notes}
              />
            </label>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100 transition hover:border-cyan-200/50 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={isSaving}
              type="submit"
            >
              {isSaving ? "Saving..." : "Save scene"}
            </button>
            <button
              className="rounded-full border border-white/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-200 transition hover:border-white/20 hover:bg-white/5"
              disabled={isSaving}
              onClick={() => {
                setDraft(buildSceneDraft(scene));
                setIsEditing(false);
              }}
              type="button"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Narration
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-100">{scene.narration_text}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Overlay
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-100">{scene.overlay_text}</p>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Image prompt
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-100">{scene.image_prompt}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Video prompt
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-100">{scene.video_prompt}</p>
              </div>
            </div>
          </div>

          {scene.notes ? (
            <p className="mt-4 rounded-2xl border border-white/10 bg-white/4 px-4 py-3 text-sm text-slate-300">
              {scene.notes}
            </p>
          ) : null}
        </>
      )}
    </article>
  );
}
