import { FoundationCohortDetailWorkspace } from "@/components/admin/newcomer-training/cohort-detail-workspace";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";

export default async function FoundationCohortPage({ params }: { params: Promise<{ cohortId: string }> }) {
    await requireServerSession({ requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES], unauthorizedRedirectTo: "/" });
    const { cohortId } = await params;
    return <FoundationCohortDetailWorkspace cohortId={cohortId} />;
}
