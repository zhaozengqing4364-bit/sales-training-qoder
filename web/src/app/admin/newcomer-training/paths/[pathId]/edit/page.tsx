import { FoundationV2PathEditor } from "@/components/admin/newcomer-training/v2-path-editor";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";

export default async function FoundationPathEditorPage({ params }: { params: Promise<{ pathId: string }> }) {
    await requireServerSession({
        requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES],
        unauthorizedRedirectTo: "/",
    });
    const { pathId } = await params;
    return <FoundationV2PathEditor pathId={pathId} />;
}
