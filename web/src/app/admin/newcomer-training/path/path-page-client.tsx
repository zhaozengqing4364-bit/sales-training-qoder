"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

import type { ActivityEditorResources, ResourceOption } from "@/components/admin/newcomer-training/activity-editors/types";
import { PathEditor } from "@/components/admin/newcomer-training/path-editor";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api/client";
import type {
    ActivityType,
    TrainingPathConfigResponse,
    TrainingPathPayload,
} from "@/lib/api/types/newcomer-training";
import { useSalesTrainerAdminRouteAccess } from "@/lib/sales-trainer/use-admin-route-access";

const EMPTY_RESOURCES: ActivityEditorResources = {
    learning_contents: [], exam_papers: [], scoring_rubrics: [], materials: [],
    practice_templates: [], runtime_profiles: [], coach_profiles: [],
};

type ResourceCatalogKey = keyof ActivityEditorResources;
type ResourceWarning = { key: ResourceCatalogKey; label: string };
type CatalogLoadState = "idle" | "loading" | "loaded" | "failed";

const RESOURCE_LABELS: Record<ResourceCatalogKey, string> = {
    learning_contents: "学习内容目录",
    exam_papers: "试卷目录",
    scoring_rubrics: "评分标准目录",
    materials: "讲解材料目录",
    practice_templates: "对练模板目录",
    runtime_profiles: "语音运行方案目录",
    coach_profiles: "AI 教练方案目录",
};

const ACTIVITY_RESOURCE_KEYS: Record<ActivityType, ResourceCatalogKey[]> = {
    lesson: ["learning_contents"],
    quiz: ["exam_papers"],
    audio_assessment: ["scoring_rubrics", "materials"],
    realtime_roleplay: ["practice_templates", "runtime_profiles"],
    ai_coach: ["coach_profiles"],
    assignment: [],
};

async function fetchResourceCatalog(key: ResourceCatalogKey): Promise<ResourceOption[]> {
    switch (key) {
        case "learning_contents": {
            const result = await api.learningContents.list({ status: "published" });
            return result.items.map((item) => ({ id: item.learning_content_id, title: item.title, status: item.status }));
        }
        case "exam_papers": {
            const result = await api.admin.salesTrainer.listExamPapers();
            return result.items.map((item) => ({ id: item.paper_id, title: item.title, status: item.status }));
        }
        case "scoring_rubrics":
            return api.admin.newcomerTraining.listScoringRubrics();
        case "materials": {
            const result = await api.admin.salesTrainer.listMaterials();
            return result.items.map((item) => ({ id: item.material_id, title: item.name, status: item.current_version_id ? "published" : item.status }));
        }
        case "practice_templates": {
            const result = await api.admin.listPracticeTemplates();
            return result.items.map((item) => ({ id: item.template_id, title: item.name, status: item.status }));
        }
        case "runtime_profiles": {
            const result = await api.admin.getVoiceRuntimeProfiles({ only_active: true });
            return result.items.map((item) => ({ id: item.id, title: item.name, status: item.is_active ? "published" : "archived" }));
        }
        case "coach_profiles":
            return api.admin.newcomerTraining.listCoachProfiles();
    }
}

