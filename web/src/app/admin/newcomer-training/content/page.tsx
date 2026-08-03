import { FoundationContentWorkspace } from "@/components/admin/newcomer-training/content-workspace";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";

export default async function FoundationContentPage() {
    await requireServerSession({ requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES], unauthorizedRedirectTo: "/" });
    return <FoundationContentWorkspace />;
}
