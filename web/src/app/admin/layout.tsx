import { AdminShell } from "@/components/layout/admin-shell";
import { requireServerSession } from "@/lib/server-auth";

export default async function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const currentUser = await requireServerSession({
        requiredRoles: [
            "admin",
            "super_admin",
            "support",
            "content_admin",
            "newcomer_content_admin",
            "training_lead",
            "training_manager",
            "ops",
            "operator",
            "operations",
            "sre",
        ],
        unauthorizedRedirectTo: "/",
    });

    return (
        <AdminShell currentUser={currentUser}>{children}</AdminShell>
    );
}
