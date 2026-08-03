import { FoundationGovernanceSettingsWorkspace } from "@/components/admin/newcomer-training/governance-settings-workspace";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";

export default async function FoundationGovernanceSettingsPage() {
    await requireServerSession({ requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES], unauthorizedRedirectTo: "/" });
    return <FoundationGovernanceSettingsWorkspace />;
}
