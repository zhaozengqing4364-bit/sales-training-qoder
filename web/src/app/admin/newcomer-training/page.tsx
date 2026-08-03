import { FoundationOperationsOverview } from "@/components/admin/newcomer-training/operations-overview";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";

export default async function NewcomerTrainingAdminPage() {
    await requireServerSession({
        requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES],
        unauthorizedRedirectTo: "/",
    });
    return <FoundationOperationsOverview />;
}
