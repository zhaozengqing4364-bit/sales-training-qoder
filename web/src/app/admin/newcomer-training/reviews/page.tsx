import { FoundationAdminCapabilityBoundary } from "@/components/admin/newcomer-training/workspace-nav";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";
import { ReadinessReviewQueueWorkspace } from "./review-queue-workspace";

export default async function FoundationReadinessReviewsPage() {
    await requireServerSession({
        requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES],
        unauthorizedRedirectTo: "/",
    });
    return (
        <FoundationAdminCapabilityBoundary capability="review_readiness">
            <ReadinessReviewQueueWorkspace />
        </FoundationAdminCapabilityBoundary>
    );
}
