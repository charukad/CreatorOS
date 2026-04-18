import { ProjectDetail } from "../../../components/project-detail";
import {
  getCurrentProjectScript,
  getProject,
  listBrandProfiles,
  listProjectIdeas,
} from "../../../lib/api";
import type { BrandProfile, ContentIdea, Project, ProjectScript } from "../../../types/api";

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
  let ideas: ContentIdea[] = [];
  let currentScript: ProjectScript | null = null;
  let error: string | null = null;

  try {
    [project, brandProfiles, ideas, currentScript] = await Promise.all([
      getProject(projectId),
      listBrandProfiles(),
      listProjectIdeas(projectId),
      getCurrentProjectScript(projectId),
    ]);
  } catch (loadError) {
    error = loadError instanceof Error ? loadError.message : "Unable to load project.";
  }

  return (
    <ProjectDetail
      brandProfiles={brandProfiles}
      currentScript={currentScript}
      error={error}
      ideas={ideas}
      project={project}
    />
  );
}
