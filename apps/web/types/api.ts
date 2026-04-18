import type { ProjectStatus } from "@creatoros/shared";

export type BrandProfile = {
  id: string;
  user_id: string;
  channel_name: string;
  niche: string;
  target_audience: string;
  tone: string;
  hook_style: string;
  cta_style: string;
  visual_style: string;
  posting_preferences_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type BrandProfilePayload = {
  channel_name: string;
  niche: string;
  target_audience: string;
  tone: string;
  hook_style: string;
  cta_style: string;
  visual_style: string;
  posting_preferences_json: Record<string, unknown>;
};

export type Project = {
  id: string;
  user_id: string;
  brand_profile_id: string;
  title: string;
  target_platform: string;
  objective: string;
  notes: string | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
};

export type ProjectPayload = {
  brand_profile_id: string;
  title: string;
  target_platform: string;
  objective: string;
  notes: string | null;
};

