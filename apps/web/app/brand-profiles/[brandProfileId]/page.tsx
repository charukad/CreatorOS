import { BrandProfileDetail } from "../../../components/brand-profile-detail";
import {
  getBrandProfile,
  getBrandProfileReadiness,
  getBrandPromptContext,
} from "../../../lib/api";
import type {
  BrandProfile,
  BrandProfileReadiness,
  BrandPromptContext,
} from "../../../types/api";

type BrandProfilePageProps = {
  params: Promise<{
    brandProfileId: string;
  }>;
};

export const dynamic = "force-dynamic";

export default async function BrandProfilePage({ params }: BrandProfilePageProps) {
  const { brandProfileId } = await params;
  let brandProfile: BrandProfile | null = null;
  let promptContext: BrandPromptContext | null = null;
  let readiness: BrandProfileReadiness | null = null;
  let error: string | null = null;

  try {
    [brandProfile, readiness, promptContext] = await Promise.all([
      getBrandProfile(brandProfileId),
      getBrandProfileReadiness(brandProfileId),
      getBrandPromptContext(brandProfileId),
    ]);
  } catch (loadError) {
    error = loadError instanceof Error ? loadError.message : "Unable to load brand profile.";
  }

  return (
    <BrandProfileDetail
      brandProfile={brandProfile}
      error={error}
      promptContext={promptContext}
      readiness={readiness}
    />
  );
}
