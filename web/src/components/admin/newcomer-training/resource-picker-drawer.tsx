"use client";

import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/glass-modal";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { ResourceOption } from "./activity-editors/types";

export type ResourcePickerKind = "learning_content" | "exam_paper" | "material" | "scoring_rubric";

interface QuickCreatePayload {
    title: string;
    body?: string;
    file?: File | null;
    pass_score?: number;
    question_ids?: string[];
    dimensions?: Array<{ key: string; label: string; description?: string; weight: number }>;
}

interface ResourcePickerDrawerProps {
    kind: ResourcePickerKind;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onCreated: (resource: ResourceOption) => void;
    createResource?: (payload: QuickCreatePayload) => Promise<ResourceOption>;
}

const labels: Record<ResourcePickerKind, { title: string; name: string }> = {
    learning_content: { title: "快速新建学习内容", name: "内容名称" },
    exam_paper: { title: "快速组卷", name: "试卷名称" },
    material: { title: "快速新建讲解材料", name: "材料名称" },
    scoring_rubric: { title: "快速新建评分标准", name: "评分标准名称" },
};

async function createWithExistingApi(kind: ResourcePickerKind, payload: QuickCreatePayload): Promise<ResourceOption> {
    if (kind === "learning_content") {
        if (!payload.body?.trim()) throw new Error("首章节内容不能为空。");
        const content = await api.learningContents.create({ title: payload.title, summary: "在训练路径编辑器中创建" });
        await api.learningContents.addChapter(content.learning_content_id, { title: "学习要点", content: payload.body.trim() });
        const published = await api.learningContents.publish(content.learning_content_id);
        return { id: published.learning_content_id, title: published.title, status: published.status };
    }
    if (kind === "exam_paper") {
        if (!payload.question_ids?.length) throw new Error("至少填写一道题目编号。");
        const paper = await api.admin.salesTrainer.createExamPaper({
            paper_key: `path-${crypto.randomUUID()}`,
            title: payload.title,
            description: "在训练路径编辑器中创建",
            module_key: "configurable",
            pass_threshold: payload.pass_score ?? 80,
            questions: payload.question_ids.map((questionId, index) => ({ question_id: questionId, order_index: index + 1, points: 10 })),
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
    if (!payload.dimensions?.length) throw new Error("至少配置一个评分维度。");
    const rubric = await api.admin.newcomerTraining.createScoringRubric({
        title: payload.title,
        pass_score: payload.pass_score ?? 80,
        dimensions: payload.dimensions,
    });
    return rubric;
}

export function ResourcePickerDrawer({ kind, open, onOpenChange, onCreated, createResource }: ResourcePickerDrawerProps) {
    const [title, setTitle] = useState("");
    const [body, setBody] = useState("");
    const [file, setFile] = useState<File | null>(null);
    const [questionIds, setQuestionIds] = useState("");
    const [dimensionLabel, setDimensionLabel] = useState("内容准确");
    const [dimensionWeight, setDimensionWeight] = useState(1);
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    useEffect(() => { if (!open) { setTitle(""); setBody(""); setFile(null); setQuestionIds(""); setDimensionLabel("内容准确"); setDimensionWeight(1); setError(null); } }, [open]);
    const label = labels[kind];
    const submit = async () => {
        if (!title.trim()) { setError(`${label.name}不能为空。`); return; }
        if (kind === "learning_content" && !body.trim()) { setError("首章节内容不能为空。"); return; }
        const parsedQuestionIds = questionIds.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean);
        if (kind === "exam_paper" && parsedQuestionIds.length === 0) { setError("至少填写一道题目编号。"); return; }
        if (kind === "scoring_rubric" && !dimensionLabel.trim()) { setError("评分维度名称不能为空。"); return; }
        setPending(true); setError(null);
        try {
            const resource = await (createResource ?? ((data) => createWithExistingApi(kind, data)))({
                title: title.trim(), body, file, pass_score: 80,
                question_ids: parsedQuestionIds,
                dimensions: kind === "scoring_rubric" ? [{ key: `dimension_${crypto.randomUUID().replaceAll("-", "").slice(0, 10)}`, label: dimensionLabel.trim(), description: "训练路径中明确配置的评分维度", weight: dimensionWeight }] : undefined,
            });
            onCreated(resource); onOpenChange(false);
        } catch (cause) { setError(cause instanceof Error ? cause.message : getApiErrorMessage(cause)); }
        finally { setPending(false); }
    };
    return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="max-w-xl p-0"><DialogHeader className="border-b border-slate-200 px-6 py-4"><div className="flex items-center justify-between"><div><DialogTitle>{label.title}</DialogTitle><DialogDescription className="mt-1">创建、发布并自动绑定到当前活动。</DialogDescription></div><Button type="button" variant="ghost" size="icon" aria-label="关闭快速新建" onClick={() => onOpenChange(false)}><X className="h-4 w-4" /></Button></div></DialogHeader><div className="space-y-4 p-6">
        <form aria-label={label.title} className="space-y-4" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
            {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
            <label className="block text-sm font-medium text-slate-700">{label.name}<input aria-label={label.name} value={title} disabled={pending} onChange={(event) => setTitle(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2" /></label>
            {kind === "learning_content" && <label className="block text-sm font-medium text-slate-700">首章节内容<textarea aria-label="首章节内容" rows={5} value={body} disabled={pending} onChange={(event) => setBody(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2" /></label>}
            {kind === "material" && <label className="block text-sm font-medium text-slate-700">材料文件<input aria-label="材料文件" type="file" disabled={pending} onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="mt-1 block w-full text-sm" /></label>}
            {kind === "exam_paper" && <label className="block text-sm font-medium text-slate-700">题目编号<input aria-label="题目编号" value={questionIds} disabled={pending} onChange={(event) => setQuestionIds(event.target.value)} placeholder="用逗号分隔已发布题目编号" className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2" /><span className="mt-1 block text-xs font-normal text-slate-500">只会绑定你明确填写的已发布题目，不会自动抽题。</span></label>}
            {kind === "scoring_rubric" && <div className="grid gap-3 rounded-xl border border-slate-200 p-3 sm:grid-cols-[1fr_120px]"><label className="text-sm font-medium text-slate-700">评分维度名称<input aria-label="评分维度名称" value={dimensionLabel} onChange={(event) => setDimensionLabel(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2" /></label><label className="text-sm font-medium text-slate-700">权重<input aria-label="评分维度权重" type="number" min={0.1} max={100} step={0.1} value={dimensionWeight} onChange={(event) => setDimensionWeight(Number(event.target.value))} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2" /></label></div>}
            <div className="flex justify-end gap-2"><Button type="button" variant="ghost" disabled={pending} onClick={() => onOpenChange(false)}>取消</Button><Button type="submit" disabled={pending}>{pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}创建并绑定</Button></div>
        </form>
    </div></DialogContent></Dialog>;
}
