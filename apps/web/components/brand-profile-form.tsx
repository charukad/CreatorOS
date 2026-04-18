"use client";

import { startTransition, useState, type FormEvent } from "react";
import type { BrandProfile, BrandProfilePayload } from "../types/api";

type BrandProfileFormProps = {
  initialValue?: Partial<BrandProfile>;
  onSubmit: (payload: BrandProfilePayload) => Promise<void>;
  resetOnSuccess?: boolean;
  submitLabel: string;
};

function toJsonString(preferences: unknown): string {
  return JSON.stringify(preferences ?? {}, null, 2);
}

export function BrandProfileForm({
  initialValue,
  onSubmit,
  resetOnSuccess = false,
  submitLabel,
}: BrandProfileFormProps) {
  const [channelName, setChannelName] = useState(() => initialValue?.channel_name ?? "");
  const [niche, setNiche] = useState(() => initialValue?.niche ?? "");
  const [targetAudience, setTargetAudience] = useState(() => initialValue?.target_audience ?? "");
  const [tone, setTone] = useState(() => initialValue?.tone ?? "");
  const [hookStyle, setHookStyle] = useState(() => initialValue?.hook_style ?? "");
  const [ctaStyle, setCtaStyle] = useState(() => initialValue?.cta_style ?? "");
  const [visualStyle, setVisualStyle] = useState(() => initialValue?.visual_style ?? "");
  const [postingPreferences, setPostingPreferences] = useState(
    () => toJsonString(initialValue?.posting_preferences_json),
  );
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isPending, setIsPending] = useState(false);

  function resetForm() {
    setChannelName("");
    setNiche("");
    setTargetAudience("");
    setTone("");
    setHookStyle("");
    setCtaStyle("");
    setVisualStyle("");
    setPostingPreferences("{}");
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setStatusMessage(null);

    let postingPreferencesJson: Record<string, unknown>;
    try {
      postingPreferencesJson = JSON.parse(postingPreferences || "{}") as Record<string, unknown>;
    } catch {
      setError("Posting preferences must be valid JSON.");
      return;
    }

    const payload: BrandProfilePayload = {
      channel_name: channelName.trim(),
      niche: niche.trim(),
      target_audience: targetAudience.trim(),
      tone: tone.trim(),
      hook_style: hookStyle.trim(),
      cta_style: ctaStyle.trim(),
      visual_style: visualStyle.trim(),
      posting_preferences_json: postingPreferencesJson,
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
      <div className="grid gap-4 md:grid-cols-2">
        <label className="grid gap-2 text-sm text-slate-200">
          Channel name
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
            onChange={(event) => setChannelName(event.target.value)}
            required
            value={channelName}
          />
        </label>
        <label className="grid gap-2 text-sm text-slate-200">
          Niche
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
            onChange={(event) => setNiche(event.target.value)}
            required
            value={niche}
          />
        </label>
      </div>

      <label className="grid gap-2 text-sm text-slate-200">
        Target audience
        <textarea
          className="min-h-28 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
          onChange={(event) => setTargetAudience(event.target.value)}
          required
          value={targetAudience}
        />
      </label>

      <div className="grid gap-4 md:grid-cols-3">
        <label className="grid gap-2 text-sm text-slate-200">
          Tone
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
            onChange={(event) => setTone(event.target.value)}
            required
            value={tone}
          />
        </label>
        <label className="grid gap-2 text-sm text-slate-200">
          Hook style
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
            onChange={(event) => setHookStyle(event.target.value)}
            required
            value={hookStyle}
          />
        </label>
        <label className="grid gap-2 text-sm text-slate-200">
          CTA style
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
            onChange={(event) => setCtaStyle(event.target.value)}
            required
            value={ctaStyle}
          />
        </label>
      </div>

      <label className="grid gap-2 text-sm text-slate-200">
        Visual style
        <input
          className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40"
          onChange={(event) => setVisualStyle(event.target.value)}
          required
          value={visualStyle}
        />
      </label>

      <label className="grid gap-2 text-sm text-slate-200">
        Posting preferences JSON
        <textarea
          className="min-h-36 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 font-mono text-sm text-white outline-none transition focus:border-cyan-300/40"
          onChange={(event) => setPostingPreferences(event.target.value)}
          value={postingPreferences}
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
          Required fields feed the idea and script generation context.
        </p>
        <button
          className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-5 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-100 transition hover:border-cyan-200/50 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isPending}
          type="submit"
        >
          {isPending ? "Saving..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
