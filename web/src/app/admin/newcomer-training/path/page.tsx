"use client";

import { useCallback, useEffect, useState } from "react";

import { PathEditor } from "@/components/admin/newcomer-training/path-editor";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api/client";
import type { TrainingPathConfigResponse, TrainingPathPayload } from "@/lib/api/types/newcomer-training";
import type { ActivityEditorResources } from "@/components/admin/newcomer-training/activity-editors/types";

const EMPTY_RESOURCES: ActivityEditorResources = { learning_contents: [], exam_papers: [], scoring_rubrics: [], materials: [], practice_templates: [], runtime_profiles: [], coach_profiles: [] };

export default function NewcomerTrainingPathPage() {
    const toast = useToast();
    const [model, setModel] = useState<TrainingPathConfigResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [resources, setResources] = useState<ActivityEditorResources>(EMPTY_RESOURCES);
    const load = useCallback(async () => {
        setLoading(true); setError(null);
        try {
            const [path, contents, papers, rubrics, materials, templates, runtimes, coaches] = await Promise.all([
                api.admin.newcomerTraining.getPath(),
                api.learningContents.list({ status: "published" }),
                api.admin.salesTrainer.listExamPapers(),
                api.admin.newcomerTraining.listScoringRubrics(),
                api.admin.salesTrainer.listMaterials(),
                api.admin.listPracticeTemplates(),
                api.admin.getVoiceRuntimeProfiles({ only_active: true }),
                api.admin.newcomerTraining.listCoachProfiles(),
            ]);
            setModel(path);
            setResources({
                learning_contents: contents.items.map((item) => ({ id: item.learning_content_id, title: item.title, status: item.status })),
                exam_papers: papers.items.map((item) => ({ id: item.paper_id, title: item.title, status: item.status })),
                scoring_rubrics: rubrics,
                materials: materials.items.map((item) => ({ id: item.material_id, title: item.name, status: item.current_version_id ? "published" : item.status })),
                practice_templates: templates.items.map((item) => ({ id: item.template_id, title: item.name, status: item.status })),
                runtime_profiles: runtimes.items.map((item) => ({ id: item.id, title: item.name, status: item.is_active ? "published" : "archived" })),
                coach_profiles: coaches,
            });
        }
        catch { setError("训练路径加载失败，请检查网络后重试。"); }
        finally { setLoading(false); }
    }, []);
    useEffect(() => { void load(); }, [load]);

    if (loading) return <div className="flex min-h-[50vh] items-center justify-center text-sm text-slate-500">正在加载训练路径…</div>;
    if (error || !model) return <div role="alert" className="mx-auto mt-12 max-w-xl rounded-2xl border border-red-200 bg-red-50 p-6 text-red-800"><p className="font-semibold">{error ?? "训练路径不可用"}</p><Button className="mt-4" variant="secondary" onClick={() => void load()}>重新加载</Button></div>;

    return <main className="min-h-screen bg-slate-50 p-4 md:p-6">
        <PathEditor key={model.working_revision_id ?? model.active_revision_id ?? "empty"} initialModel={model} resources={resources}
            onSave={async (payload: TrainingPathPayload, reason: string) => { await api.admin.newcomerTraining.saveDraft(payload, reason); toast.success("草稿已保存"); }}
            onValidate={async (payload) => { await api.admin.newcomerTraining.saveDraft(payload, "路径检查前自动保存"); const validation = await api.admin.newcomerTraining.validateDraft(); toast.success(validation.can_publish ? "检查通过，可以发布" : "检查完成，请处理未完成项"); return validation; }}
            onPublish={async (payload, reason) => { await api.admin.newcomerTraining.saveDraft(payload, reason); await api.admin.newcomerTraining.publish(reason); toast.success("训练路径已发布"); await load(); }} />
    </main>;
}
