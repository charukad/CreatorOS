import { ProjectDetail } from "../../../components/project-detail";
import { getProject, listBrandProfiles } from "../../../lib/api";
import type { BrandProfile, Project } from "../../../types/api";

type ProjectPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export const dynamic = "force-dynamic";

export default async function ProjectPage({ params }: ProjectPageProps) {
  const { projectId } = await params;
  let project: Project | null = null;
  let brandProfiles: BrandProfile[] = [];
  let error: string | null = null;

  try {
    [project, brandProfiles] = await Promise.all([getProject(projectId), listBrandProfiles()]);
  } catch (loadError) {
    error = loadError instanceof Error ? loadError.message : "Unable to load project.";
  }

  return <ProjectDetail brandProfiles={brandProfiles} error={error} project={project} />;
}
