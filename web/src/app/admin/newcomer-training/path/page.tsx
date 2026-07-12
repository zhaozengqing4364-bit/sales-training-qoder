"use client";

import { useCallback, useEffect, useState } from "react";

import { PathEditor } from "@/components/admin/newcomer-training/path-editor";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api/client";
import type { TrainingPathConfigResponse, TrainingPathPayload } from "@/lib/api/types/newcomer-training";

export default function NewcomerTrainingPathPage() {
    const toast = useToast();
    const [model, setModel] = useState<TrainingPathConfigResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const load = useCallback(async () => {
        setLoading(true); setError(null);
        try { setModel(await api.admin.newcomerTraining.getPath()); }
        catch { setError("训练路径加载失败，请检查网络后重试。"); }
        finally { setLoading(false); }
    }, []);
    useEffect(() => { void load(); }, [load]);

    if (loading) return <div className="flex min-h-[50vh] items-center justify-center text-sm text-slate-500">正在加载训练路径…</div>;
    if (error || !model) return <div role="alert" className="mx-auto mt-12 max-w-xl rounded-2xl border border-red-200 bg-red-50 p-6 text-red-800"><p className="font-semibold">{error ?? "训练路径不可用"}</p><Button className="mt-4" variant="secondary" onClick={() => void load()}>重新加载</Button></div>;

    return <main className="min-h-screen bg-slate-50 p-4 md:p-6">
        <PathEditor key={model.working_revision_id ?? model.active_revision_id ?? "empty"} initialModel={model}
            onSave={async (payload: TrainingPathPayload, reason: string) => { await api.admin.newcomerTraining.saveDraft(payload, reason); toast.success("草稿已保存"); }}
            onValidate={async (payload) => { await api.admin.newcomerTraining.saveDraft(payload, "路径检查前自动保存"); const validation = await api.admin.newcomerTraining.validateDraft(); toast.success(validation.can_publish ? "检查通过，可以发布" : "检查完成，请处理未完成项"); return validation; }}
            onPublish={async (payload, reason) => { await api.admin.newcomerTraining.saveDraft(payload, reason); await api.admin.newcomerTraining.publish(reason); toast.success("训练路径已发布"); await load(); }} />
    </main>;
}
