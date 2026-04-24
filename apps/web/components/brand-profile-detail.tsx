"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { BrandProfileForm } from "./brand-profile-form";
import { useToast } from "./toast-provider";
import { updateBrandProfile } from "../lib/api";
import type {
  BrandProfile,
  BrandProfilePayload,
  BrandProfileReadiness,
  BrandPromptContext,
} from "../types/api";

type BrandProfileDetailProps = {
  brandProfile: BrandProfile | null;
  error: string | null;
  promptContext: BrandPromptContext | null;
  readiness: BrandProfileReadiness | null;
};

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

export function BrandProfileDetail({
  brandProfile,
  error,
  promptContext,
  readiness,
}: BrandProfileDetailProps) {
  const router = useRouter();
  const { pushToast } = useToast();

  async function handleSubmit(payload: BrandProfilePayload) {
    if (!brandProfile) {
      throw new Error("Brand profile data is unavailable.");
    }

    await updateBrandProfile(brandProfile.id, payload);
    pushToast({
      title: "Brand profile saved",
      description: "Creator positioning updates will flow into future idea and script generation.",
      tone: "success",
    });
    router.refresh();
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-8 px-6 py-10">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">
            Brand profile
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-white">Edit creator positioning</h1>
        </div>
        <Link
          href="/"
          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
        >
          Back to dashboard
        </Link>
      </div>

      {error || !brandProfile ? (
        <section className="rounded-[1.5rem] border border-rose-400/30 bg-rose-500/10 p-5 text-sm text-rose-100">
          <p className="font-semibold">Could not load this brand profile.</p>
          <p className="mt-2">{error ?? "The requested brand profile could not be found."}</p>
          <button
            className="mt-4 rounded-full border border-rose-300/30 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-rose-50 transition hover:bg-rose-400/10"
            onClick={() => router.refresh()}
            type="button"
          >
            Retry
          </button>
        </section>
      ) : null}

      {brandProfile ? (
        <>
          <section className="grid gap-4 rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6 md:grid-cols-3">
            <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                Channel
              </p>
              <p className="mt-3 text-lg font-medium text-white">{brandProfile.channel_name}</p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                Created
              </p>
              <p className="mt-3 text-sm text-slate-200">{formatTimestamp(brandProfile.created_at)}</p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                Last saved
              </p>
              <p className="mt-3 text-sm text-slate-200">{formatTimestamp(brandProfile.updated_at)}</p>
            </div>
          </section>

          {readiness ? (
            <section
              className={`rounded-[1.75rem] border p-6 ${
                readiness.is_ready
                  ? "border-emerald-300/20 bg-emerald-400/10"
                  : "border-amber-300/20 bg-amber-400/10"
              }`}
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-white">Onboarding readiness</h2>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-200">
                    CreatorOS checks the profile before using it as generation context, so weak or
                    missing setup does not quietly reduce output quality.
                  </p>
                </div>
                <span className="rounded-full border border-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100">
                  {readiness.is_ready ? "Ready" : "Needs refinement"}
                </span>
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-3">
                <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                    Missing fields
                  </p>
                  <p className="mt-3 text-2xl font-semibold text-white">
                    {readiness.missing_fields.length}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                    Warnings
                  </p>
                  <p className="mt-3 text-2xl font-semibold text-white">
                    {readiness.warnings.length}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                    Next steps
                  </p>
                  <p className="mt-3 text-2xl font-semibold text-white">
                    {readiness.recommended_next_steps.length}
                  </p>
                </div>
              </div>

              {readiness.warnings.length > 0 || readiness.recommended_next_steps.length > 0 ? (
                <div className="mt-5 grid gap-4 lg:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                    <p className="text-sm font-semibold text-white">Warnings</p>
                    <div className="mt-3 grid gap-2 text-sm leading-6 text-slate-200">
                      {readiness.warnings.length === 0 ? (
                        <p>No warnings.</p>
                      ) : (
                        readiness.warnings.map((warning) => <p key={warning}>{warning}</p>)
                      )}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                    <p className="text-sm font-semibold text-white">Recommended next steps</p>
                    <div className="mt-3 grid gap-2 text-sm leading-6 text-slate-200">
                      {readiness.recommended_next_steps.map((step) => (
                        <p key={step}>{step}</p>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
            </section>
          ) : null}

          {promptContext ? (
            <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
              <h2 className="text-xl font-semibold text-white">AI prompt context</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                This is the structured context CreatorOS can hand to idea, script, narration, and
                visual generation without reinterpreting brand rules every time.
              </p>
              <div className="mt-5 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
                <pre className="max-h-[420px] overflow-auto rounded-2xl border border-white/8 bg-slate-950/60 p-4 text-sm leading-6 text-slate-200">
                  {promptContext.context_markdown}
                </pre>
                <pre className="max-h-[420px] overflow-auto rounded-2xl border border-white/8 bg-slate-950/60 p-4 text-xs leading-5 text-slate-300">
                  {JSON.stringify(promptContext.context_json, null, 2)}
                </pre>
              </div>
            </section>
          ) : null}

          <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
            <h2 className="text-xl font-semibold text-white">Brand rules</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              Update the audience, tone, hooks, and platform preferences that feed the idea and
              script generation pipeline.
            </p>
            <div className="mt-6">
              <BrandProfileForm
                key={`${brandProfile.id}-${brandProfile.updated_at}`}
                initialValue={brandProfile}
                onSubmit={handleSubmit}
                submitLabel="Save brand profile"
              />
            </div>
          </section>
        </>
      ) : null}
    </main>
  );
}
