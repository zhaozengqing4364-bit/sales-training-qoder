import { JourneyHome } from "@/components/newcomer-training/journey-home";
import type { FoundationJourneyProjection } from "@/lib/api/types/newcomer-training";
import { toJourneyPageViewModel } from "@/lib/newcomer-training/view-models";
import { serverApiGet, ServerApiError } from "@/lib/server-api";

export default async function NewcomerTrainingPage() {
    let journey: FoundationJourneyProjection;
    try {
        journey = await serverApiGet<FoundationJourneyProjection>(
            "/newcomer-training/journey",
        );
    } catch (error) {
        if (error instanceof ServerApiError && error.status === 403) {
            return (
                <main className="mx-auto max-w-xl px-4 py-12">
                    <section role="status" className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
                        <h1 className="font-semibold text-amber-950">没有查看新人训练的权限</h1>
                        <p className="mt-2 text-sm leading-6 text-amber-900">请联系培训负责人确认账号角色和训练分配。</p>
                    </section>
                </main>
            );
        }
        throw error;
    }
    return <JourneyHome journey={toJourneyPageViewModel(journey)} />;
}
