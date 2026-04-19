import Link from "next/link";
import type { ProjectActivity } from "../types/api";

type ProjectActivityPanelProps = {
  activity: ProjectActivity[];
};

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

function activityLevelClassName(level: string): string {
  switch (level) {
    case "error":
      return "border-rose-300/30 bg-rose-400/10 text-rose-100";
    case "warning":
      return "border-amber-300/30 bg-amber-400/10 text-amber-100";
    default:
      return "border-cyan-300/30 bg-cyan-400/10 text-cyan-100";
  }
}

export function ProjectActivityPanel({ activity }: ProjectActivityPanelProps) {
  return (
    <section className="rounded-[1.75rem] border border-white/10 bg-[var(--card)] p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Activity timeline</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
            Approvals and job lifecycle events are collected here so recovery decisions have a
            visible audit trail.
          </p>
        </div>
        <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-100">
          {activity.length} events
        </span>
      </div>

      {activity.length === 0 ? (
        <div className="mt-5 rounded-2xl border border-dashed border-white/10 bg-slate-950/40 p-4 text-sm text-slate-300">
          No activity has been recorded yet. Approvals and queued jobs will appear here.
        </div>
      ) : (
        <div className="mt-5 grid gap-3">
          {activity.map((entry) => {
            const jobId =
              typeof entry.metadata_json["background_job_id"] === "string"
                ? entry.metadata_json["background_job_id"]
                : null;

            return (
              <article
                className="rounded-2xl border border-white/8 bg-slate-950/40 p-4"
                key={`${entry.source_type}-${entry.source_id}-${entry.created_at}`}
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <span
                      className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${activityLevelClassName(entry.level)}`}
                    >
                      {entry.source_type.replaceAll("_", " ")}
                    </span>
                    <h3 className="mt-3 text-base font-semibold text-white">{entry.title}</h3>
                    {entry.description ? (
                      <p className="mt-2 text-sm leading-6 text-slate-300">
                        {entry.description}
                      </p>
                    ) : null}
                    {jobId ? (
                      <Link
                        className="mt-3 inline-flex rounded-full border border-cyan-300/30 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-100 transition hover:bg-cyan-400/10"
                        href={`/jobs/${jobId}`}
                      >
                        Open job detail
                      </Link>
                    ) : null}
                  </div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    {formatTimestamp(entry.created_at)}
                  </p>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
