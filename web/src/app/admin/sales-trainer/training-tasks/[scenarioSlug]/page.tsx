import { redirect } from "next/navigation";

interface LegacyTrainingTaskDetailPageProps {
    params: Promise<{ scenarioSlug: string }>;
}

export default async function LegacyTrainingTaskDetailPage({
    params,
}: LegacyTrainingTaskDetailPageProps) {
    const { scenarioSlug } = await params;
    redirect(`/admin/sales-trainer/audio/${encodeURIComponent(scenarioSlug)}`);
}
