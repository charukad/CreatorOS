import { apiBaseUrl } from "./env";
import type {
  ApiErrorEnvelope,
  Asset,
  AnalyticsSnapshot,
  AnalyticsSnapshotPayload,
  ApprovalDecisionPayload,
  ApprovalRecord,
  AudioGenerationPayload,
  BackgroundJob,
  BackgroundJobDetail,
  BrandProfile,
  BrandProfilePayload,
  ContentIdea,
  IdeaApprovalPayload,
  Project,
  ProjectActivity,
  ProjectAnalytics,
  ProjectPayload,
  ProjectScript,
  ManualPublishCompletePayload,
  ManualInterventionPayload,
  PublishJob,
  ProjectArchivePayload,
  PublishJobPreparePayload,
  PublishJobSchedulePayload,
  ProjectExport,
  ProjectManualOverridePayload,
  SceneUpdatePayload,
  ScriptPromptPack,
  ScriptGeneratePayload,
  VisualGenerationPayload,
} from "../types/api";

type LegacyApiErrorShape = {
  detail?: string;
};

export class ApiRequestError extends Error {
  code: string;
  details: Record<string, unknown>;
  requestId: string | null;
  status: number;

  constructor({
    code,
    details,
    message,
    requestId,
    status,
  }: {
    code: string;
    details: Record<string, unknown>;
    message: string;
    requestId: string | null;
    status: number;
  }) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.details = details;
    this.requestId = requestId;
    this.status = status;
  }
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}/api${path}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  const rawBody = await response.text();
  let parsedBody: (Partial<ApiErrorEnvelope> & LegacyApiErrorShape & T) | null = null;
  if (rawBody) {
    try {
      parsedBody = JSON.parse(rawBody) as Partial<ApiErrorEnvelope> & LegacyApiErrorShape & T;
    } catch {
      if (!response.ok) {
        throw new Error(rawBody);
      }
    }
  }

  if (!response.ok) {
    if (parsedBody?.error) {
      throw new ApiRequestError({
        code: parsedBody.error.code,
        details: parsedBody.error.details,
        message: parsedBody.error.message,
        requestId: parsedBody.error.request_id,
        status: response.status,
      });
    }

    throw new ApiRequestError({
      code: `HTTP_${response.status}`,
      details: {},
      message: parsedBody?.detail ?? `API request failed with status ${response.status}`,
      requestId: response.headers.get("X-Request-ID"),
      status: response.status,
    });
  }

  return parsedBody as T;
}

type ProjectTransitionPayload = {
  target_status: Project["status"];
};

export function listBrandProfiles(): Promise<BrandProfile[]> {
  return apiRequest<BrandProfile[]>("/brand-profiles");
}

