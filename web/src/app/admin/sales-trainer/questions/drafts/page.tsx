"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { AlertTriangle, Check, RefreshCcw, Save, Sparkles, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    BusinessEtiquetteCapabilityConfig,
    BusinessEtiquetteQuestionDraft,
    BusinessEtiquetteQuestionDraftStatus,
    BusinessEtiquetteQuestionDraftType,
    SalesTrainerAdminCapabilities,
    SalesTrainerQuestionCategory,
} from "@/lib/api/types";

const QUESTION_TYPES: readonly BusinessEtiquetteQuestionDraftType[] = [
    "single_choice",
    "multiple_choice",
    "short_answer",
];

function typeLabel(type: BusinessEtiquetteQuestionDraftType): string {
    if (type === "single_choice") return "单选题";
    if (type === "multiple_choice") return "多选题";
    return "简答题";
}

function statusLabel(status: BusinessEtiquetteQuestionDraftStatus): string {
    if (status === "pending_review") return "待审核";
    if (status === "converted") return "已转正式草稿";
    if (status === "rejected") return "已拒绝";
    return "已通过";
}

function parseCsv(value: string): string[] {
    return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function formatOptions(draft: BusinessEtiquetteQuestionDraft | null): string {
    return JSON.stringify(draft?.options ?? [], null, 2);
}

function parseOptions(value: string) {
    const parsed = JSON.parse(value) as unknown;
    if (!Array.isArray(parsed)) {
        throw new Error("选项必须是 JSON 数组。");
    }
    return parsed.map((item) => {
        if (!item || typeof item !== "object") {
            throw new Error("每个选项必须是对象。");
        }
        const option = item as { value?: unknown; label?: unknown };
        return {
            value: String(option.value ?? "").trim(),
            label: String(option.label ?? "").trim(),
        };
    }).filter((item) => item.value && item.label);
}

function parseModelConfig(value: string): Record<string, unknown> {
    if (!value.trim()) return {};
    const parsed = JSON.parse(value) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("模型配置必须是 JSON 对象。");
    }
    return parsed as Record<string, unknown>;
}

function QuestionProductionFlow() {
    const steps = [
        ["1", "生成草稿", "AI 只写入待审核草稿箱"],
        ["2", "人工审核", "运营编辑题干、答案、解析和能力点"],
        ["3", "转正式草稿", "审核通过后创建正式题目草稿"],
        ["4", "发布题目", "到正式题目库发布后才进入候选池"],
        ["5", "小测抽题", "学员端按已发布题目和能力点抽取"],
    ] as const;
    return (
        <GlassCard className="p-5">
            <div className="grid gap-3 lg:grid-cols-5">
                {steps.map(([index, title, description]) => (
                    <div key={index} className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
                        <div className="flex items-center gap-2">
                            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white">
                                {index}
                            </span>
                            <h2 className="text-sm font-bold text-slate-900">{title}</h2>
                        </div>
                        <p className="mt-2 text-xs leading-5 text-slate-500">{description}</p>
                    </div>
                ))}
            </div>
        </GlassCard>
    );
}

