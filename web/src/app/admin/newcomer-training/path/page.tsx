import type { TrainingPathConfigResponse } from "@/lib/api/types/newcomer-training";
import { serverApiGet } from "@/lib/server-api";

import { NewcomerTrainingPathPageClient } from "./path-page-client";

export default async function NewcomerTrainingPathPage() {
    const initialModel = await serverApiGet<TrainingPathConfigResponse>(
        "/admin/newcomer-training/path/",
    );
    return <NewcomerTrainingPathPageClient initialModel={initialModel} />;
}
