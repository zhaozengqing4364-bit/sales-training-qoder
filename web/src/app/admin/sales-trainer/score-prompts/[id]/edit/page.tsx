import { redirect } from "next/navigation";

export default function LegacyEditSalesTrainerScorePromptPage({
    params,
}: {
    params: { id: string };
}) {
    redirect(`/admin/sales-trainer/audio/score-standards/${params.id}/edit`);
}