export default function BusinessEtiquetteQuestionDraftsPage() {
    const pathname = usePathname();
    const isLearningTopicsPath = pathname.startsWith("/admin/sales-trainer/learning-topics");
    const searchParams = useSearchParams();
    const toast = useToast();
    const [drafts, setDrafts] = useState<BusinessEtiquetteQuestionDraft[]>([]);
    const [categories, setCategories] = useState<SalesTrainerQuestionCategory[]>([]);
    const [capabilities, setCapabilities] = useState<BusinessEtiquetteCapabilityConfig[]>([]);
    const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
    const [statusFilter, setStatusFilter] = useState<BusinessEtiquetteQuestionDraftStatus | "">("pending_review");
    const [typeFilter, setTypeFilter] = useState<BusinessEtiquetteQuestionDraftType | "">("");
    const [chapterFilter, setChapterFilter] = useState("");
    const [capabilityFilter, setCapabilityFilter] = useState("");
    const [batchFilter, setBatchFilter] = useState(searchParams.get("batch_id") ?? "");
    const [chapterOrder, setChapterOrder] = useState("1");
    const [promptTemplateId, setPromptTemplateId] = useState("");
    const [draftCount, setDraftCount] = useState("3");
    const [questionTypes, setQuestionTypes] = useState<BusinessEtiquetteQuestionDraftType[]>([
        "single_choice",
        "multiple_choice",
        "short_answer",
    ]);
    const [capabilityKeysText, setCapabilityKeysText] = useState("");
    const [modelConfigJson, setModelConfigJson] = useState("{}");
    const [reason, setReason] = useState("生成商务礼仪题目草稿");
    const [approveCategoryId, setApproveCategoryId] = useState("");
    const [reviewNotes, setReviewNotes] = useState("");
    const [editOptionsJson, setEditOptionsJson] = useState("[]");
    const [editCapabilityKeysText, setEditCapabilityKeysText] = useState("");
    const [editCorrectAnswersText, setEditCorrectAnswersText] = useState("");
    const [selectedDraftEdit, setSelectedDraftEdit] = useState<BusinessEtiquetteQuestionDraft | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [adminCapabilities, setAdminCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const selectedDraftIdRef = useRef<string | null>(null);
    const canAccessQuestions = isSalesTrainerAdminPathAllowedForCapabilities(pathname, adminCapabilities);

    const pendingCount = drafts.filter((draft) => draft.status === "pending_review").length;

    const applySelectedDraft = useCallback((draft: BusinessEtiquetteQuestionDraft | null) => {
        selectedDraftIdRef.current = draft?.draft_id ?? null;
        setSelectedDraftId(draft?.draft_id ?? null);
        setSelectedDraftEdit(draft ? { ...draft, options: draft.options.map((item) => ({ ...item })) } : null);
        setEditOptionsJson(formatOptions(draft));
        setEditCapabilityKeysText((draft?.capability_keys ?? []).join(", "));
        setEditCorrectAnswersText((draft?.correct_answers ?? []).join(", "));
        setReviewNotes(draft?.review_notes ?? "");
    }, []);

    const loadData = useCallback(async () => {
        if (!canAccessQuestions) {
            setLoadError(null);
            return;
        }
        setIsLoading(true);
        setLoadError(null);
        try {
            const [draftResult, categoryResult, capabilityResult] = await Promise.all([
                api.admin.salesTrainer.listBusinessEtiquetteQuestionDrafts({
                    status: statusFilter || undefined,
                    question_type: typeFilter || undefined,
                    chapter_order: chapterFilter ? Number(chapterFilter) : undefined,
                    capability_key: capabilityFilter || undefined,
                    batch_id: batchFilter || undefined,
                    limit: 100,
                }),
                api.admin.salesTrainer.listQuestionCategories(),
                api.admin.salesTrainer.getBusinessEtiquetteCapabilities(),
            ]);
            setDrafts(draftResult.items);
            setCategories(categoryResult.items);
            setCapabilities(capabilityResult.capabilities);
            const currentSelectedId = selectedDraftIdRef.current;
            if (!currentSelectedId || !draftResult.items.some((draft) => draft.draft_id === currentSelectedId)) {
                applySelectedDraft(draftResult.items[0] ?? null);
            }
        } catch (error) {
            const message = getApiErrorMessage(error);
            setDrafts([]);
            setCategories([]);
            setCapabilities([]);
            applySelectedDraft(null);
            setLoadError(message);
            toast.error(message);
        } finally {
            setIsLoading(false);
        }
    }, [
        applySelectedDraft,
        batchFilter,
        canAccessQuestions,
        capabilityFilter,
        chapterFilter,
        statusFilter,
        toast,
        typeFilter,
    ]);

    useEffect(() => {
        let isCurrent = true;
        void api.admin.salesTrainer.getCapabilities()
            .then((result) => {
                if (!isCurrent) return;
                setAdminCapabilities(result);
                setCapabilityError(null);
            })
            .catch((error) => {
                if (!isCurrent) return;
                setAdminCapabilities(null);
                setCapabilityError(getApiErrorMessage(error));
            })
            .finally(() => {
                if (!isCurrent) return;
                setIsCapabilityLoading(false);
            });
        return () => {
            isCurrent = false;
        };
    }, []);

    useEffect(() => {
        if (isCapabilityLoading) {
            return undefined;
        }
        if (!canAccessQuestions) {
            setDrafts([]);
            setCategories([]);
            setCapabilities([]);
            applySelectedDraft(null);
            setLoadError(null);
            setIsLoading(false);
            return undefined;
        }
        const timer = window.setTimeout(() => {
            void loadData();
        }, 0);
        return () => window.clearTimeout(timer);
    }, [applySelectedDraft, canAccessQuestions, isCapabilityLoading, loadData]);

    function toggleQuestionType(type: BusinessEtiquetteQuestionDraftType) {
        setQuestionTypes((current) => (
            current.includes(type)
                ? current.filter((item) => item !== type)
                : [...current, type]
        ));
    }

    async function generateDrafts() {
        if (!promptTemplateId.trim()) {
            toast.error("请填写 Prompt 模板 ID。");
            return;
        }
        if (!questionTypes.length) {
            toast.error("至少选择一种题型。");
            return;
        }
        setIsGenerating(true);
        try {
            const result = await api.admin.salesTrainer.generateBusinessEtiquetteQuestionDrafts({
                chapter_order: Number(chapterOrder),
                prompt_template_id: promptTemplateId.trim(),
                question_types: questionTypes,
                draft_count: Number(draftCount),
                capability_keys: parseCsv(capabilityKeysText),
                model_config: parseModelConfig(modelConfigJson),
                reason,
            });
            toast.success(`已生成 ${result.total} 道待审核题目草稿。`);
            setBatchFilter(result.batch_id);
            setStatusFilter("pending_review");
            await loadData();
            applySelectedDraft(result.items[0] ?? null);
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsGenerating(false);
        }
    }

    function patchSelectedDraft(patch: Partial<BusinessEtiquetteQuestionDraft>) {
        setSelectedDraftEdit((current) => current ? { ...current, ...patch } : current);
    }

    async function saveDraft() {
        if (!selectedDraftEdit) return;
        setIsSaving(true);
        try {
            const saved = await api.admin.salesTrainer.updateBusinessEtiquetteQuestionDraft(
                selectedDraftEdit.draft_id,
                {
                    title: selectedDraftEdit.title,
                    stem: selectedDraftEdit.stem,
                    question_type: selectedDraftEdit.question_type,
                    options: parseOptions(editOptionsJson),
                    correct_answer: selectedDraftEdit.correct_answer,
                    correct_answers: parseCsv(editCorrectAnswersText),
                    reference_answer: selectedDraftEdit.reference_answer,
                    explanation: selectedDraftEdit.explanation,
                    difficulty: selectedDraftEdit.difficulty,
                    capability_keys: parseCsv(editCapabilityKeysText),
                    source_excerpt: selectedDraftEdit.source_excerpt,
                    review_notes: reviewNotes || null,
                },
            );
            toast.success("题目草稿已保存。");
            setDrafts((current) => current.map((draft) => (
                draft.draft_id === saved.draft_id ? saved : draft
            )));
            applySelectedDraft(saved);
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsSaving(false);
        }
    }

    async function approveDraft() {
        if (!selectedDraftEdit) return;
        if (!approveCategoryId) {
            toast.error("请选择题目分类。");
            return;
        }
        setIsSaving(true);
        try {
            const approved = await api.admin.salesTrainer.approveBusinessEtiquetteQuestionDraft(
                selectedDraftEdit.draft_id,
                { category_id: approveCategoryId, review_notes: reviewNotes || null },
            );
            toast.success("题目已转为正式题目草稿，请到正式题目库发布后再进入学员小测。");
            setDrafts((current) => current.map((draft) => (
                draft.draft_id === approved.draft_id ? approved : draft
            )));
            applySelectedDraft(approved);
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsSaving(false);
        }
    }

    async function rejectDraft() {
        if (!selectedDraftEdit) return;
        if (!reviewNotes.trim()) {
            toast.error("请填写拒绝原因。");
            return;
        }
        setIsSaving(true);
        try {
            const rejected = await api.admin.salesTrainer.rejectBusinessEtiquetteQuestionDraft(
                selectedDraftEdit.draft_id,
                { review_notes: reviewNotes.trim() },
            );
            toast.success("题目草稿已拒绝。");
            setDrafts((current) => current.map((draft) => (
                draft.draft_id === rejected.draft_id ? rejected : draft
            )));
            applySelectedDraft(rejected);
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsSaving(false);
        }
    }

    return (
        <AdminIndexShell
            className="space-y-5"
            header={(
                <div className="space-y-4">
                    <AdminPageHeader
                        title="AI 出题审核"
                        description="按章节生成商务礼仪题目草稿，人工审核后只会转为正式题目草稿；发布仍在正式题目库完成。"
                        primaryAction={canAccessQuestions ? (
                            <div className="flex flex-wrap gap-2">
                                <Button variant="outline" asChild>
                                    <Link href={isLearningTopicsPath
                                        ? "/admin/sales-trainer/learning-topics/questions"
                                        : "/admin/sales-trainer/questions"}>正式题目库</Link>
                                </Button>
                                <Button variant="outline" onClick={() => void loadData()}>
                                    <RefreshCcw className="mr-2 h-4 w-4" />
                                    刷新
                                </Button>
                            </div>
                        ) : null}
                    />
                    <SalesTrainerAdminModuleNav currentPath={pathname} capabilities={adminCapabilities} />
                </div>
            )}
        >
            {isCapabilityLoading ? (
                <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
                    正在校验题库管理权限...
                </div>
            ) : capabilityError || !canAccessQuestions ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-800">
                    <div className="flex items-start gap-3">
                        <AlertTriangle className="mt-0.5 h-5 w-5" aria-hidden />
                        <div>
                            <h2 className="font-bold text-amber-950">题库管理权限不足</h2>
                            <p className="mt-1 text-sm leading-6">
                                当前页不会在权限未确认时加载 AI 草稿或展示审核写入入口。请联系管理员开通题库管理权限后重试。
                            </p>
                            {capabilityError ? (
                                <p className="mt-2 text-sm font-medium">{capabilityError}</p>
                            ) : null}
                        </div>
                    </div>
                </div>
            ) : loadError ? (
                <AdminLoadErrorCard
                    title="题目草稿加载失败"
                    description="当前页不会把草稿、分类或能力点接口异常伪装成暂无草稿。请检查题库权限、Prompt 生成配置或后端服务状态后重试。"
                    message={loadError}
                    retryLabel="重新加载草稿"
                    onRetry={() => void loadData()}
                />
            ) : (
            <>
            <QuestionProductionFlow />
            <div className="grid gap-5 xl:grid-cols-[minmax(360px,0.9fr)_minmax(520px,1.1fr)]">
                <div className="space-y-5">
                    <GlassCard className="space-y-4 p-5">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-base font-semibold text-slate-950">按章节生成 AI 草稿</h2>
                                <p className="text-sm text-slate-500">
                                    建议从学习内容详情页按当前章节生成；这里保留批量补生成入口。
                                </p>
                            </div>
                            <Sparkles className="h-5 w-5 text-slate-500" aria-hidden />
                        </div>
                        <div className="grid gap-3 sm:grid-cols-2">
                            <label className="space-y-1 text-sm font-medium text-slate-700">
                                章节序号
                                <input
                                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                    min={1}
                                    type="number"
                                    value={chapterOrder}
                                    onChange={(event) => setChapterOrder(event.target.value)}
                                />
                            </label>
                            <label className="space-y-1 text-sm font-medium text-slate-700">
                                生成数量
                                <input
                                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                    max={10}
                                    min={1}
                                    type="number"
                                    value={draftCount}
                                    onChange={(event) => setDraftCount(event.target.value)}
                                />
                            </label>
                        </div>
                        <label className="space-y-1 text-sm font-medium text-slate-700">
                            Prompt 模板 ID（高级）
                            <input
                                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                value={promptTemplateId}
                                onChange={(event) => setPromptTemplateId(event.target.value)}
                            />
                        </label>
                        <div className="flex flex-wrap gap-2">
                            {QUESTION_TYPES.map((type) => (
                                <label
                                    key={type}
                                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
                                >
                                    <input
                                        checked={questionTypes.includes(type)}
                                        type="checkbox"
                                        onChange={() => toggleQuestionType(type)}
                                    />
                                    {typeLabel(type)}
                                </label>
                            ))}
                        </div>
                        <label className="space-y-1 text-sm font-medium text-slate-700">
                            能力点 key
                            <input
                                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                value={capabilityKeysText}
                                onChange={(event) => setCapabilityKeysText(event.target.value)}
                            />
                        </label>
                        <label className="space-y-1 text-sm font-medium text-slate-700">
                            模型配置 JSON
                            <textarea
                                className="min-h-24 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-xs"
                                value={modelConfigJson}
                                onChange={(event) => setModelConfigJson(event.target.value)}
                            />
                        </label>
                        <label className="space-y-1 text-sm font-medium text-slate-700">
                            操作原因
                            <input
                                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                value={reason}
                                onChange={(event) => setReason(event.target.value)}
                            />
                        </label>
                        <Button onClick={() => void generateDrafts()} disabled={isGenerating}>
                            <Sparkles className="mr-2 h-4 w-4" />
                            生成草稿
                        </Button>
                    </GlassCard>

                    <GlassCard className="space-y-4 p-5">
                        <div className="flex items-center justify-between">
                            <h2 className="text-base font-semibold text-slate-950">审核筛选</h2>
                            <span className="text-sm text-slate-500">{pendingCount} 待审</span>
                        </div>
                        <div className="grid gap-3 sm:grid-cols-2">
                            <select
                                className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                value={statusFilter}
                                onChange={(event) => setStatusFilter(event.target.value as BusinessEtiquetteQuestionDraftStatus | "")}
                            >
                                <option value="">全部状态</option>
                                <option value="pending_review">待审核</option>
                                <option value="converted">已转正式草稿</option>
                                <option value="rejected">已拒绝</option>
                            </select>
                            <select
                                className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                value={typeFilter}
                                onChange={(event) => setTypeFilter(event.target.value as BusinessEtiquetteQuestionDraftType | "")}
                            >
                                <option value="">全部题型</option>
                                {QUESTION_TYPES.map((type) => (
                                    <option key={type} value={type}>{typeLabel(type)}</option>
                                ))}
                            </select>
                            <input
                                className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                placeholder="章节序号"
                                value={chapterFilter}
                                onChange={(event) => setChapterFilter(event.target.value)}
                            />
                            <select
                                className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                value={capabilityFilter}
                                onChange={(event) => setCapabilityFilter(event.target.value)}
                            >
                                <option value="">全部能力点</option>
                                {capabilities.map((capability) => (
                                    <option key={capability.capability_key} value={capability.capability_key}>
                                        {capability.display_name}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <input
                            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                            placeholder="批次 ID"
                            value={batchFilter}
                            onChange={(event) => setBatchFilter(event.target.value)}
                        />
                    </GlassCard>
                </div>

                <div className="grid gap-5 lg:grid-cols-[minmax(260px,0.8fr)_minmax(360px,1.2fr)]">
                    <GlassCard className="p-0">
                        <div className="border-b border-slate-200 px-5 py-4">
                            <h2 className="text-base font-semibold text-slate-950">待审核草稿队列</h2>
                            <p className="text-sm text-slate-500">{isLoading ? "加载中" : `${drafts.length} 条记录`}</p>
                        </div>
                        <div className="max-h-[760px] divide-y divide-slate-100 overflow-y-auto">
                            {drafts.map((draft) => (
                                <button
                                    key={draft.draft_id}
                                    className={[
                                        "block w-full px-5 py-4 text-left transition-colors",
                                        selectedDraftId === draft.draft_id ? "bg-slate-100" : "hover:bg-slate-50",
                                    ].join(" ")}
                                    type="button"
                                    onClick={() => applySelectedDraft(draft)}
                                >
                                    <div className="flex items-center justify-between gap-3">
                                        <span className="text-sm font-semibold text-slate-950">{draft.title}</span>
                                        <span className="rounded-full bg-slate-900 px-2 py-1 text-xs text-white">
                                            {statusLabel(draft.status)}
                                        </span>
                                    </div>
                                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                                        <span>第 {draft.chapter_order} 章</span>
                                        <span>{typeLabel(draft.question_type)}</span>
                                        <span>{draft.capability_keys.join(", ")}</span>
                                    </div>
                                </button>
                            ))}
                            {!drafts.length && (
                                <div className="px-5 py-8 text-sm text-slate-500">暂无草稿</div>
                            )}
                        </div>
                    </GlassCard>

                    <GlassCard className="space-y-4 p-5">
                        {selectedDraftEdit ? (
                            <>
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                    <div>
                                        <h2 className="text-base font-semibold text-slate-950">审核编辑</h2>
                                        <p className="text-sm text-slate-500">
                                            批次 {selectedDraftEdit.batch_id.slice(0, 8)}
                                        </p>
                                    </div>
                                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                                        {statusLabel(selectedDraftEdit.status)}
                                    </span>
                                </div>
                                <label className="space-y-1 text-sm font-medium text-slate-700">
                                    题目标题
                                    <input
                                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                        disabled={selectedDraftEdit.status !== "pending_review"}
                                        value={selectedDraftEdit.title}
                                        onChange={(event) => patchSelectedDraft({ title: event.target.value })}
                                    />
                                </label>
                                <label className="space-y-1 text-sm font-medium text-slate-700">
                                    题干
                                    <textarea
                                        className="min-h-28 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                        disabled={selectedDraftEdit.status !== "pending_review"}
                                        value={selectedDraftEdit.stem}
                                        onChange={(event) => patchSelectedDraft({ stem: event.target.value })}
                                    />
                                </label>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        题型
                                        <select
                                            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                            disabled={selectedDraftEdit.status !== "pending_review"}
                                            value={selectedDraftEdit.question_type}
                                            onChange={(event) => patchSelectedDraft({
                                                question_type: event.target.value as BusinessEtiquetteQuestionDraftType,
                                            })}
                                        >
                                            {QUESTION_TYPES.map((type) => (
                                                <option key={type} value={type}>{typeLabel(type)}</option>
                                            ))}
                                        </select>
                                    </label>
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        难度
                                        <select
                                            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                            disabled={selectedDraftEdit.status !== "pending_review"}
                                            value={selectedDraftEdit.difficulty}
                                            onChange={(event) => patchSelectedDraft({
                                                difficulty: event.target.value as BusinessEtiquetteQuestionDraft["difficulty"],
                                            })}
                                        >
                                            <option value="easy">简单</option>
                                            <option value="medium">中等</option>
                                            <option value="hard">困难</option>
                                        </select>
                                    </label>
                                </div>
                                <label className="space-y-1 text-sm font-medium text-slate-700">
                                    选项 JSON
                                    <textarea
                                        className="min-h-28 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-xs"
                                        disabled={selectedDraftEdit.status !== "pending_review"}
                                        value={editOptionsJson}
                                        onChange={(event) => setEditOptionsJson(event.target.value)}
                                    />
                                </label>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        单选答案
                                        <input
                                            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                            disabled={selectedDraftEdit.status !== "pending_review"}
                                            value={selectedDraftEdit.correct_answer ?? ""}
                                            onChange={(event) => patchSelectedDraft({ correct_answer: event.target.value || null })}
                                        />
                                    </label>
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        多选答案
                                        <input
                                            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                            disabled={selectedDraftEdit.status !== "pending_review"}
                                            value={editCorrectAnswersText}
                                            onChange={(event) => setEditCorrectAnswersText(event.target.value)}
                                        />
                                    </label>
                                </div>
                                <label className="space-y-1 text-sm font-medium text-slate-700">
                                    简答参考答案
                                    <textarea
                                        className="min-h-24 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                        disabled={selectedDraftEdit.status !== "pending_review"}
                                        value={selectedDraftEdit.reference_answer ?? ""}
                                        onChange={(event) => patchSelectedDraft({ reference_answer: event.target.value || null })}
                                    />
                                </label>
                                <label className="space-y-1 text-sm font-medium text-slate-700">
                                    解析
                                    <textarea
                                        className="min-h-24 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                        disabled={selectedDraftEdit.status !== "pending_review"}
                                        value={selectedDraftEdit.explanation ?? ""}
                                        onChange={(event) => patchSelectedDraft({ explanation: event.target.value || null })}
                                    />
                                </label>
                                <label className="space-y-1 text-sm font-medium text-slate-700">
                                    能力点 key
                                    <input
                                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                        disabled={selectedDraftEdit.status !== "pending_review"}
                                        value={editCapabilityKeysText}
                                        onChange={(event) => setEditCapabilityKeysText(event.target.value)}
                                    />
                                </label>
                                <label className="space-y-1 text-sm font-medium text-slate-700">
                                    来源片段
                                    <textarea
                                        className="min-h-24 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                        disabled={selectedDraftEdit.status !== "pending_review"}
                                        value={selectedDraftEdit.source_excerpt ?? ""}
                                        onChange={(event) => patchSelectedDraft({ source_excerpt: event.target.value || null })}
                                    />
                                </label>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        题目分类
                                        <select
                                            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                            disabled={selectedDraftEdit.status !== "pending_review"}
                                            value={approveCategoryId}
                                            onChange={(event) => setApproveCategoryId(event.target.value)}
                                        >
                                            <option value="">选择分类</option>
                                            {categories.map((category) => (
                                                <option key={category.category_id} value={category.category_id}>
                                                    {category.name}
                                                </option>
                                            ))}
                                        </select>
                                        <span className="block text-xs font-normal leading-5 text-slate-500">
                                            分类只用于正式题目的管理筛选；学员小测按已发布题目和能力点抽题。
                                        </span>
                                    </label>
                                    <label className="space-y-1 text-sm font-medium text-slate-700">
                                        审核备注
                                        <input
                                            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                                            disabled={selectedDraftEdit.status !== "pending_review"}
                                            value={reviewNotes}
                                            onChange={(event) => setReviewNotes(event.target.value)}
                                        />
                                    </label>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <Button
                                        disabled={isSaving || selectedDraftEdit.status !== "pending_review"}
                                        variant="outline"
                                        onClick={() => void saveDraft()}
                                    >
                                        <Save className="mr-2 h-4 w-4" />
                                        保存草稿
                                    </Button>
                                    <Button
                                        disabled={isSaving || selectedDraftEdit.status !== "pending_review"}
                                        onClick={() => void approveDraft()}
                                    >
                                        <Check className="mr-2 h-4 w-4" />
                                        转为正式题目草稿
                                    </Button>
                                    <Button
                                        disabled={isSaving || selectedDraftEdit.status !== "pending_review"}
                                        variant="destructive"
                                        onClick={() => void rejectDraft()}
                                    >
                                        <XCircle className="mr-2 h-4 w-4" />
                                        拒绝
                                    </Button>
                                </div>
                                <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
                                    Prompt 合约 {selectedDraftEdit.prompt_contract_hash} · 修订 {selectedDraftEdit.training_pack_revision_no ?? "-"}
                                </div>
                                {selectedDraftEdit.status === "converted" && selectedDraftEdit.question_id ? (
                                    <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm leading-6 text-emerald-800">
                                        已转为正式题目草稿。下一步到{" "}
                                        <Link
                                            className="font-semibold underline underline-offset-4"
                                            href={isLearningTopicsPath
                                                ? `/admin/sales-trainer/learning-topics/questions/${selectedDraftEdit.question_id}/edit`
                                                : `/admin/sales-trainer/questions/${selectedDraftEdit.question_id}/edit`}
                                        >
                                            正式题目库
                                        </Link>
                                        {" "}检查并发布，发布后才会进入学员小测候选池。
                                    </div>
                                ) : null}
                            </>
                        ) : (
                            <div className="py-16 text-center text-sm text-slate-500">请选择一条草稿</div>
                        )}
                    </GlassCard>
                </div>
            </div>
            </>
            )}
        </AdminIndexShell>
    );
}
