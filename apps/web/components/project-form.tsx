"use client";

import { startTransition, useState, type FormEvent } from "react";
import type { BrandProfile, Project, ProjectPayload } from "../types/api";

type ProjectFormProps = {
  brandProfiles: BrandProfile[];
  disabled?: boolean;
  initialValue?: Partial<Project>;
  onSubmit: (payload: ProjectPayload) => Promise<void>;
  resetOnSuccess?: boolean;
  submitLabel: string;
};

export function ProjectForm({
  brandProfiles,
  disabled = false,
  initialValue,
  onSubmit,
  resetOnSuccess = false,
  submitLabel,
}: ProjectFormProps) {
  const [brandProfileId, setBrandProfileId] = useState(
    () => initialValue?.brand_profile_id ?? brandProfiles[0]?.id ?? "",
  );
  const [title, setTitle] = useState(() => initialValue?.title ?? "");
  const [targetPlatform, setTargetPlatform] = useState(() => initialValue?.target_platform ?? "");
  const [objective, setObjective] = useState(() => initialValue?.objective ?? "");
  const [notes, setNotes] = useState(() => initialValue?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isPending, setIsPending] = useState(false);

  function resetForm() {
    setBrandProfileId(brandProfiles[0]?.id ?? "");
    setTitle("");
    setTargetPlatform("");
    setObjective("");
    setNotes("");
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setStatusMessage(null);

    if (!brandProfileId) {
      setError("Create a brand profile before creating projects.");
      return;
    }

    const payload: ProjectPayload = {
      brand_profile_id: brandProfileId,
      title: title.trim(),
      target_platform: targetPlatform.trim(),
      objective: objective.trim(),
      notes: notes.trim() || null,
    };

    setIsPending(true);
    startTransition(() => {
      void onSubmit(payload)
        .then(() => {
          setStatusMessage("Saved.");
          if (resetOnSuccess) {
            resetForm();
          }
        })
        .catch((submitError) => {
          setError(submitError instanceof Error ? submitError.message : "Unable to save.");
        })
        .finally(() => {
          setIsPending(false);
        });
    });
  }

  return (
    <form className="grid gap-4" onSubmit={handleSubmit}>
      <label className="grid gap-2 text-sm text-slate-200">
        Brand profile
        <select
          className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={disabled || brandProfiles.length === 0}
          onChange={(event) => setBrandProfileId(event.target.value)}
          required
          value={brandProfileId}
        >
          {brandProfiles.length === 0 ? <option value="">Create a brand profile first</option> : null}
          {brandProfiles.map((brandProfile) => (
            <option key={brandProfile.id} value={brandProfile.id}>
              {brandProfile.channel_name}
            </option>
          ))}
        </select>
      </label>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="grid gap-2 text-sm text-slate-200">
          Project title
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
            disabled={disabled}
            onChange={(event) => setTitle(event.target.value)}
            required
            value={title}
          />
        </label>
        <label className="grid gap-2 text-sm text-slate-200">
          Target platform
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
            disabled={disabled}
            onChange={(event) => setTargetPlatform(event.target.value)}
            placeholder="youtube_shorts"
            required
            value={targetPlatform}
          />
        </label>
      </div>

      <label className="grid gap-2 text-sm text-slate-200">
        Objective
        <textarea
          className="min-h-28 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
          disabled={disabled}
          onChange={(event) => setObjective(event.target.value)}
          required
          value={objective}
        />
      </label>

      <label className="grid gap-2 text-sm text-slate-200">
        Notes
        <textarea
          className="min-h-28 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
          disabled={disabled}
          onChange={(event) => setNotes(event.target.value)}
          value={notes}
        />
      </label>

      {error ? (
        <p className="rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          {error}
        </p>
      ) : null}

      {statusMessage ? (
        <p className="rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
          {statusMessage}
        </p>
      ) : null}

      <div className="flex items-center justify-between gap-4">
        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
          Projects start in draft so the next workflow stages can gate approvals properly.
        </p>
        <button
          className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-5 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-100 transition hover:border-cyan-200/50 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={disabled || isPending}
          type="submit"
        >
          {isPending ? "Saving..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
