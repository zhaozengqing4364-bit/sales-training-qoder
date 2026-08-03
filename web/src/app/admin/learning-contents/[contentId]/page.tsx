"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
    AlertTriangle,
    ArrowLeft,
    BookOpen,
    ChevronUp,
    ChevronDown,
    Edit3,
    ExternalLink,
    Plus,
    RefreshCcw,
    Trash2,
} from "lucide-react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    LearningChapter,
    LearningContent,
    LearningContentBindingImpactResponse,
} from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { debug } from "@/lib/debug";

const LearningContentMarkdownPreview = dynamic(
    () => import("@/components/admin/learning-contents/learning-content-markdown-preview"),
    {
        loading: () => (
            <p className="text-sm text-slate-500" role="status">
                正在显示正文…
            </p>
        ),
        ssr: false,
    },
);

function DeferredLearningContentMarkdownPreview({ content }: { content: string }) {
    const [showRichPreview, setShowRichPreview] = useState(false);

    useEffect(() => {
        const timeoutId = window.setTimeout(() => setShowRichPreview(true), 600);
        return () => window.clearTimeout(timeoutId);
    }, []);

    if (!showRichPreview) {
        return <div className="whitespace-pre-wrap text-sm leading-7 text-slate-700">{content}</div>;
    }
    return <LearningContentMarkdownPreview content={content} />;
}

const STATUS_LABELS: Record<string, string> = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
};

const STATUS_COLORS: Record<string, string> = {
    draft: "bg-slate-100 text-slate-700",
    published: "bg-emerald-100 text-emerald-700",
    archived: "bg-amber-100 text-amber-700",
};

interface GateResult {
    gate_name: string;
    status: string;
    reason_code: string;
    message: string;
}

interface GateResults {
    gate_results?: GateResult[];
}

function isGateResults(value: unknown): value is GateResults {
    return (
        value !== null &&
        typeof value === "object" &&
        "gate_results" in (value as Record<string, unknown>)
    );
}

function extractGateResults(error: unknown): GateResult[] | null {
    if (error instanceof Error && "details" in error) {
        const details = (error as { details?: unknown }).details;
        if (isGateResults(details) && Array.isArray(details.gate_results)) {
            return details.gate_results;
        }
    }
    return null;
}

interface EditingChapter {
    chapter_id: string;
    title: string;
    content: string;
}

function summarizeChapterContent(content: string): string {
    const text = content.replace(/\s+/g, " ").trim();
    if (!text) return "暂无正文";
    return text.length > 96 ? `${text.slice(0, 96)}...` : text;
}

function revisionLabel(id: string | null | undefined, no: number | null | undefined): string {
    if (!id || !no) return "暂无";
    return `v${no} · ${id.slice(0, 8)}`;
}

function bindingStatusLabel(impact: LearningContentBindingImpactResponse | null): string {
    if (!impact) return "检查中";
    if (impact.active_bindings.length > 0 && impact.working_bindings.length > 0) {
        return "学员端生效 + 待发布路径修订";
    }
    if (impact.active_bindings.length > 0) return "学员端正在使用";
    if (impact.working_bindings.length > 0) return "待发布路径修订引用";
    return "未绑定新人训练路径";
}

