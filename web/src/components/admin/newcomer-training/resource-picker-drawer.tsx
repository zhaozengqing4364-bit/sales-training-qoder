"use client";

import { useEffect, useId, useRef, useState } from "react";
import { FileCheck2, Loader2, UploadCloud } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/glass-modal";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { generateClientId } from "@/lib/client-id";
import type { ResourceOption } from "./activity-editors/types";

export type ResourcePickerKind = "learning_content" | "exam_paper" | "material" | "scoring_rubric";

export type ResourceCreateResult = {
    draftPersisted?: boolean;
};

type MaterialOperationStage = "creating" | "uploading" | "publishing";

interface QuickCreatePayload {
    title: string;
    body?: string;
    file?: File | null;
    pass_score?: number;
    question_ids?: string[];
    dimensions?: Array<{ key: string; label: string; description?: string; weight: number }>;
    signal?: AbortSignal;
    onMaterialStageChange?: (stage: MaterialOperationStage) => void;
    resumeMaterialId?: string | null;
    onMaterialCreated?: (materialId: string) => void;
}

interface ResourcePickerDrawerProps {
    kind: ResourcePickerKind;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onCreated: (resource: ResourceOption) => void | Promise<void | ResourceCreateResult>;
    /** 打开「去完善提示词」前确保路径草稿已保存；返回 false 时不跳转。 */
    onBeforeRefineNavigate?: () => Promise<boolean>;
    createResource?: (payload: QuickCreatePayload) => Promise<ResourceOption>;
}

const labels: Record<ResourcePickerKind, { title: string; name: string }> = {
    learning_content: { title: "新建学习内容", name: "内容名称" },
    exam_paper: { title: "新建试卷", name: "试卷名称" },
    material: { title: "上传讲解材料", name: "材料名称" },
    scoring_rubric: { title: "新建评分标准", name: "评分标准名称" },
};

const MATERIAL_FILE_ACCEPT = [
    ".ppt",
    ".pptx",
    ".pdf",
    ".doc",
    ".docx",
    ".md",
    ".txt",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".mp3",
    ".wav",
    ".m4a",
    ".webm",
].join(",");

const RAW_SERVER_ERROR_PATTERN = /^\[HTTP_5\d\d\]$/;
const MATERIAL_CANCELLED_MESSAGE = "已取消上传。材料名称和已选文件均已保留，可直接重试。";

const materialOperationLabels: Record<MaterialOperationStage, string> = {
    creating: "正在创建材料记录…",
    uploading: "正在上传文件…",
    publishing: "正在发布并绑定…",
};

function formatFileSize(sizeBytes: number): string {
    if (sizeBytes < 1024) return `${sizeBytes} B`;
    if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
    return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getQuickCreateErrorMessage(kind: ResourcePickerKind, cause: unknown): string {
    const message = getApiErrorMessage(cause);
    if (kind !== "material") return message;
    const detail = RAW_SERVER_ERROR_PATTERN.test(message)
        ? "服务暂时无法处理该文件，请稍后重试；若问题持续，请联系管理员。"
        : message;
    const recovery = detail.includes("均已保留")
        ? ""
        : " 材料名称和已选文件均已保留，可直接重试。";
    return `上传未完成。${detail}${recovery}`;
}

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
            paper_key: `path-${generateClientId()}`,
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
        payload.onMaterialStageChange?.("creating");
        let materialId = payload.resumeMaterialId;
        if (materialId) {
            await api.admin.salesTrainer.updateMaterial(
                materialId,
                { name: payload.title },
                payload.signal,
            );
        } else {
            const material = await api.admin.salesTrainer.createMaterial(
                { material_key: `path-${generateClientId()}`, name: payload.title, material_type: "attachment", purpose: "training_activity" },
                payload.signal,
            );
            materialId = material.material_id;
            payload.onMaterialCreated?.(materialId);
        }
        payload.onMaterialStageChange?.("uploading");
        const version = await api.admin.salesTrainer.uploadMaterialVersion(
            materialId,
            { file: payload.file, version_label: "1.0", title: payload.title, release_notes: "训练路径快速新建" },
            payload.signal,
        );
        payload.onMaterialStageChange?.("publishing");
        await api.admin.salesTrainer.publishMaterialVersion(version.version_id, payload.signal);
        return { id: materialId, title: payload.title, status: "published" };
    }
    if (!payload.dimensions?.length) throw new Error("至少配置一个评分维度。");
    const rubric = await api.admin.newcomerTraining.createScoringRubric({
        title: payload.title,
        pass_score: payload.pass_score ?? 80,
        dimensions: payload.dimensions,
    });
    return rubric;
}

