import { requireServerSession } from "@/lib/server-auth";

export default async function UserLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    await requireServerSession();

    return children;
}
