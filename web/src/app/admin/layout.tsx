import { AdminShell } from "@/components/layout/admin-shell";
import { requireServerSession } from "@/lib/server-auth";

export default async function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const currentUser = await requireServerSession({
        requiredRoles: ["admin"],
        unauthorizedRedirectTo: "/",
    });

    return (
        <AdminShell currentUser={currentUser}>{children}</AdminShell>
    );
}
