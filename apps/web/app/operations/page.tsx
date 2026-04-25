import Link from "next/link";
import { OperationsRecoveryCenter } from "../../components/operations-recovery-center";
import {
  getArtifactRetentionPlan,
  getOperationsRecovery,
  getWorkerPresence,
} from "../../lib/api";
import type {
  ArtifactRetentionPlan,
  OperationsRecovery,
  WorkerPresence,
} from "../../types/api";

export const dynamic = "force-dynamic";

export default async function OperationsPage() {
  let errorMessage: string | null = null;
  let recovery: OperationsRecovery | null = null;
  let retentionPlan: ArtifactRetentionPlan | null = null;
  let workerPresence: WorkerPresence | null = null;

  try {
    [recovery, retentionPlan, workerPresence] = await Promise.all([
      getOperationsRecovery(),
      getArtifactRetentionPlan(),
      getWorkerPresence(),
    ]);
  } catch (error) {
    errorMessage =
      error instanceof Error ? error.message : "Unable to load operations data.";
  }

  if (recovery === null || retentionPlan === null || workerPresence === null) {
    return (
      <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-6 px-6 py-10">
        <Link
          className="w-fit rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-200 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
          href="/"
        >
          Back to dashboard
        </Link>
        <section className="rounded-[1.75rem] border border-rose-400/30 bg-rose-500/10 p-6 text-rose-100">
          <h1 className="text-2xl font-semibold text-white">Unable to load operations data</h1>
          <p className="mt-3 text-sm leading-6">
            {errorMessage ?? "Unable to load operations data."}
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-8 px-6 py-10">
      <Link
        className="w-fit rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-200 transition hover:border-cyan-300/40 hover:bg-cyan-400/10"
        href="/"
      >
        Back to dashboard
      </Link>
      <OperationsRecoveryCenter
        recovery={recovery}
        retentionPlan={retentionPlan}
        workerPresence={workerPresence}
      />
    </main>
  );
}
