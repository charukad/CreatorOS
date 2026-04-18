export const projectStorageSections = [
  "script",
  "audio",
  "scenes",
  "rough-cuts",
  "final",
  "subtitles",
  "metadata",
] as const;

export type ProjectStorageSection = (typeof projectStorageSections)[number];

function trimSlashes(value: string): string {
  return value.replace(/^\/+|\/+$/g, "");
}

export function buildProjectStoragePath(
  projectId: string,
  section: ProjectStorageSection,
  ...segments: string[]
): string {
  const safeSegments = segments.map(trimSlashes).filter(Boolean);
  return ["storage", "projects", trimSlashes(projectId), section, ...safeSegments].join("/");
}

