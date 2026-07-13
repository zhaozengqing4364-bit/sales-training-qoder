import type { TrainingPathConfigResponse } from "@/lib/api/types/newcomer-training";
import { ADMIN_CONSOLE_ROLE_VALUES } from "@/lib/auth/current-user";
import { requireServerSession } from "@/lib/server-auth";
import { serverApiGet } from "@/lib/server-api";

import { NewcomerTrainingPathPageClient } from "./path-page-client";

export default async function NewcomerTrainingPathPage() {
    await requireServerSession({
        requiredRoles: [...ADMIN_CONSOLE_ROLE_VALUES],
        unauthorizedRedirectTo: "/",
    });
    const initialModel = await serverApiGet<TrainingPathConfigResponse>(
        "/admin/newcomer-training/path/",
    );
    return <NewcomerTrainingPathPageClient initialModel={initialModel} />;
}
