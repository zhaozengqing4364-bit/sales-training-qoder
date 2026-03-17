import { DashboardShell } from "@/components/layout/dashboard-shell";
import { requireServerSession } from "@/lib/server-auth";

export default async function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const currentUser = await requireServerSession();

    return (
        <DashboardShell currentUser={currentUser}>{children}</DashboardShell>
    );
}
