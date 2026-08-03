import { FoundationCohortWorkspace } from "@/components/admin/newcomer-training/cohort-workspace";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";

export default async function FoundationCohortsPage() {
    await requireServerSession({ requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES], unauthorizedRedirectTo: "/" });
    return <FoundationCohortWorkspace />;
}