export function NewcomerTrainingPathPageClient({
    initialModel,
}: {
    initialModel?: TrainingPathConfigResponse;
}) {
    const pathname = usePathname();
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);
    const toast = useToast();
    const [model, setModel] = useState<TrainingPathConfigResponse | null>(initialModel ?? null);
    const [loading, setLoading] = useState(!initialModel);
    const [error, setError] = useState<string | null>(null);
    const [resources, setResources] = useState<ActivityEditorResources>(EMPTY_RESOURCES);
    const [resourceWarnings, setResourceWarnings] = useState<ResourceWarning[]>([]);
    const [loadingCatalogs, setLoadingCatalogs] = useState<ResourceCatalogKey[]>([]);
    const initialLoadStarted = useRef(false);
    const catalogStates = useRef<Record<ResourceCatalogKey, CatalogLoadState>>({
        learning_contents: "idle", exam_papers: "idle", scoring_rubrics: "idle", materials: "idle",
        practice_templates: "idle", runtime_profiles: "idle", coach_profiles: "idle",
    });

    const load = useCallback(async () => {
        setError(null);
        if (!model) setLoading(true);
        try {
            setModel(await api.admin.newcomerTraining.getPath());
        } catch {
            if (!model) setError("训练路径加载失败，请检查网络后重试。");
        } finally {
            setLoading(false);
        }
    }, [model]);

    useEffect(() => {
        if (initialModel || initialLoadStarted.current) return;
        initialLoadStarted.current = true;
        void load();
    }, [initialModel, load]);

    const loadCatalog = useCallback(async (key: ResourceCatalogKey, force = false) => {
        const state = catalogStates.current[key];
        if (!force && state !== "idle") return;

        catalogStates.current[key] = "loading";
        setLoadingCatalogs((current) => current.includes(key) ? current : [...current, key]);
        try {
            const options = await fetchResourceCatalog(key);
            setResources((current) => ({ ...current, [key]: options }));
            setResourceWarnings((current) => current.filter((warning) => warning.key !== key));
            catalogStates.current[key] = "loaded";
        } catch {
            catalogStates.current[key] = "failed";
            setResourceWarnings((current) => current.some((warning) => warning.key === key)
                ? current
                : [...current, { key, label: RESOURCE_LABELS[key] }]);
        } finally {
            setLoadingCatalogs((current) => current.filter((catalogKey) => catalogKey !== key));
        }
    }, []);

    const loadResourcesForActivity = useCallback((activityType: ActivityType) => {
        ACTIVITY_RESOURCE_KEYS[activityType].forEach((key) => { void loadCatalog(key); });
    }, [loadCatalog]);

    const retryCatalog = async (warning: ResourceWarning) => {
        await loadCatalog(warning.key, true);
        if (catalogStates.current[warning.key] === "failed") {
            toast.error(`${warning.label}仍不可用，请稍后重试`);
        }
    };

    if (loading) return <div className="flex min-h-[50vh] items-center justify-center text-sm text-slate-500">正在加载训练路径…</div>;
    if (error || !model) return <div role="alert" className="mx-auto mt-12 max-w-xl rounded-2xl border border-red-200 bg-red-50 p-6 text-red-800"><p className="font-semibold">{error ?? "训练路径不可用"}</p><Button className="mt-4" variant="secondary" onClick={() => void load()}>重新加载</Button></div>;

    return <main className="min-h-screen bg-slate-50 p-4 md:p-6">
        <div className="mb-4"><SalesTrainerAdminModuleNav currentPath={pathname} capabilities={routeAccess.capabilities} /></div>
        {loadingCatalogs.length > 0 ? <div className="mb-4 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">正在加载当前活动需要的可选资源…</div> : null}
        {resourceWarnings.length > 0 ? <div role="alert" className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"><p>当前活动的部分资源暂不可用，路径仍可继续编辑。</p><div className="mt-2 flex flex-wrap gap-2">{resourceWarnings.map((warning) => <div key={warning.key} className="inline-flex items-center gap-2 rounded-xl bg-white/70 px-2 py-1"><span>{warning.label}暂不可用</span><Button size="sm" variant="outline" isLoading={loadingCatalogs.includes(warning.key)} onClick={() => void retryCatalog(warning)}>重新加载{warning.label}</Button></div>)}</div></div> : null}
        <PathEditor key={model.working_revision_id ?? model.active_revision_id ?? "empty"} initialModel={model} resources={resources}
            onResourcesNeeded={loadResourcesForActivity}
            onSave={async (payload: TrainingPathPayload, reason: string, expectedRevisionId) => { const revision = await api.admin.newcomerTraining.saveDraft(payload, reason, expectedRevisionId); toast.success("草稿已保存"); return revision; }}
            onValidate={async (payload) => { const validation = await api.admin.newcomerTraining.validateCandidate(payload); toast.success(validation.can_publish ? "检查通过，可以发布" : "检查完成，请处理未完成项"); return validation; }}
            onPublish={async (payload, reason, expectedRevisionId) => { const revision = await api.admin.newcomerTraining.publishCandidate(payload, reason, expectedRevisionId); toast.success("训练路径已发布"); void load(); return revision; }} />
    </main>;
}
