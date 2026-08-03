import { FoundationAssessmentOperationsWorkspace } from "@/components/admin/newcomer-training/assessment-operations-workspace";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";

export default async function FoundationAssessmentsPage() {
    await requireServerSession({ requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES], unauthorizedRedirectTo: "/" });
    return <FoundationAssessmentOperationsWorkspace />;
}
