import { AdminShell } from "@/components/layout/admin-shell";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";

export default async function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const currentUser = await requireServerSession({
        requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES],
        unauthorizedRedirectTo: "/",
    });

    return (
        <AdminShell currentUser={currentUser}>{children}</AdminShell>
    );
}
