import { redirect } from "next/navigation";

export default function LegacyEditSalesTrainerScorePromptPage({
    params,
}: {
    params: { id: string };
}) {
    redirect(`/admin/sales-trainer/score-standards/${params.id}/edit`);
}
