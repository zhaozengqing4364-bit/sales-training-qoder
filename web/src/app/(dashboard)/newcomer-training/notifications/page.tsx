import { NotificationCenter } from "@/components/newcomer-training/notification-center";
import type {
    EvidenceDossierV1,
    FoundationNotificationPage,
    FoundationTaskStatusPage,
} from "@/lib/api/types/newcomer-training";
import { toNotificationCenterViewModel } from "@/lib/newcomer-training/view-models";
import { serverApiGet } from "@/lib/server-api";

const PAGE_SIZE = 20;

function resolvedPage(value: string | string[] | undefined): number {
    const parsed = Number(Array.isArray(value) ? value[0] : value);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

export default async function FoundationNotificationsPage({
    searchParams,
}: {
    searchParams: Promise<{ page?: string | string[] }>;
}) {
    const page = resolvedPage((await searchParams).page);
    const [notifications, tasks, dossier] = await Promise.allSettled([
        serverApiGet<FoundationNotificationPage>(`/newcomer-training/notifications?page=${page}&page_size=${PAGE_SIZE}`),
        serverApiGet<FoundationTaskStatusPage>(`/newcomer-training/tasks?page=${page}&page_size=${PAGE_SIZE}`),
        serverApiGet<EvidenceDossierV1>("/newcomer-training/dossier"),
    ]);
    const failedSources: string[] = [];
    if (notifications.status === "rejected") failedSources.push("训练通知");
    if (tasks.status === "rejected") failedSources.push("后台任务");
    if (dossier.status === "rejected") failedSources.push("复核结果");
    if (
        notifications.status === "rejected"
        && tasks.status === "rejected"
        && dossier.status === "rejected"
    ) {
        throw notifications.reason;
    }

    return (
        <NotificationCenter
            model={toNotificationCenterViewModel({
                notifications: notifications.status === "fulfilled" ? notifications.value : undefined,
                tasks: tasks.status === "fulfilled" ? tasks.value : undefined,
                dossier: dossier.status === "fulfilled" ? dossier.value : undefined,
                page,
                pageSize: PAGE_SIZE,
                failedSources,
            })}
        />
    );
}
