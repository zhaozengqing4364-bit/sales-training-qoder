"use client";

import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/glass-modal";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { ResourceOption } from "./activity-editors/types";

export type ResourcePickerKind = "learning_content" | "exam_paper" | "material" | "scoring_rubric";

interface QuickCreatePayload {
    title: string;
    body?: string;
    file?: File | null;
    pass_score?: number;
}

interface ResourcePickerDrawerProps {
    kind: ResourcePickerKind;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onCreated: (resource: ResourceOption) => void;
    createResource?: (payload: QuickCreatePayload) => Promise<ResourceOption>;
}

const labels: Record<ResourcePickerKind, { title: string; name: string; action: string }> = {
    learning_content: { title: "快速新建学习内容", name: "内容名称", action: "快速建课" },
    exam_paper: { title: "快速组卷", name: "试卷名称", action: "快速组卷" },
    material: { title: "快速新建讲解材料", name: "材料名称", action: "快速建材料" },
    scoring_rubric: { title: "快速新建评分标准", name: "评分标准名称", action: "快速建标准" },
};

async function createWithExistingApi(kind: ResourcePickerKind, payload: QuickCreatePayload): Promise<ResourceOption> {
    if (kind === "learning_content") {
        const content = await api.learningContents.create({ title: payload.title, summary: "在训练路径编辑器中创建" });
        await api.learningContents.addChapter(content.learning_content_id, { title: "学习要点", content: payload.body?.trim() || "请补充本课程的学习内容。" });
        const published = await api.learningContents.publish(content.learning_content_id);
        return { id: published.learning_content_id, title: published.title, status: published.status };
    }
    if (kind === "exam_paper") {
        const questions = await api.admin.salesTrainer.listQuestions({ status: "published" });
        if (questions.items.length === 0) throw new Error("请先至少发布一道题目，再快速组卷。");
        const paper = await api.admin.salesTrainer.createExamPaper({
            paper_key: `path-${crypto.randomUUID()}`,
            title: payload.title,
            description: "在训练路径编辑器中创建",
            module_key: "configurable",
            pass_threshold: payload.pass_score ?? 80,
            questions: questions.items.slice(0, 10).map((question, index) => ({ question_id: question.question_id, order_index: index + 1, points: 10 })),
        });
        const published = await api.admin.salesTrainer.publishExamPaper(paper.paper_id);
        return { id: published.paper_id, title: published.title, status: published.status };
    }
    if (kind === "material") {
        if (!payload.file) throw new Error("请选择要发布的材料文件。");
        const material = await api.admin.salesTrainer.createMaterial({ material_key: `path-${crypto.randomUUID()}`, name: payload.title, material_type: "attachment", purpose: "training_activity" });
        const version = await api.admin.salesTrainer.uploadMaterialVersion(material.material_id, { file: payload.file, version_label: "1.0", title: payload.title, release_notes: "训练路径快速新建" });
        await api.admin.salesTrainer.publishMaterialVersion(version.version_id);
        return { id: material.material_id, title: material.name, status: "published" };
    }
    const rubric = await api.admin.newcomerTraining.createScoringRubric({
        title: payload.title,
        pass_score: payload.pass_score ?? 80,
        dimensions: [{ key: "accuracy", label: "内容准确", description: "讲解内容准确、完整", weight: 1 }],
    });
    return rubric;
}

export function ResourcePickerDrawer({ kind, open, onOpenChange, onCreated, createResource }: ResourcePickerDrawerProps) {
    const [started, setStarted] = useState(false);
    const [title, setTitle] = useState("");
    const [body, setBody] = useState("");
    const [file, setFile] = useState<File | null>(null);
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    useEffect(() => { if (!open) { setStarted(false); setTitle(""); setBody(""); setFile(null); setError(null); } }, [open]);
    const label = labels[kind];
    const submit = async () => {
        if (!title.trim()) { setError(`${label.name}不能为空。`); return; }
        setPending(true); setError(null);
        try {
            const resource = await (createResource ?? ((data) => createWithExistingApi(kind, data)))({ title: title.trim(), body, file, pass_score: 80 });
            onCreated(resource); onOpenChange(false);
        } catch (cause) { setError(cause instanceof Error ? cause.message : getApiErrorMessage(cause)); }
        finally { setPending(false); }
    };
    return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="max-w-xl p-0"><DialogHeader className="border-b border-slate-200 px-6 py-4"><div className="flex items-center justify-between"><DialogTitle>{label.title}</DialogTitle><Button type="button" variant="ghost" size="icon" aria-label="关闭快速新建" onClick={() => onOpenChange(false)}><X className="h-4 w-4" /></Button></div></DialogHeader><div className="space-y-4 p-6">
        {!started ? <div className="rounded-2xl bg-slate-50 p-6 text-center"><p className="text-sm text-slate-600">在当前路径编辑流程中创建、发布并自动绑定，不需要离开此页面。</p><Button className="mt-4" onClick={() => setStarted(true)}>{label.action}</Button></div> : <form aria-label={label.title} className="space-y-4" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
            {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
            <label className="block text-sm font-medium text-slate-700">{label.name}<input aria-label={label.name} value={title} disabled={pending} onChange={(event) => setTitle(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2" /></label>
            {kind === "learning_content" && <label className="block text-sm font-medium text-slate-700">首章节内容<textarea aria-label="首章节内容" rows={5} value={body} disabled={pending} onChange={(event) => setBody(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2" /></label>}
            {kind === "material" && <label className="block text-sm font-medium text-slate-700">材料文件<input aria-label="材料文件" type="file" disabled={pending} onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="mt-1 block w-full text-sm" /></label>}
            {kind === "exam_paper" && <p className="rounded-xl bg-blue-50 p-3 text-sm text-blue-800">将从已发布题目中选取最多 10 道题，创建后仍可在题库中调整。</p>}
            {kind === "scoring_rubric" && <p className="rounded-xl bg-blue-50 p-3 text-sm text-blue-800">创建包含“内容准确”维度的基础标准，后续可继续完善维度。</p>}
            <div className="flex justify-end gap-2"><Button type="button" variant="ghost" disabled={pending} onClick={() => onOpenChange(false)}>取消</Button><Button type="submit" disabled={pending}>{pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}创建并绑定</Button></div>
        </form>}
    </div></DialogContent></Dialog>;
}