export default function AdminLearningContentDetailPage() {
    const { contentId } = useParams<{ contentId: string }>();

    const [content, setContent] = useState<LearningContent | null>(null);
    const [bindingImpact, setBindingImpact] = useState<LearningContentBindingImpactResponse | null>(null);
    const [bindingImpactError, setBindingImpactError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [title, setTitle] = useState("");
    const [summary, setSummary] = useState("");
    const [owner, setOwner] = useState("");
    const [source, setSource] = useState("");
    const [safetyFlagged, setSafetyFlagged] = useState(false);

    const [metaSaving, setMetaSaving] = useState(false);
    const [metaError, setMetaError] = useState<string | null>(null);

    const [newChapterTitle, setNewChapterTitle] = useState("");
    const [newChapterContent, setNewChapterContent] = useState("");
    const [chapterAdding, setChapterAdding] = useState(false);
    const [chapterError, setChapterError] = useState<string | null>(null);

    const [editingChapter, setEditingChapter] = useState<EditingChapter | null>(null);
    const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null);

    const [actionLoading, setActionLoading] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);
    const [actionNotice, setActionNotice] = useState<string | null>(null);
    const [publishGateErrors, setPublishGateErrors] = useState<GateResult[] | null>(null);
    const [confirmAction, setConfirmAction] = useState<
        | { type: "delete-chapter"; chapter: LearningChapter; affectedOrders: number[] }
        | { type: "reorder-chapter"; chapterIds: string[]; affectedOrders: number[]; direction: "up" | "down" }
        | { type: "publish" }
        | { type: "archive" }
        | null
    >(null);

    const [editDiscardConfirm, setEditDiscardConfirm] = useState<
        | { type: "cancel" }
        | { type: "switch"; chapter: LearningChapter }
        | { type: "select"; chapter: LearningChapter }
        | null
    >(null);

    const loadContent = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        setBindingImpact(null);
        setBindingImpactError(null);
        const contentRequest = api.learningContents.get(contentId);
        const bindingImpactRequest = api.learningContents.getBindingImpact(contentId);
        try {
            const data = await contentRequest;
            setContent(data);
            setTitle(data.title);
            setSummary(data.summary ?? "");
            setOwner(data.owner ?? "");
            setSource(data.source ?? "");
            setSafetyFlagged(data.safety_flagged);
            setActionError(null);
            setPublishGateErrors(null);
        } catch (err) {
            debug.error("Failed to load learning content:", err);
            setError(getApiErrorMessage(err));
            setContent(null);
            setBindingImpact(null);
        } finally {
            setIsLoading(false);
        }

        try {
            const impact = await bindingImpactRequest;
            setBindingImpact(impact);
        } catch (impactError) {
            debug.error("Failed to load learning content binding impact:", impactError);
            setBindingImpact(null);
            setBindingImpactError(getApiErrorMessage(impactError));
        }
    }, [contentId]);

    useEffect(() => {
        void Promise.resolve().then(loadContent);
    }, [loadContent]);

    const handleSaveMetadata = async () => {
        setMetaSaving(true);
        setMetaError(null);
        setActionNotice(null);
        try {
            await api.learningContents.update(contentId, {
                title: title.trim(),
                summary: summary.trim() || null,
                owner: owner.trim() || null,
                source: source.trim() || null,
                safety_flagged: safetyFlagged,
            });
            setActionNotice(content?.revision_state.save_result_copy ?? "已保存。");
            await loadContent();
        } catch (err) {
            setMetaError(getApiErrorMessage(err));
        } finally {
            setMetaSaving(false);
        }
    };

    const handleAddChapter = async () => {
        if (!newChapterTitle.trim() || !newChapterContent.trim()) {
            return;
        }
        setChapterAdding(true);
        setChapterError(null);
        setActionNotice(null);
        try {
            const chapter = await api.learningContents.addChapter(contentId, {
                title: newChapterTitle.trim(),
                content: newChapterContent.trim(),
            });
            setSelectedChapterId(chapter.chapter_id);
            setNewChapterTitle("");
            setNewChapterContent("");
            setActionNotice(content?.revision_state.save_result_copy ?? "章节已保存。");
            await loadContent();
        } catch (err) {
            setChapterError(getApiErrorMessage(err));
        } finally {
            setChapterAdding(false);
        }
    };

    const hasEditingChanges = editingChapter
        ? (() => {
            const original = content?.chapters.find(
                (c) => c.chapter_id === editingChapter.chapter_id,
            );
            if (!original) return false;
            return (
                editingChapter.title !== original.title ||
                editingChapter.content !== original.content
            );
        })()
        : false;

    const handleEditChapter = (chapter: LearningChapter) => {
        if (editingChapter && hasEditingChanges && editingChapter.chapter_id !== chapter.chapter_id) {
            setEditDiscardConfirm({ type: "switch", chapter });
            return;
        }
        setSelectedChapterId(chapter.chapter_id);
        setEditingChapter({
            chapter_id: chapter.chapter_id,
            title: chapter.title,
            content: chapter.content,
        });
    };

    const handleSaveEditChapter = async () => {
        if (!editingChapter) return;
        setChapterAdding(true);
        setChapterError(null);
        setActionNotice(null);
        try {
            await api.learningContents.updateChapter(contentId, editingChapter.chapter_id, {
                title: editingChapter.title.trim(),
                content: editingChapter.content.trim(),
            });
            setEditingChapter(null);
            setActionNotice(content?.revision_state.save_result_copy ?? "章节已保存。");
            await loadContent();
        } catch (err) {
            setChapterError(getApiErrorMessage(err));
        } finally {
            setChapterAdding(false);
        }
    };

    const handleCancelEdit = () => {
        if (hasEditingChanges) {
            setEditDiscardConfirm({ type: "cancel" });
            return;
        }
        setEditingChapter(null);
    };

    const handleSelectChapter = (chapter: LearningChapter) => {
        if (editingChapter && hasEditingChanges && editingChapter.chapter_id !== chapter.chapter_id) {
            setEditDiscardConfirm({ type: "select", chapter });
            return;
        }
        if (editingChapter && editingChapter.chapter_id !== chapter.chapter_id) {
            setEditingChapter(null);
        }
        setSelectedChapterId(chapter.chapter_id);
    };

    const handleDeleteChapter = async (chapterId: string) => {
        setChapterAdding(true);
        setChapterError(null);
        setActionNotice(null);
        try {
            await api.learningContents.deleteChapter(contentId, chapterId);
            setActionNotice(content?.revision_state.save_result_copy ?? "章节已删除。");
            await loadContent();
        } catch (err) {
            setChapterError(getApiErrorMessage(err));
        } finally {
            setChapterAdding(false);
        }
    };

    const handleDeleteChapterRequest = (chapter: LearningChapter) => {
        const affectedOrders = SORTED_CHAPTERS
            .filter((item) => item.order_index >= chapter.order_index)
            .map((item) => item.order_index);
        setConfirmAction({ type: "delete-chapter", chapter, affectedOrders });
    };

    const reorderChapters = async (chapterIds: string[]) => {
        if (!content) return;
        setChapterError(null);
        setActionNotice(null);
        try {
            await api.learningContents.reorderChapters(contentId, chapterIds);
            setActionNotice(content.revision_state.save_result_copy);
            await loadContent();
        } catch (err) {
            setChapterError(getApiErrorMessage(err));
        }
    };

    const requestReorder = (index: number, direction: "up" | "down") => {
        if (!content) return;
        const targetIndex = direction === "up" ? index - 1 : index + 1;
        if (targetIndex < 0 || targetIndex >= SORTED_CHAPTERS.length) return;
        const newOrder = SORTED_CHAPTERS.map((c) => c.chapter_id);
        const temp = newOrder[index];
        newOrder[index] = newOrder[targetIndex];
        newOrder[targetIndex] = temp;
        const affectedOrders = [
            SORTED_CHAPTERS[index]?.order_index,
            SORTED_CHAPTERS[targetIndex]?.order_index,
        ].filter((order): order is number => typeof order === "number");
        if (impactUnitsForOrders().length > 0) {
            setConfirmAction({
                type: "reorder-chapter",
                chapterIds: newOrder,
                affectedOrders,
                direction,
            });
            return;
        }
        void reorderChapters(newOrder);
    };

    const handleMoveUp = (index: number) => {
        requestReorder(index, "up");
    };

    const handleMoveDown = (index: number) => {
        requestReorder(index, "down");
    };

    const handlePublish = async () => {
        setActionLoading(true);
        setActionError(null);
        setActionNotice(null);
        setPublishGateErrors(null);
        try {
            await api.learningContents.publish(contentId);
            setActionNotice(content?.status === "published" ? "待发布修订已发布，学员端将读取最新内容。" : "学习内容已发布。");
            await loadContent();
        } catch (err) {
            const gates = extractGateResults(err);
            if (gates && gates.length > 0) {
                setPublishGateErrors(gates);
            } else {
                setActionError(getApiErrorMessage(err));
            }
        } finally {
            setActionLoading(false);
        }
    };

    const handleArchive = async () => {
        setActionLoading(true);
        setActionError(null);
        setActionNotice(null);
        setPublishGateErrors(null);
        try {
            await api.learningContents.archive(contentId);
            setActionNotice("学习内容已归档。");
            await loadContent();
        } catch (err) {
            setActionError(getApiErrorMessage(err));
        } finally {
            setActionLoading(false);
        }
    };

    const handleConfirmAction = () => {
        const action = confirmAction;
        setConfirmAction(null);
        if (!action) return;
        if (action.type === "delete-chapter") {
            void handleDeleteChapter(action.chapter.chapter_id);
            return;
        }
        if (action.type === "reorder-chapter") {
            void reorderChapters(action.chapterIds);
            return;
        }
        if (action.type === "publish") {
            void handlePublish();
            return;
        }
        void handleArchive();
    };

    const handleConfirmDiscard = () => {
        const action = editDiscardConfirm;
        setEditDiscardConfirm(null);
        if (!action) return;
        if (action.type === "cancel") {
            setEditingChapter(null);
            return;
        }
        if (action.type === "select") {
            setEditingChapter(null);
            setSelectedChapterId(action.chapter.chapter_id);
            return;
        }
        // switch to another chapter after discarding
        setSelectedChapterId(action.chapter.chapter_id);
        setEditingChapter({
            chapter_id: action.chapter.chapter_id,
            title: action.chapter.title,
            content: action.chapter.content,
        });
    };

    const SORTED_CHAPTERS = content?.chapters
        ? [...content.chapters].sort((a, b) => a.order_index - b.order_index)
        : [];
    const selectedChapter = SORTED_CHAPTERS.find((chapter) => chapter.chapter_id === selectedChapterId)
        ?? SORTED_CHAPTERS[0]
        ?? null;
    const selectedChapterIndex = selectedChapter
        ? SORTED_CHAPTERS.findIndex((chapter) => chapter.chapter_id === selectedChapter.chapter_id)
        : -1;
    const revisionState = content?.revision_state ?? null;
    const canPublish = Boolean(
        content
        && (
            content.status === "draft"
            || (content.status === "published" && revisionState?.has_unpublished_revision)
        ),
    );
    const canArchive = Boolean(
        content
        && content.status !== "archived"
        && bindingImpact
        && bindingImpact.can_archive,
    );
    const allBindings = [
        ...(bindingImpact?.active_bindings ?? []),
        ...(bindingImpact?.working_bindings ?? []),
    ];
    const impactUnitsForOrders = () => allBindings;
    const confirmImpactUnits = confirmAction && "affectedOrders" in confirmAction
        ? impactUnitsForOrders()
        : [];
    const impactDescription = confirmImpactUnits.length
        ? `会影响训练活动：${confirmImpactUnits.map((binding) => binding.activity_title).join("；")}。`
        : "";
    const confirmTitle = confirmAction?.type === "delete-chapter"
        ? "删除学习章节"
        : confirmAction?.type === "reorder-chapter"
          ? "调整章节顺序"
          : confirmAction?.type === "archive"
            ? "归档学习内容"
            : "发布学习内容";
    const confirmDescription = confirmAction?.type === "delete-chapter"
        ? `确定要删除「${confirmAction.chapter.title}」吗？删除后该章节无法恢复。${impactDescription ? ` ${impactDescription} 请确认相关活动仍符合学习目标。` : ""}`
        : confirmAction?.type === "reorder-chapter"
          ? `确定要${confirmAction.direction === "up" ? "上移" : "下移"}当前章节吗？${impactDescription ? ` ${impactDescription} 请确认相关活动仍符合学习目标。` : ""}`
          : confirmAction?.type === "archive"
            ? bindingImpact?.archive_block_reason
                ?? `确定要归档「${content?.title ?? "当前学习内容"}」吗？归档后学员将不能继续访问该内容。`
            : content?.status === "published"
              ? `确定要发布「${content?.title ?? "当前学习内容"}」的待发布修订吗？发布后学员端会读取最新文章内容。`
              : `确定要发布「${content?.title ?? "当前学习内容"}」吗？发布前会再次执行章节与安全门禁检查。`;

    return (
        <div className="space-y-6 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-[var(--duration-tooltip)]">
            <ConfirmDialog
                open={!!confirmAction}
                onOpenChange={(open) => {
                    if (!open) setConfirmAction(null);
                }}
                title={confirmTitle}
                description={confirmDescription}
                confirmText={
                    confirmAction?.type === "delete-chapter"
                        ? "确认删除"
                        : confirmAction?.type === "archive"
                          ? "确认归档"
                          : confirmAction?.type === "reorder-chapter"
                            ? "确认调整"
                            : "确认发布"
                }
                variant={confirmAction?.type === "delete-chapter" ? "danger" : "warning"}
                onConfirm={handleConfirmAction}
                isLoading={chapterAdding || actionLoading}
            />

            <ConfirmDialog
                open={!!editDiscardConfirm}
                onOpenChange={(open) => {
                    if (!open) setEditDiscardConfirm(null);
                }}
                title="未保存的修改"
                description="当前章节有未保存的修改内容，如果放弃修改，所有的更改将会丢失。要放弃修改吗？"
                confirmText="放弃修改"
                cancelText="继续编辑"
                variant="warning"
                onConfirm={handleConfirmDiscard}
            />

            <div className="flex items-center gap-4">
                <Link
                    href="/admin/learning-contents"
                    className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900 transition-colors"
                >
                    <ArrowLeft className="h-4 w-4" />
                    返回列表
                </Link>
            </div>

            {error ? (
                <GlassCard className="p-8 text-center">
                    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-50 text-red-500">
                        <BookOpen className="h-8 w-8" />
                    </div>
                    <h3 className="mb-2 text-lg font-bold text-slate-900">加载失败</h3>
                    <p className="mb-4 text-sm text-slate-500">{error}</p>
                    <Button onClick={() => void loadContent()} className="rounded-full">
                        <RefreshCcw className="mr-2 h-4 w-4" /> 重试
                    </Button>
                </GlassCard>
            ) : null}

            {isLoading && !error ? (
                <GlassCard className="p-8 text-center">
                    <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900" />
                    <p className="text-slate-500">加载中...</p>
                </GlassCard>
            ) : null}

            {content && !isLoading ? (
                <>
                    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                        <div>
                            <h1 className="text-3xl font-black tracking-tight text-slate-900">
                                {content.title}
                            </h1>
                            <p className="mt-1 text-slate-500">
                                {content.summary || "暂无摘要"}
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
                            <span
                                className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${STATUS_COLORS[content.status] || "bg-slate-100 text-slate-700"}`}
                            >
                                {STATUS_LABELS[content.status] || content.status}
                            </span>
                            <span className="text-sm font-medium text-slate-500">v{content.version}</span>
                        </div>
                    </div>

                    <GlassCard className="p-5">
                        <div className="grid gap-4 lg:grid-cols-4">
                            <div className="rounded-xl border border-slate-100 bg-slate-50/70 px-4 py-3">
                                <p className="text-xs font-semibold text-slate-400">当前发布版本</p>
                                <p className="mt-1 text-sm font-bold text-slate-900">
                                    {revisionLabel(revisionState?.active_revision_id, revisionState?.active_revision_no)}
                                </p>
                            </div>
                            <div className="rounded-xl border border-slate-100 bg-slate-50/70 px-4 py-3">
                                <p className="text-xs font-semibold text-slate-400">待发布修订</p>
                                <p className="mt-1 text-sm font-bold text-slate-900">
                                    {revisionState?.has_unpublished_revision
                                        ? revisionLabel(revisionState.working_revision_id, revisionState.working_revision_no)
                                        : "无待发布修订"}
                                </p>
                            </div>
                            <div className="rounded-xl border border-slate-100 bg-slate-50/70 px-4 py-3">
                                <p className="text-xs font-semibold text-slate-400">学员端绑定</p>
                                <p className="mt-1 text-sm font-bold text-slate-900">
                                    {bindingStatusLabel(bindingImpact)}
                                </p>
                            </div>
                            <div className="rounded-xl border border-slate-100 bg-slate-50/70 px-4 py-3">
                                <p className="text-xs font-semibold text-slate-400">当前编辑写入</p>
                                <p className="mt-1 text-sm font-bold text-slate-900">
                                    {revisionState?.edit_target === "working_revision"
                                        ? "待发布修订"
                                        : revisionState?.edit_target === "archived_locked"
                                          ? "已锁定"
                                          : "草稿记录"}
                                </p>
                            </div>
                        </div>
                        {actionNotice ? (
                            <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
                                {actionNotice}
                            </div>
                        ) : null}
                        {bindingImpactError ? (
                            <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                                绑定影响读取失败：{bindingImpactError}
                            </div>
                        ) : null}
                        {!bindingImpact?.can_archive && bindingImpact?.archive_block_reason ? (
                            <div className="mt-4 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                                <p>{bindingImpact.archive_block_reason}</p>
                            </div>
                        ) : null}
                        <div className="mt-4 flex flex-wrap gap-2">
                            <Link href="/admin/newcomer-training/paths" prefetch={false} className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
                                路径配置
                                <ExternalLink className="h-3.5 w-3.5" />
                            </Link>
                            <Link href="/admin/sales-trainer/questions" prefetch={false} className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
                                管理测验题目
                                <ExternalLink className="h-3.5 w-3.5" />
                            </Link>
                        </div>
                    </GlassCard>

                    <div className="grid gap-6 lg:grid-cols-3">
                        <div className="lg:col-span-2 flex flex-col gap-6">
                            <GlassCard className="order-2 p-6">
                                <h2 className="mb-4 text-lg font-bold text-slate-900">元数据</h2>
                                {metaError ? (
                                    <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                        {metaError}
                                    </div>
                                ) : null}
                                <div className="space-y-4">
                                    <div>
                                        <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                            标题
                                        </label>
                                        <input
                                            type="text"
                                            value={title}
                                            onChange={(e) => setTitle(e.target.value)}
                                            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                        />
                                    </div>
                                    <div>
                                        <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                            摘要
                                        </label>
                                        <textarea
                                            value={summary}
                                            onChange={(e) => setSummary(e.target.value)}
                                            rows={3}
                                            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                        />
                                    </div>
                                    <div className="grid gap-4 sm:grid-cols-2">
                                        <div>
                                            <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                                负责人
                                            </label>
                                            <input
                                                type="text"
                                                value={owner}
                                                onChange={(e) => setOwner(e.target.value)}
                                                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                            />
                                        </div>
                                        <div>
                                            <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                                来源
                                            </label>
                                            <select
                                                aria-label="来源"
                                                value={source}
                                                onChange={(e) => setSource(e.target.value)}
                                                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                            >
                                                <option value="manual">手动录入</option>
                                                <option value="imported">批量导入</option>
                                                <option value="generated">系统生成</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="checkbox"
                                            id="safety-flagged"
                                            checked={safetyFlagged}
                                            onChange={(e) => setSafetyFlagged(e.target.checked)}
                                            aria-label="安全标记"
                                            className="h-4 w-4 rounded border-slate-300 text-red-600 focus:ring-red-500"
                                        />
                                        <label
                                            htmlFor="safety-flagged"
                                            className="text-sm font-medium text-slate-700"
                                        >
                                            安全标记
                                        </label>
                                    </div>
                                    <div className="flex gap-2">
                                        <Button
                                            onClick={() => void handleSaveMetadata()}
                                            disabled={metaSaving}
                                            isLoading={metaSaving}
                                            className="rounded-full"
                                        >
                                            保存元数据
                                        </Button>
                                        <Button
                                            variant="outline"
                                            className="rounded-full"
                                            onClick={() => void loadContent()}
                                            disabled={metaSaving}
                                        >
                                            <RefreshCcw className="mr-2 h-4 w-4" />
                                            重置
                                        </Button>
                                    </div>
                                </div>
                            </GlassCard>

                            <GlassCard className="order-1 p-6">
                                <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                                    <div>
                                        <h2 className="text-lg font-bold text-slate-900">
                                            章节与出题 ({SORTED_CHAPTERS.length})
                                        </h2>
                                        <p className="mt-1 text-sm text-slate-500">
                                            左侧选择章节、调整顺序；右侧查看正文并生成本章考题草稿。
                                        </p>
                                    </div>
                                    {selectedChapter ? (
                                        <span className="text-xs font-medium text-slate-400">
                                            当前：第 {selectedChapterIndex + 1} 章
                                        </span>
                                    ) : null}
                                </div>
                                {chapterError ? (
                                    <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                        {chapterError}
                                    </div>
                                ) : null}

                                {SORTED_CHAPTERS.length === 0 ? (
                                    <div className="mb-4 rounded-xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-8 text-center text-sm text-slate-500">
                                        暂无章节。先添加章节，发布门禁和 AI 出题才有内容来源。
                                    </div>
                                ) : (
                                    <div className="mb-5 grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                                        <div className="space-y-3" aria-label="章节目录">
                                            {SORTED_CHAPTERS.map((chapter, index) => {
                                                const isSelected = selectedChapter?.chapter_id === chapter.chapter_id;
                                                const isEditing = editingChapter?.chapter_id === chapter.chapter_id;
                                                return (
                                                    <div
                                                        key={chapter.chapter_id}
                                                        className={`rounded-2xl border p-4 transition-colors ${
                                                            isSelected
                                                                ? "border-slate-300 bg-white shadow-sm"
                                                                : "border-slate-100 bg-slate-50/60 hover:border-slate-200 hover:bg-white"
                                                        }`}
                                                    >
                                                        <button
                                                            type="button"
                                                            onClick={() => handleSelectChapter(chapter)}
                                                            className="block w-full text-left"
                                                            aria-pressed={isSelected}
                                                        >
                                                            <div className="flex items-start gap-3">
                                                                <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-xs font-bold ${
                                                                    isSelected
                                                                        ? "bg-slate-900 text-white"
                                                                        : "bg-white text-slate-500"
                                                                }`}
                                                                >
                                                                    {index + 1}
                                                                </span>
                                                                <div className="min-w-0 flex-1">
                                                                    <div className="flex flex-wrap items-center gap-2">
                                                                        <h3 className="line-clamp-2 text-sm font-semibold text-slate-900">
                                                                            {chapter.title}
                                                                        </h3>
                                                                        {isEditing ? (
                                                                            <span className="rounded-md bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                                                                                编辑中
                                                                            </span>
                                                                        ) : null}
                                                                    </div>
                                                                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
                                                                        {summarizeChapterContent(chapter.content)}
                                                                    </p>
                                                                </div>
                                                            </div>
                                                        </button>
                                                        <div className="mt-3 flex flex-wrap items-center gap-1 pl-11">
                                                            <button
                                                                type="button"
                                                                onClick={() => handleMoveUp(index)}
                                                                disabled={index === 0}
                                                                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:opacity-30"
                                                                title="上移"
                                                            >
                                                                <ChevronUp className="h-4 w-4" />
                                                            </button>
                                                            <button
                                                                type="button"
                                                                onClick={() => handleMoveDown(index)}
                                                                disabled={index === SORTED_CHAPTERS.length - 1}
                                                                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:opacity-30"
                                                                title="下移"
                                                            >
                                                                <ChevronDown className="h-4 w-4" />
                                                            </button>
                                                            {isEditing ? null : (
                                                                <button
                                                                    type="button"
                                                                    onClick={() => handleEditChapter(chapter)}
                                                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-blue-50 hover:text-blue-700"
                                                                    title="编辑"
                                                                >
                                                                    <Edit3 className="h-3.5 w-3.5" />
                                                                </button>
                                                            )}
                                                            <button
                                                                type="button"
                                                                onClick={() => handleDeleteChapterRequest(chapter)}
                                                                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-red-50 hover:text-red-700"
                                                                title="删除"
                                                            >
                                                                <Trash2 className="h-3.5 w-3.5" />
                                                            </button>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>

                                        <div className="rounded-2xl border border-slate-100 bg-white/80 p-4 shadow-sm">
                                            {selectedChapter ? (
                                                editingChapter?.chapter_id === selectedChapter.chapter_id ? (
                                                    <div className="space-y-4">
                                                        <div>
                                                            <p className="text-xs font-semibold text-slate-400">
                                                                编辑当前章节
                                                            </p>
                                                            <h3 className="mt-1 text-base font-bold text-slate-900">
                                                                第 {selectedChapterIndex + 1} 章
                                                            </h3>
                                                        </div>
                                                        <div>
                                                            <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                                                章节标题
                                                            </label>
                                                            <input
                                                                type="text"
                                                                value={editingChapter.title}
                                                                onChange={(e) =>
                                                                    setEditingChapter({
                                                                        ...editingChapter,
                                                                        title: e.target.value,
                                                                    })
                                                                }
                                                                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                                            />
                                                        </div>
                                                        <div>
                                                            <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                                                章节正文
                                                            </label>
                                                            <textarea
                                                                value={editingChapter.content}
                                                                onChange={(e) =>
                                                                    setEditingChapter({
                                                                        ...editingChapter,
                                                                        content: e.target.value,
                                                                    })
                                                                }
                                                                rows={10}
                                                                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm leading-6 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                                            />
                                                        </div>
                                                        <div className="flex flex-wrap gap-2">
                                                            <Button
                                                                size="sm"
                                                                variant="primary"
                                                                onClick={() => void handleSaveEditChapter()}
                                                                disabled={chapterAdding}
                                                                isLoading={chapterAdding}
                                                            >
                                                                保存
                                                            </Button>
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                onClick={handleCancelEdit}
                                                                disabled={chapterAdding}
                                                            >
                                                                取消
                                                            </Button>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className="space-y-4">
                                                        <div>
                                                            <p className="text-xs font-semibold text-slate-400">
                                                                当前章节 · 第 {selectedChapterIndex + 1} 章
                                                            </p>
                                                            <h3 className="mt-1 text-base font-bold text-slate-900">
                                                                {selectedChapter.title}
                                                            </h3>
                                                        </div>
                                                        <div className="max-h-[520px] overflow-auto rounded-xl border border-slate-100 bg-slate-50/70 p-5">
                                                            {selectedChapter.content ? (
                                                                <DeferredLearningContentMarkdownPreview
                                                                    key={selectedChapter.chapter_id}
                                                                    content={selectedChapter.content}
                                                                />
                                                            ) : (
                                                                <p className="text-sm text-slate-500">暂无正文</p>
                                                            )}
                                                        </div>
                                                    </div>
                                                )
                                            ) : null}
                                        </div>
                                    </div>
                                )}

                                <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
                                    <h3 className="mb-3 text-sm font-bold text-slate-700">添加章节</h3>
                                    <div className="space-y-3">
                                        <input
                                            type="text"
                                            value={newChapterTitle}
                                            onChange={(e) => setNewChapterTitle(e.target.value)}
                                            placeholder="章节标题"
                                            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                        />
                                        <textarea
                                            value={newChapterContent}
                                            onChange={(e) => setNewChapterContent(e.target.value)}
                                            placeholder="章节内容"
                                            rows={3}
                                            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                        />
                                        <Button
                                            onClick={() => void handleAddChapter()}
                                            disabled={chapterAdding || !newChapterTitle.trim() || !newChapterContent.trim()}
                                            isLoading={chapterAdding}
                                            className="rounded-full"
                                            size="sm"
                                        >
                                            <Plus className="mr-1.5 h-4 w-4" />
                                            添加章节
                                        </Button>
                                    </div>
                                </div>
                            </GlassCard>
                        </div>

                        <div className="space-y-6">
                            <GlassCard className="p-6">
                                <h2 className="mb-4 text-lg font-bold text-slate-900">操作</h2>
                                {actionError ? (
                                    <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                        {actionError}
                                    </div>
                                ) : null}
                                {publishGateErrors ? (
                                    <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
                                        <p className="mb-2 text-sm font-bold text-amber-800">发布门禁未通过</p>
                                        <ul className="space-y-1">
                                            {publishGateErrors.map((gate) => (
                                                <li
                                                    key={gate.reason_code}
                                                    className="text-xs text-amber-700"
                                                >
                                                    <span className="font-mono">{gate.reason_code}</span>: {gate.message}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                ) : null}
                                <div className="space-y-3">
                                    <Button
                                        onClick={() => setConfirmAction({ type: "publish" })}
                                        disabled={actionLoading || !canPublish}
                                        isLoading={actionLoading}
                                        className="w-full rounded-full"
                                        variant="primary"
                                    >
                                        {revisionState?.publish_label ?? "发布"}
                                    </Button>
                                    <Button
                                        onClick={() => setConfirmAction({ type: "archive" })}
                                        disabled={actionLoading || !canArchive}
                                        isLoading={actionLoading}
                                        className="w-full rounded-full"
                                        variant="outline"
                                    >
                                        归档
                                    </Button>
                                    {!canArchive && content.status !== "archived" ? (
                                        <p className="text-xs leading-5 text-amber-700">
                                            {bindingImpact?.archive_block_reason ?? "正在检查新人训练路径绑定，归档暂不可用。"}
                                        </p>
                                    ) : null}
                                </div>
                            </GlassCard>

                            <GlassCard className="p-6">
                                <h2 className="mb-4 text-lg font-bold text-slate-900">信息</h2>
                                <dl className="space-y-3 text-sm">
                                    <div className="flex justify-between">
                                        <dt className="text-slate-400">ID</dt>
                                        <dd className="font-mono text-xs text-slate-600">
                                            {content.learning_content_id.slice(0, 12)}...
                                        </dd>
                                    </div>
                                    <div className="flex justify-between">
                                        <dt className="text-slate-400">内容哈希</dt>
                                        <dd className="font-mono text-xs text-slate-600">
                                            {content.content_hash
                                                ? content.content_hash.slice(0, 10) + "..."
                                                : "-"}
                                        </dd>
                                    </div>
                                    <div className="flex justify-between">
                                        <dt className="text-slate-400">安全标记</dt>
                                        <dd>
                                            {content.safety_flagged ? (
                                                <span className="inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-600">
                                                    已标记
                                                </span>
                                            ) : (
                                                <span className="text-xs text-slate-400">未标记</span>
                                            )}
                                        </dd>
                                    </div>
                                    <div className="flex justify-between">
                                        <dt className="text-slate-400">创建时间</dt>
                                        <dd className="text-slate-600">
                                            {new Date(content.created_at).toLocaleDateString("zh-CN")}
                                        </dd>
                                    </div>
                                    <div className="flex justify-between">
                                        <dt className="text-slate-400">更新时间</dt>
                                        <dd className="text-slate-600">
                                            {new Date(content.updated_at).toLocaleDateString("zh-CN")}
                                        </dd>
                                    </div>
                                    {content.published_at ? (
                                        <div className="flex justify-between">
                                            <dt className="text-slate-400">发布时间</dt>
                                            <dd className="text-slate-600">
                                                {new Date(content.published_at).toLocaleDateString("zh-CN")}
                                            </dd>
                                        </div>
                                    ) : null}
                                </dl>
                            </GlassCard>
                        </div>
                    </div>
                </>
            ) : null}
        </div>
    );
}
