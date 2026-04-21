import type { ProjectStatus } from "@creatoros/shared";
import { projectStatusTones, statusClassName } from "../lib/status-styles";

type StatusBadgeProps = {
  label: string;
  status: ProjectStatus;
};

export function StatusBadge({ label, status }: StatusBadgeProps) {
  return (
    <span
      className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${statusClassName(projectStatusTones[status])}`}
    >
      {label}
    </span>
  );
}
