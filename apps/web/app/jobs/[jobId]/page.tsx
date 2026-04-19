import { JobDetail } from "../../../components/job-detail";
import { getJob } from "../../../lib/api";
import type { BackgroundJobDetail } from "../../../types/api";

type JobPageProps = {
  params: Promise<{
    jobId: string;
  }>;
};

export const dynamic = "force-dynamic";

export default async function JobPage({ params }: JobPageProps) {
  const { jobId } = await params;
  let detail: BackgroundJobDetail | null = null;
  let error: string | null = null;

  try {
    detail = await getJob(jobId);
  } catch (loadError) {
    error = loadError instanceof Error ? loadError.message : "Unable to load job.";
  }

  if (!detail) {
    return (
      <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-10">
        <section className="rounded-[1.5rem] border border-rose-400/30 bg-rose-500/10 p-5 text-sm text-rose-100">
          <p className="font-semibold">Could not load this job.</p>
          <p className="mt-2">{error ?? "The requested job could not be found."}</p>
        </section>
      </main>
    );
  }

  return <JobDetail detail={detail} />;
}