export function ResourcePickerDrawer({ kind, open, onOpenChange, onCreated, onBeforeRefineNavigate, createResource }: ResourcePickerDrawerProps) {
    const [title, setTitle] = useState("");
    const [body, setBody] = useState("");
    const [file, setFile] = useState<File | null>(null);
    const [questionIds, setQuestionIds] = useState("");
    const [dimensionLabel, setDimensionLabel] = useState("内容准确");
    const [dimensionWeight, setDimensionWeight] = useState(1);
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [materialStage, setMaterialStage] = useState<MaterialOperationStage | null>(null);
    const [materialDraftId, setMaterialDraftId] = useState<string | null>(null);
    const [createdRubric, setCreatedRubric] = useState<ResourceOption | null>(null);
    const [draftPersisted, setDraftPersisted] = useState<boolean | null>(null);
    const [refinePending, setRefinePending] = useState(false);
    const [refineError, setRefineError] = useState<string | null>(null);
    const fileInputId = useId();
    const fileHelpId = useId();
    const fileInputRef = useRef<HTMLInputElement>(null);
    const activeMaterialControllerRef = useRef<AbortController | null>(null);
    const openRef = useRef(open);
    const mountedRef = useRef(true);
    openRef.current = open;
    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
        };
    }, []);
    useEffect(() => {
        if (open) return;
        activeMaterialControllerRef.current?.abort();
        activeMaterialControllerRef.current = null;
        setTitle("");
        setBody("");
        setFile(null);
        setQuestionIds("");
        setDimensionLabel("内容准确");
        setDimensionWeight(1);
        setPending(false);
        setMaterialStage(null);
        setMaterialDraftId(null);
        setCreatedRubric(null);
        setDraftPersisted(null);
        setRefinePending(false);
        setRefineError(null);
        setError(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
    }, [open]);
    useEffect(() => () => {
        activeMaterialControllerRef.current?.abort();
        activeMaterialControllerRef.current = null;
    }, []);
    const label = labels[kind];
    const abortMaterialUpload = (message?: string) => {
        const controller = activeMaterialControllerRef.current;
        if (!controller) return;
        activeMaterialControllerRef.current = null;
        controller.abort();
        setPending(false);
        setMaterialStage(null);
        if (message) setError(message);
    };
    const handleOpenChange = (nextOpen: boolean) => {
        // 去完善前的草稿保存进行中时，禁止关闭以免跳过保存结果或在卸载后误开编辑页
        if (!nextOpen && refinePending) return;
        if (!nextOpen) abortMaterialUpload();
        onOpenChange(nextOpen);
    };
    const submit = async () => {
        if (kind === "material" && !file) { setError("请选择要上传的材料文件。"); return; }
        if (!title.trim()) { setError(`${label.name}不能为空。`); return; }
        if (kind === "learning_content" && !body.trim()) { setError("首章节内容不能为空。"); return; }
        const parsedQuestionIds = questionIds.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean);
        if (kind === "exam_paper" && parsedQuestionIds.length === 0) { setError("至少填写一道题目编号。"); return; }
        if (kind === "scoring_rubric" && !dimensionLabel.trim()) { setError("评分维度名称不能为空。"); return; }
        const materialController = kind === "material" ? new AbortController() : null;
        if (materialController) {
            activeMaterialControllerRef.current?.abort();
            activeMaterialControllerRef.current = materialController;
            setMaterialStage("creating");
        }
        setPending(true); setError(null);
        try {
            const resource = await (createResource ?? ((data) => createWithExistingApi(kind, data)))({
                title: title.trim(), body, file, pass_score: 80,
                question_ids: parsedQuestionIds,
                dimensions: kind === "scoring_rubric" ? [{ key: `dimension_${generateClientId().replaceAll("-", "").slice(0, 10)}`, label: dimensionLabel.trim(), description: "训练路径中明确配置的评分维度", weight: dimensionWeight }] : undefined,
                signal: materialController?.signal,
                onMaterialStageChange: (stage) => {
                    if (
                        activeMaterialControllerRef.current === materialController
                        && !materialController?.signal.aborted
                    ) {
                        setMaterialStage(stage);
                    }
                },
                resumeMaterialId: materialDraftId,
                onMaterialCreated: setMaterialDraftId,
            });
            if (materialController?.signal.aborted) return;
            const createResult = await Promise.resolve(onCreated(resource));
            if (kind === "scoring_rubric") {
                setCreatedRubric(resource);
                setDraftPersisted(
                    createResult && typeof createResult === "object" && "draftPersisted" in createResult
                        ? Boolean(createResult.draftPersisted)
                        : null,
                );
                setRefineError(null);
                return;
            }
            handleOpenChange(false);
        } catch (cause) {
            if (!materialController?.signal.aborted) {
                setError(getQuickCreateErrorMessage(kind, cause));
            }
        } finally {
            if (!materialController || activeMaterialControllerRef.current === materialController) {
                if (materialController) activeMaterialControllerRef.current = null;
                setPending(false);
                setMaterialStage(null);
            }
        }
    };
    const openRefinePrompt = async () => {
        if (!createdRubric) return;
        const href = `/admin/sales-trainer/score-standards/${encodeURIComponent(createdRubric.id)}/edit`;
        // 必须在点击事件的同步阶段创建新页，否则等待草稿保存后再 window.open
        // 会被浏览器当作非用户触发的弹窗而拦截。
        const refineWindow = window.open("about:blank", "_blank");
        if (!refineWindow) {
            setRefineError("浏览器阻止了评分标准编辑页，请允许本站打开新页面后重试。");
            return;
        }
        refineWindow.opener = null;
        setRefinePending(true);
        setRefineError(null);
        try {
            if (onBeforeRefineNavigate) {
                const canNavigate = await onBeforeRefineNavigate();
                if (!mountedRef.current || !openRef.current) {
                    refineWindow.close();
                    return;
                }
                if (!canNavigate) {
                    refineWindow.close();
                    setDraftPersisted(false);
                    setRefineError("路径草稿保存失败，请先保存草稿后再去完善提示词。");
                    return;
                }
                setDraftPersisted(true);
            }
            // 保存等待期间若抽屉已关闭或卸载，禁止再打开编辑页
            if (!mountedRef.current || !openRef.current) {
                refineWindow.close();
                return;
            }
            refineWindow.location.replace(href);
        } catch (cause) {
            refineWindow.close();
            if (!mountedRef.current || !openRef.current) return;
            setDraftPersisted(false);
            setRefineError(cause instanceof Error ? cause.message : "路径草稿保存失败，请先保存草稿后再去完善提示词。");
        } finally {
            if (mountedRef.current && openRef.current) setRefinePending(false);
        }
    };
    const submitLabel = kind === "material" ? "上传并绑定" : "创建并绑定";
    const pendingLabel = kind === "material"
        ? materialOperationLabels[materialStage ?? "creating"]
        : kind === "scoring_rubric"
            ? "正在创建、绑定并保存草稿…"
            : "正在创建并绑定…";
    const dialogDescription = kind === "material"
        ? "选择文件后会自动创建、发布并绑定到当前活动；材料名称可在上传前修改。"
        : kind === "scoring_rubric"
            ? "填写名称与维度后即可创建并绑定；系统会写入默认评分提示词，可稍后完善。"
            : "完成后自动发布并绑定到当前活动，无需离开本页。";
    if (createdRubric && kind === "scoring_rubric") {
        const persistStatusMessage = draftPersisted === true
            ? "评分标准已创建；路径草稿已保存。"
            : draftPersisted === false
                ? "评分标准已创建并绑定，但路径草稿尚未保存成功。请先保存草稿，再去完善提示词或离开本页。"
                : "评分标准已创建并绑定到当前活动。";
        return <Dialog open={open} onOpenChange={handleOpenChange}><DialogContent className="max-w-xl p-0"><DialogHeader className="border-b border-slate-200 px-6 py-4 pr-12"><DialogTitle>评分标准已绑定</DialogTitle><DialogDescription className="mt-1">「{createdRubric.title}」已绑定到当前活动，可继续完善提示词，或稍后在录音评分标准页编辑。</DialogDescription></DialogHeader><div className="space-y-4 p-6">
            <div
                role={draftPersisted === false ? "alert" : "status"}
                className={draftPersisted === false
                    ? "rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
                    : "rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"}
            >
                {persistStatusMessage}
            </div>
            {refineError && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{refineError}</div>}
            <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
                <Button type="button" variant="ghost" disabled={refinePending} aria-busy={refinePending} onClick={() => void openRefinePrompt()}>
                    {refinePending && <Loader2 aria-hidden="true" className="mr-2 h-4 w-4 animate-spin" />}
                    去完善提示词
                </Button>
                <Button type="button" disabled={refinePending} onClick={() => handleOpenChange(false)}>完成</Button>
            </div>
        </div></DialogContent></Dialog>;
    }
    return <Dialog open={open} onOpenChange={handleOpenChange}><DialogContent className="max-w-xl p-0"><DialogHeader className="border-b border-slate-200 px-6 py-4 pr-12"><DialogTitle>{label.title}</DialogTitle><DialogDescription className="mt-1">{dialogDescription}</DialogDescription></DialogHeader><div className="space-y-4 p-6">
        <form aria-label={label.title} className="space-y-4" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
            {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
            {pending && kind === "material" && <div role="status" aria-live="polite" className="flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50 px-3 py-3 text-sm text-blue-900">
                <Loader2 aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
                <div>
                    <p className="font-medium">{pendingLabel}</p>
                    <p className="mt-1 text-xs leading-5 text-blue-700">文件和材料名称已保留。如长时间无响应，可取消本次上传后直接重试。</p>
                </div>
            </div>}
            {kind === "material" && <div className="space-y-2">
                <label htmlFor={fileInputId} className="block text-sm font-medium text-slate-700">材料文件</label>
                <label htmlFor={fileInputId} aria-disabled={pending} data-file-state={file ? "selected" : "empty"} className={`group flex min-h-32 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50/80 px-4 py-5 text-center transition-[border-color,background-color,box-shadow] focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 ${pending ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-slate-400 hover:bg-slate-100/80"}`}>
                    <input ref={fileInputRef} id={fileInputId} aria-label="材料文件" aria-describedby={fileHelpId} type="file" accept={MATERIAL_FILE_ACCEPT} disabled={pending} onChange={(event) => { setFile(event.target.files?.[0] ?? null); setError(null); }} className="sr-only" />
                    {file ? <span aria-live="polite" className="flex min-w-0 items-center gap-3 text-left">
                        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700"><FileCheck2 aria-hidden="true" className="h-5 w-5" /></span>
                        <span className="min-w-0">
                            <span className="block text-xs font-medium text-emerald-700">已选择文件</span>
                            <span className="mt-0.5 block break-all text-sm font-semibold text-slate-900">{file.name}</span>
                            <span className="mt-1 block text-xs text-slate-500">{formatFileSize(file.size)} · 点击可重新选择</span>
                        </span>
                    </span> : <span className="flex flex-col items-center">
                        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-slate-600 shadow-sm ring-1 ring-slate-200"><UploadCloud aria-hidden="true" className="h-5 w-5" /></span>
                        <span className="mt-3 text-sm font-semibold text-slate-900">选择要上传的讲解材料</span>
                        <span className="mt-2 inline-flex min-h-9 items-center rounded-lg bg-slate-900 px-4 text-sm font-medium text-white">选择文件</span>
                    </span>}
                </label>
                <p id={fileHelpId} className="text-xs leading-5 text-slate-500">支持 PPT、PPTX、PDF、Word、Markdown、图片和常用音频文件。</p>
            </div>}
            <label className="block text-sm font-medium text-slate-700">{label.name}<input aria-label={label.name} value={title} disabled={pending} onChange={(event) => { setTitle(event.target.value); setError(null); }} className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 outline-none transition-[border-color,box-shadow] focus:border-blue-500 focus:ring-2 focus:ring-blue-100" /></label>
            {kind === "learning_content" && <label className="block text-sm font-medium text-slate-700">首章节内容<textarea aria-label="首章节内容" rows={5} value={body} disabled={pending} onChange={(event) => setBody(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2" /></label>}
            {kind === "exam_paper" && <label className="block text-sm font-medium text-slate-700">题目编号<input aria-label="题目编号" value={questionIds} disabled={pending} onChange={(event) => setQuestionIds(event.target.value)} placeholder="用逗号分隔已发布题目编号" className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2" /><span className="mt-1 block text-xs font-normal text-slate-500">只会绑定你明确填写的已发布题目，不会自动抽题。</span></label>}
            {kind === "scoring_rubric" && <div className="grid gap-3 rounded-xl border border-slate-200 p-3 sm:grid-cols-[1fr_120px]"><label className="text-sm font-medium text-slate-700">评分维度名称<input aria-label="评分维度名称" value={dimensionLabel} onChange={(event) => setDimensionLabel(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2" /></label><label className="text-sm font-medium text-slate-700">权重<input aria-label="评分维度权重" type="number" min={0.1} max={100} step={0.1} value={dimensionWeight} onChange={(event) => setDimensionWeight(Number(event.target.value))} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2" /></label></div>}
            <div className="flex justify-end gap-2 pt-1"><Button type="button" variant="ghost" disabled={pending && kind !== "material"} onClick={() => { if (pending && kind === "material") abortMaterialUpload(MATERIAL_CANCELLED_MESSAGE); else handleOpenChange(false); }}>{pending && kind === "material" ? "取消上传" : "取消"}</Button><Button type="submit" disabled={pending} aria-busy={pending}>{pending && <Loader2 aria-hidden="true" className="mr-2 h-4 w-4 animate-spin" />}{pending ? pendingLabel : submitLabel}</Button></div>
        </form>
    </div></DialogContent></Dialog>;
}
