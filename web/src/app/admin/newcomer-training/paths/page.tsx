import { FoundationPathList } from "@/components/admin/newcomer-training/path-list";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";

export default async function FoundationPathsPage() {
    await requireServerSession({
        requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES],
        unauthorizedRedirectTo: "/",
    });
    return <FoundationPathList />;
}
