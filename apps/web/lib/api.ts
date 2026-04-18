import { apiBaseUrl } from "./env";
import type {
  BrandProfile,
  BrandProfilePayload,
  Project,
  ProjectPayload,
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
