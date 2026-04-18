import { apiBaseUrl } from "./env";
import type {
  Asset,
  ApprovalDecisionPayload,
  ApprovalRecord,
  AudioGenerationPayload,
  BackgroundJob,
  BrandProfile,
  BrandProfilePayload,
  ContentIdea,
  IdeaApprovalPayload,
  Project,
  ProjectPayload,
  ProjectScript,
  SceneUpdatePayload,
  ScriptPromptPack,
  ScriptGeneratePayload,
  VisualGenerationPayload,
} from "../types/api";

type ApiErrorShape = {
  detail?: string;
  error?: {
    message?: string;
  };
};

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
  let parsedBody: (ApiErrorShape & T) | null = null;
  if (rawBody) {
    try {
      parsedBody = JSON.parse(rawBody) as ApiErrorShape & T;
    } catch {
      if (!response.ok) {
        throw new Error(rawBody);
      }
    }
  }

  if (!response.ok) {
    const message =
      parsedBody?.error?.message ??
      parsedBody?.detail ??
      `API request failed with status ${response.status}`;
    throw new Error(message);
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

export function listProjectJobs(projectId: string): Promise<BackgroundJob[]> {
  return apiRequest<BackgroundJob[]>(`/projects/${projectId}/jobs`);
}

export function listProjectAssets(projectId: string): Promise<Asset[]> {
  return apiRequest<Asset[]>(`/projects/${projectId}/assets`);
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
