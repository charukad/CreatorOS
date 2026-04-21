import { ProjectDetail } from "../../../components/project-detail";
import {
  getCurrentProjectScript,
  getProject,
  getProjectAnalytics,
  getScriptPromptPack,
  listProjectActivity,
  listProjectAssets,
  listBrandProfiles,
  listProjectApprovals,
  listProjectIdeas,
  listProjectJobs,
  listProjectPublishJobs,
} from "../../../lib/api";
import type {
  Asset,
  ApprovalRecord,
  BackgroundJob,
  BrandProfile,
  ContentIdea,
  Project,
  ProjectActivity,
  ProjectAnalytics,
  PublishJob,
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
  let activity: ProjectActivity[] = [];
  let analytics: ProjectAnalytics = {
    insights: [],
    snapshots: [],
  };
  let approvals: ApprovalRecord[] = [];
  let assets: Asset[] = [];
  let jobs: BackgroundJob[] = [];
  let publishJobs: PublishJob[] = [];
  let currentScript: ProjectScript | null = null;
  let promptPack: ScriptPromptPack | null = null;
  let error: string | null = null;

  try {
    [
      project,
      brandProfiles,
      ideas,
      activity,
      analytics,
      approvals,
      jobs,
      assets,
      publishJobs,
      currentScript,
    ] = await Promise.all([
      getProject(projectId),
      listBrandProfiles(),
      listProjectIdeas(projectId),
      listProjectActivity(projectId),
      getProjectAnalytics(projectId),
      listProjectApprovals(projectId),
      listProjectJobs(projectId),
      listProjectAssets(projectId),
      listProjectPublishJobs(projectId),
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
      activity={activity}
      analytics={analytics}
      assets={assets}
      approvals={approvals}
      brandProfiles={brandProfiles}
      currentScript={currentScript}
      error={error}
      ideas={ideas}
      jobs={jobs}
      promptPack={promptPack}
      project={project}
      publishJobs={publishJobs}
    />
  );
}
