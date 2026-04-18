import { BrandProfileDetail } from "../../../components/brand-profile-detail";
import { getBrandProfile } from "../../../lib/api";

type BrandProfilePageProps = {
  params: Promise<{
    brandProfileId: string;
  }>;
};

export const dynamic = "force-dynamic";

export default async function BrandProfilePage({ params }: BrandProfilePageProps) {
  const { brandProfileId } = await params;
  let brandProfile = null;
  let error: string | null = null;

  try {
    brandProfile = await getBrandProfile(brandProfileId);
  } catch (loadError) {
    error = loadError instanceof Error ? loadError.message : "Unable to load brand profile.";
  }

  return <BrandProfileDetail brandProfile={brandProfile} error={error} />;
}