export function createBrandProfile(payload: BrandProfilePayload): Promise<BrandProfile> {
  return apiRequest<BrandProfile>("/brand-profiles", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getBrandProfile(brandProfileId: string): Promise<BrandProfile> {
  return apiRequest<BrandProfile>(`/brand-profiles/${brandProfileId}`);
}

export function updateBrandProfile(
  brandProfileId: string,
  payload: BrandProfilePayload,
): Promise<BrandProfile> {
  return apiRequest<BrandProfile>(`/brand-profiles/${brandProfileId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function listProjects(): Promise<Project[]> {
  return apiRequest<Project[]>("/projects");
}

export function createProject(payload: ProjectPayload): Promise<Project> {
  return apiRequest<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getProject(projectId: string): Promise<Project> {
  return apiRequest<Project>(`/projects/${projectId}`);
}

export function updateProject(projectId: string, payload: ProjectPayload): Promise<Project> {
  return apiRequest<Project>(`/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function archiveProject(
  projectId: string,
  payload: ProjectArchivePayload = {},
): Promise<Project> {
  return apiRequest<Project>(`/projects/${projectId}/archive`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function manualOverrideProjectStatus(
  projectId: string,
  payload: ProjectManualOverridePayload,
): Promise<Project> {
  return apiRequest<Project>(`/projects/${projectId}/manual-override`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function transitionProjectStatus(
  projectId: string,
  payload: ProjectTransitionPayload,
): Promise<Project> {
  return apiRequest<Project>(`/projects/${projectId}/transition`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listProjectIdeas(projectId: string): Promise<ContentIdea[]> {
  return apiRequest<ContentIdea[]>(`/projects/${projectId}/ideas`);
}

export function listProjectApprovals(projectId: string): Promise<ApprovalRecord[]> {
  return apiRequest<ApprovalRecord[]>(`/projects/${projectId}/approvals`);
}

export function listProjectActivity(projectId: string): Promise<ProjectActivity[]> {
  return apiRequest<ProjectActivity[]>(`/projects/${projectId}/activity`);
}

export function getProjectAnalytics(projectId: string): Promise<ProjectAnalytics> {
  return apiRequest<ProjectAnalytics>(`/projects/${projectId}/analytics`);
}

export function listProjectJobs(projectId: string): Promise<BackgroundJob[]> {
  return apiRequest<BackgroundJob[]>(`/projects/${projectId}/jobs`);
}

export function getJob(jobId: string): Promise<BackgroundJobDetail> {
  return apiRequest<BackgroundJobDetail>(`/jobs/${jobId}`);
}

export function cancelJob(jobId: string): Promise<BackgroundJobDetail> {
  return apiRequest<BackgroundJobDetail>(`/jobs/${jobId}/cancel`, {
    method: "POST",
  });
}

export function retryJob(jobId: string): Promise<BackgroundJobDetail> {
  return apiRequest<BackgroundJobDetail>(`/jobs/${jobId}/retry`, {
    method: "POST",
  });
}

export function markJobManualIntervention(
  jobId: string,
  payload: ManualInterventionPayload,
): Promise<BackgroundJobDetail> {
  return apiRequest<BackgroundJobDetail>(`/jobs/${jobId}/manual-intervention`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function exportProject(projectId: string): Promise<ProjectExport> {
  return apiRequest<ProjectExport>(`/projects/${projectId}/export`);
}

export function listProjectAssets(projectId: string): Promise<Asset[]> {
  return apiRequest<Asset[]>(`/projects/${projectId}/assets`);
}

export function listProjectPublishJobs(projectId: string): Promise<PublishJob[]> {
  return apiRequest<PublishJob[]>(`/projects/${projectId}/publish-jobs`);
}

export function getAssetContentUrl(assetId: string): string {
  return `${apiBaseUrl}/api/assets/${assetId}/content`;
}

export function generateProjectIdeas(projectId: string): Promise<ContentIdea[]> {
  return apiRequest<ContentIdea[]>(`/projects/${projectId}/ideas/generate`, {
    method: "POST",
  });
}

export function approveIdea(
  ideaId: string,
  payload: IdeaApprovalPayload = {},
): Promise<ContentIdea> {
  return apiRequest<ContentIdea>(`/ideas/${ideaId}/approve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function rejectIdea(
  ideaId: string,
  payload: ApprovalDecisionPayload = {},
): Promise<ContentIdea> {
  return apiRequest<ContentIdea>(`/ideas/${ideaId}/reject`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCurrentProjectScript(projectId: string): Promise<ProjectScript | null> {
  return apiRequest<ProjectScript | null>(`/projects/${projectId}/scripts/current`);
}

export function getScriptPromptPack(scriptId: string): Promise<ScriptPromptPack> {
  return apiRequest<ScriptPromptPack>(`/scripts/${scriptId}/prompt-pack`);
}

export function queueAudioGeneration(
  projectId: string,
  payload: AudioGenerationPayload = {},
): Promise<BackgroundJob> {
  return apiRequest<BackgroundJob>(`/projects/${projectId}/generate/audio`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function queueVisualGeneration(
  projectId: string,
  payload: VisualGenerationPayload = {},
): Promise<BackgroundJob> {
  return apiRequest<BackgroundJob>(`/projects/${projectId}/generate/visuals`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function queueRoughCut(projectId: string): Promise<BackgroundJob> {
  return apiRequest<BackgroundJob>(`/projects/${projectId}/compose/rough-cut`, {
    method: "POST",
  });
}

export function approveFinalVideo(
  projectId: string,
  payload: ApprovalDecisionPayload = {},
): Promise<ApprovalRecord> {
  return apiRequest<ApprovalRecord>(`/projects/${projectId}/final-video/approve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function rejectFinalVideo(
  projectId: string,
  payload: ApprovalDecisionPayload = {},
): Promise<ApprovalRecord> {
  return apiRequest<ApprovalRecord>(`/projects/${projectId}/final-video/reject`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function preparePublishJob(
  projectId: string,
  payload: PublishJobPreparePayload,
): Promise<PublishJob> {
  return apiRequest<PublishJob>(`/projects/${projectId}/publish-jobs/prepare`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function approvePublishJob(
  publishJobId: string,
  payload: ApprovalDecisionPayload = {},
): Promise<PublishJob> {
  return apiRequest<PublishJob>(`/publish-jobs/${publishJobId}/approve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function schedulePublishJob(
  publishJobId: string,
  payload: PublishJobSchedulePayload,
): Promise<PublishJob> {
  return apiRequest<PublishJob>(`/publish-jobs/${publishJobId}/schedule`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function markPublishJobPublished(
  publishJobId: string,
  payload: ManualPublishCompletePayload,
): Promise<PublishJob> {
  return apiRequest<PublishJob>(`/publish-jobs/${publishJobId}/mark-published`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function syncPublishJobAnalytics(
  publishJobId: string,
  payload: AnalyticsSnapshotPayload,
): Promise<AnalyticsSnapshot> {
  return apiRequest<AnalyticsSnapshot>(`/publish-jobs/${publishJobId}/sync-analytics`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function approveProjectAssets(
  projectId: string,
  payload: ApprovalDecisionPayload = {},
): Promise<ApprovalRecord> {
  return apiRequest<ApprovalRecord>(`/projects/${projectId}/assets/approve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function rejectProjectAssets(
  projectId: string,
  payload: ApprovalDecisionPayload = {},
): Promise<ApprovalRecord> {
  return apiRequest<ApprovalRecord>(`/projects/${projectId}/assets/reject`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function generateProjectScript(
  projectId: string,
  payload: ScriptGeneratePayload = {},
): Promise<ProjectScript> {
  return apiRequest<ProjectScript>(`/projects/${projectId}/scripts/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateScene(sceneId: string, payload: SceneUpdatePayload) {
  return apiRequest<ProjectScript["scenes"][number]>(`/scenes/${sceneId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function approveScript(
  scriptId: string,
  payload: ApprovalDecisionPayload = {},
): Promise<ProjectScript> {
  return apiRequest<ProjectScript>(`/scripts/${scriptId}/approve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function rejectScript(
  scriptId: string,
  payload: ApprovalDecisionPayload = {},
): Promise<ProjectScript> {
  return apiRequest<ProjectScript>(`/scripts/${scriptId}/reject`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
