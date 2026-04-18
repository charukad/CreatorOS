import { ProjectDetail } from "../../../components/project-detail";
import {
  getCurrentProjectScript,
  getProject,
  getScriptPromptPack,
  listProjectAssets,
  listBrandProfiles,
  listProjectApprovals,
  listProjectIdeas,
  listProjectJobs,
} from "../../../lib/api";
import type {
  Asset,
  ApprovalRecord,
  BackgroundJob,
  BrandProfile,
  ContentIdea,
  Project,
  ProjectScript,
  ScriptPromptPack,
} from "../../../types/api";

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
  let approvals: ApprovalRecord[] = [];
  let assets: Asset[] = [];
  let jobs: BackgroundJob[] = [];
  let currentScript: ProjectScript | null = null;
  let promptPack: ScriptPromptPack | null = null;
  let error: string | null = null;

  try {
    [project, brandProfiles, ideas, approvals, jobs, assets, currentScript] = await Promise.all([
      getProject(projectId),
      listBrandProfiles(),
      listProjectIdeas(projectId),
      listProjectApprovals(projectId),
      listProjectJobs(projectId),
      listProjectAssets(projectId),
      getCurrentProjectScript(projectId),
    ]);

    if (currentScript) {
      promptPack = await getScriptPromptPack(currentScript.id);
    }
  } catch (loadError) {
    error = loadError instanceof Error ? loadError.message : "Unable to load project.";
  }

  return (
    <ProjectDetail
      assets={assets}
      approvals={approvals}
      brandProfiles={brandProfiles}
      currentScript={currentScript}
      error={error}
      ideas={ideas}
      jobs={jobs}
      promptPack={promptPack}
      project={project}
    />
  );
}
