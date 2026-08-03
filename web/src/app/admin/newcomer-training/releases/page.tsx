import { FoundationReleaseWorkspace } from "@/components/admin/newcomer-training/release-workspace";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";

export default async function FoundationReleasesPage() {
    await requireServerSession({ requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES], unauthorizedRedirectTo: "/" });
    return <FoundationReleaseWorkspace />;
}
