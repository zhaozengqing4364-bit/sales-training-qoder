"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { PathEditor } from "@/components/admin/newcomer-training/path-editor";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api/client";
import type { TrainingPathConfigResponse, TrainingPathPayload } from "@/lib/api/types/newcomer-training";
import type { ActivityEditorResources } from "@/components/admin/newcomer-training/activity-editors/types";
import { useSalesTrainerAdminRouteAccess } from "@/lib/sales-trainer/use-admin-route-access";

const EMPTY_RESOURCES: ActivityEditorResources = { learning_contents: [], exam_papers: [], scoring_rubrics: [], materials: [], practice_templates: [], runtime_profiles: [], coach_profiles: [] };
type ResourceCatalogKey = keyof ActivityEditorResources;
type ResourceWarning = { key: ResourceCatalogKey; label: string };

export default function NewcomerTrainingPathPage() {
    const pathname = usePathname();
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);
    const toast = useToast();
    const [model, setModel] = useState<TrainingPathConfigResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [resources, setResources] = useState<ActivityEditorResources>(EMPTY_RESOURCES);
    const [resourceWarnings, setResourceWarnings] = useState<ResourceWarning[]>([]);
    const [resourcesLoading, setResourcesLoading] = useState(true);
    const [retryingCatalog, setRetryingCatalog] = useState<ResourceCatalogKey | null>(null);
    const load = useCallback(async () => {
        setLoading(true); setError(null);
        try {
            setModel(await api.admin.newcomerTraining.getPath());
            setLoading(false);
            setResourcesLoading(true);
            const [contents, papers, rubrics, materials, templates, runtimes, coaches] = await Promise.allSettled([
                api.learningContents.list({ status: "published" }),
                api.admin.salesTrainer.listExamPapers(),
                api.admin.newcomerTraining.listScoringRubrics(),
                api.admin.salesTrainer.listMaterials(),
                api.admin.listPracticeTemplates(),
                api.admin.getVoiceRuntimeProfiles({ only_active: true }),
                api.admin.newcomerTraining.listCoachProfiles(),
            ]);
            const warnings: ResourceWarning[] = [];
            const value = <T,>(result: PromiseSettledResult<T>, fallback: T, key: ResourceCatalogKey, label: string): T => {
                if (result.status === "fulfilled") return result.value;
                warnings.push({ key, label });
                return fallback;
            };
            const contentValue = value(contents, { items: [], total: 0 }, "learning_contents", "学习内容目录");
            const paperValue = value(papers, { items: [], total: 0 }, "exam_papers", "试卷目录");
            const rubricValue = value(rubrics, [], "scoring_rubrics", "评分标准目录");
            const materialValue = value(materials, { items: [], total: 0 }, "materials", "讲解材料目录");
            const templateValue = value(templates, { items: [], total: 0 }, "practice_templates", "对练模板目录");
            const runtimeValue = value(runtimes, { items: [], total: 0 }, "runtime_profiles", "语音运行方案目录");
            const coachValue = value(coaches, [], "coach_profiles", "AI 教练方案目录");
            setResources({
                learning_contents: contentValue.items.map((item) => ({ id: item.learning_content_id, title: item.title, status: item.status })),
                exam_papers: paperValue.items.map((item) => ({ id: item.paper_id, title: item.title, status: item.status })),
                scoring_rubrics: rubricValue,
                materials: materialValue.items.map((item) => ({ id: item.material_id, title: item.name, status: item.current_version_id ? "published" : item.status })),
                practice_templates: templateValue.items.map((item) => ({ id: item.template_id, title: item.name, status: item.status })),
                runtime_profiles: runtimeValue.items.map((item) => ({ id: item.id, title: item.name, status: item.is_active ? "published" : "archived" })),
                coach_profiles: coachValue,
            });
            setResourceWarnings(warnings);
            setResourcesLoading(false);
        }
        catch {
            setModel(null);
            setError("训练路径加载失败，请检查网络后重试。");
            setLoading(false);
            setResourcesLoading(false);
        }
    }, []);
    useEffect(() => { void load(); }, [load]);

    const retryCatalog = async (warning: ResourceWarning) => {
        setRetryingCatalog(warning.key);
        try {
            let options: ActivityEditorResources[ResourceCatalogKey];
            switch (warning.key) {
                case "learning_contents": { const result = await api.learningContents.list({ status: "published" }); options = result.items.map((item) => ({ id: item.learning_content_id, title: item.title, status: item.status })); break; }
                case "exam_papers": { const result = await api.admin.salesTrainer.listExamPapers(); options = result.items.map((item) => ({ id: item.paper_id, title: item.title, status: item.status })); break; }
                case "scoring_rubrics": options = await api.admin.newcomerTraining.listScoringRubrics(); break;
                case "materials": { const result = await api.admin.salesTrainer.listMaterials(); options = result.items.map((item) => ({ id: item.material_id, title: item.name, status: item.current_version_id ? "published" : item.status })); break; }
                case "practice_templates": { const result = await api.admin.listPracticeTemplates(); options = result.items.map((item) => ({ id: item.template_id, title: item.name, status: item.status })); break; }
                case "runtime_profiles": { const result = await api.admin.getVoiceRuntimeProfiles({ only_active: true }); options = result.items.map((item) => ({ id: item.id, title: item.name, status: item.is_active ? "published" : "archived" })); break; }
                case "coach_profiles": options = await api.admin.newcomerTraining.listCoachProfiles(); break;
            }
            setResources((current) => ({ ...current, [warning.key]: options }));
            setResourceWarnings((current) => current.filter((item) => item.key !== warning.key));
        } catch {
            toast.error(`${warning.label}仍不可用，请稍后重试`);
        } finally {
            setRetryingCatalog(null);
        }
    };

    if (loading) return <div className="flex min-h-[50vh] items-center justify-center text-sm text-slate-500">正在加载训练路径…</div>;
    if (error || !model) return <div role="alert" className="mx-auto mt-12 max-w-xl rounded-2xl border border-red-200 bg-red-50 p-6 text-red-800"><p className="font-semibold">{error ?? "训练路径不可用"}</p><Button className="mt-4" variant="secondary" onClick={() => void load()}>重新加载</Button></div>;

    return <main className="min-h-screen bg-slate-50 p-4 md:p-6">
        <div className="mb-4"><SalesTrainerAdminModuleNav currentPath={pathname} capabilities={routeAccess.capabilities} /></div>
        {resourcesLoading ? <div className="mb-4 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">可选资源仍在后台加载，不影响查看和编排路径。</div> : null}
        {resourceWarnings.length > 0 ? <div role="alert" className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"><p>部分资源暂不可用，现有路径仍可编辑。</p><div className="mt-2 flex flex-wrap gap-2">{resourceWarnings.map((warning) => <div key={warning.key} className="inline-flex items-center gap-2 rounded-xl bg-white/70 px-2 py-1"><span>{warning.label}暂不可用</span><Button size="sm" variant="outline" isLoading={retryingCatalog === warning.key} onClick={() => void retryCatalog(warning)}>重新加载{warning.label}</Button></div>)}</div></div> : null}
        <PathEditor key={model.working_revision_id ?? model.active_revision_id ?? "empty"} initialModel={model} resources={resources}
            onSave={async (payload: TrainingPathPayload, reason: string, expectedRevisionId) => { const revision = await api.admin.newcomerTraining.saveDraft(payload, reason, expectedRevisionId); toast.success("草稿已保存"); return revision; }}
            onValidate={async (payload) => { const validation = await api.admin.newcomerTraining.validateCandidate(payload); toast.success(validation.can_publish ? "检查通过，可以发布" : "检查完成，请处理未完成项"); return validation; }}
            onPublish={async (payload, reason, expectedRevisionId) => { const revision = await api.admin.newcomerTraining.publishCandidate(payload, reason, expectedRevisionId); toast.success("训练路径已发布"); await load(); return revision; }} />
    </main>;
}
