import { FoundationAdminCapabilityBoundary } from "@/components/admin/newcomer-training/workspace-nav";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";
import { ReadinessDossierWorkspace } from "./review-dossier-workspace";

export default async function FoundationReadinessDossierPage() {
    await requireServerSession({
        requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES],
        unauthorizedRedirectTo: "/",
    });
    return (
        <FoundationAdminCapabilityBoundary capability="review_readiness">
            <ReadinessDossierWorkspace />
        </FoundationAdminCapabilityBoundary>
    );
}
