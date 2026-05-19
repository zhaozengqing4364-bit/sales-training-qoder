"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import React from "react";
import {
    ArrowLeft,
    BookOpen,
    ChevronUp,
    ChevronDown,
    Edit3,
    Plus,
    RefreshCcw,
    Trash2,
} from "lucide-react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type { LearningChapter, LearningContent, QuestionCategory } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { debug } from "@/lib/debug";
import { QuestionGenerationPanel } from "./question-generation-panel";

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

export default function AdminLearningContentDetailPage() {
    const { contentId } = useParams<{ contentId: string }>();

    const [content, setContent] = useState<LearningContent | null>(null);
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

    const [actionLoading, setActionLoading] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);
    const [publishGateErrors, setPublishGateErrors] = useState<GateResult[] | null>(null);
    const [confirmAction, setConfirmAction] = useState<
        | { type: "delete-chapter"; chapter: LearningChapter }
        | { type: "publish" }
        | { type: "archive" }
        | null
    >(null);

    const [editDiscardConfirm, setEditDiscardConfirm] = useState<
        | { type: "cancel" }
        | { type: "switch"; chapter: LearningChapter }
        | null
    >(null);

    const [categories, setCategories] = useState<QuestionCategory[]>([]);

    const loadContent = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const [data, catsResult] = await Promise.all([
                api.learningContents.get(contentId),
                api.testBank.listCategories(),
            ]);
            setContent(data);
            setTitle(data.title);
            setSummary(data.summary ?? "");
            setOwner(data.owner ?? "");
            setSource(data.source ?? "");
            setSafetyFlagged(data.safety_flagged);
            setActionError(null);
            setPublishGateErrors(null);
            setCategories(catsResult.items);
        } catch (err) {
            debug.error("Failed to load learning content:", err);
            setError(getApiErrorMessage(err));
            setContent(null);
        } finally {
            setIsLoading(false);
        }
    }, [contentId]);

    useEffect(() => {
        void loadContent();
    }, [loadContent]);

    const handleSaveMetadata = async () => {
        setMetaSaving(true);
        setMetaError(null);
        try {
            await api.learningContents.update(contentId, {
                title: title.trim(),
                summary: summary.trim() || null,
                owner: owner.trim() || null,
                source: source.trim() || null,
                safety_flagged: safetyFlagged,
            });
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
        try {
            await api.learningContents.addChapter(contentId, {
                title: newChapterTitle.trim(),
                content: newChapterContent.trim(),
            });
            setNewChapterTitle("");
            setNewChapterContent("");
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
        try {
            await api.learningContents.updateChapter(contentId, editingChapter.chapter_id, {
                title: editingChapter.title.trim(),
                content: editingChapter.content.trim(),
            });
            setEditingChapter(null);
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

    const handleDeleteChapter = async (chapterId: string) => {
        setChapterAdding(true);
        setChapterError(null);
        try {
            await api.learningContents.deleteChapter(contentId, chapterId);
            await loadContent();
        } catch (err) {
            setChapterError(getApiErrorMessage(err));
        } finally {
            setChapterAdding(false);
        }
    };

    const handleMoveUp = async (index: number) => {
        if (!content || index <= 0) return;
        const chapters = [...content.chapters];
        const newOrder = chapters.map((c) => c.chapter_id);
        const temp = newOrder[index];
        newOrder[index] = newOrder[index - 1];
        newOrder[index - 1] = temp;
        try {
            await api.learningContents.reorderChapters(contentId, newOrder);
            await loadContent();
        } catch (err) {
            setChapterError(getApiErrorMessage(err));
        }
    };

    const handleMoveDown = async (index: number) => {
        if (!content || index >= content.chapters.length - 1) return;
        const chapters = [...content.chapters];
        const newOrder = chapters.map((c) => c.chapter_id);
        const temp = newOrder[index];
        newOrder[index] = newOrder[index + 1];
        newOrder[index + 1] = temp;
        try {
            await api.learningContents.reorderChapters(contentId, newOrder);
            await loadContent();
        } catch (err) {
            setChapterError(getApiErrorMessage(err));
        }
    };

    const handlePublish = async () => {
        setActionLoading(true);
        setActionError(null);
        setPublishGateErrors(null);
        try {
            await api.learningContents.publish(contentId);
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
        setPublishGateErrors(null);
        try {
            await api.learningContents.archive(contentId);
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
        // switch to another chapter after discarding
        setEditingChapter({
            chapter_id: action.chapter.chapter_id,
            title: action.chapter.title,
            content: action.chapter.content,
        });
    };

    const confirmTitle = confirmAction?.type === "delete-chapter"
        ? "删除学习章节"
        : confirmAction?.type === "archive"
          ? "归档学习内容"
          : "发布学习内容";
    const confirmDescription = confirmAction?.type === "delete-chapter"
        ? `确定要删除「${confirmAction.chapter.title}」吗？删除后该章节无法恢复。`
        : confirmAction?.type === "archive"
          ? `确定要归档「${content?.title ?? "当前学习内容"}」吗？归档后学员将不能继续访问该内容。`
          : `确定要发布「${content?.title ?? "当前学习内容"}」吗？发布前会再次执行章节与安全门禁检查。`;

    const SORTED_CHAPTERS = content?.chapters
        ? [...content.chapters].sort((a, b) => a.order_index - b.order_index)
        : [];

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <ConfirmDialog
                open={!!confirmAction}
                onOpenChange={(open) => {
                    if (!open) setConfirmAction(null);
                }}
                title={confirmTitle}
                description={confirmDescription}
                confirmText={confirmAction?.type === "delete-chapter" ? "确认删除" : confirmAction?.type === "archive" ? "确认归档" : "确认发布"}
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

                    <div className="grid gap-6 lg:grid-cols-3">
                        <div className="lg:col-span-2 space-y-6">
                            <GlassCard className="p-6">
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

                            <GlassCard className="p-6">
                                <h2 className="mb-4 text-lg font-bold text-slate-900">
                                    章节管理 ({SORTED_CHAPTERS.length})
                                </h2>
                                {chapterError ? (
                                    <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                        {chapterError}
                                    </div>
                                ) : null}

                                {SORTED_CHAPTERS.length === 0 ? (
                                    <div className="py-4 text-center text-sm text-slate-500">暂无章节</div>
                                ) : (
                                    <div className="mb-4 overflow-x-auto">
                                        <table className="w-full text-left text-sm">
                                            <thead className="border-b border-slate-100 bg-slate-50/50 text-xs font-bold uppercase tracking-wider text-slate-400">
                                                <tr>
                                                    <th className="px-3 py-2 w-12">#</th>
                                                    <th className="px-3 py-2">标题</th>
                                                    <th className="px-3 py-2">内容</th>
                                                    <th className="px-3 py-2 w-32">操作</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-slate-100">
                                                {SORTED_CHAPTERS.map((chapter, index) => (
                                                    <React.Fragment key={chapter.chapter_id}>
                                                    <tr
                                                        className="transition-colors hover:bg-slate-50/50"
                                                    >
                                                        <td className="px-3 py-3 text-slate-400">
                                                            {index + 1}
                                                        </td>
                                                        <td className="px-3 py-3">
                                                            {editingChapter?.chapter_id === chapter.chapter_id ? (
                                                                <input
                                                                    type="text"
                                                                    value={editingChapter.title}
                                                                    onChange={(e) =>
                                                                        setEditingChapter({
                                                                            ...editingChapter,
                                                                            title: e.target.value,
                                                                        })
                                                                    }
                                                                    className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                                                />
                                                            ) : (
                                                                <span className="font-medium text-slate-900">
                                                                    {chapter.title}
                                                                </span>
                                                            )}
                                                        </td>
                                                        <td className="max-w-xs truncate px-3 py-3 text-slate-500">
                                                            {editingChapter?.chapter_id === chapter.chapter_id ? (
                                                                <textarea
                                                                    value={editingChapter.content}
                                                                    onChange={(e) =>
                                                                        setEditingChapter({
                                                                            ...editingChapter,
                                                                            content: e.target.value,
                                                                        })
                                                                    }
                                                                    rows={2}
                                                                    className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                                                />
                                                            ) : (
                                                                chapter.content.length > 60
                                                                    ? chapter.content.slice(0, 60) + "..."
                                                                    : chapter.content
                                                            )}
                                                        </td>
                                                        <td className="px-3 py-3">
                                                            <div className="flex items-center gap-1">
                                                                {editingChapter?.chapter_id === chapter.chapter_id ? (
                                                                    <>
                                                                        <Button
                                                                            size="sm"
                                                                            variant="primary"
                                                                            onClick={() => void handleSaveEditChapter()}
                                                                        >
                                                                            保存
                                                                        </Button>
                                                                        <Button
                                                                            size="sm"
                                                                            variant="ghost"
                                                                            onClick={handleCancelEdit}
                                                                        >
                                                                            取消
                                                                        </Button>
                                                                    </>
                                                                ) : (
                                                                    <>
                                                                        <button
                                                                            type="button"
                                                                            onClick={() => handleMoveUp(index)}
                                                                            disabled={index === 0}
                                                                            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-30"
                                                                            title="上移"
                                                                        >
                                                                            <ChevronUp className="h-4 w-4" />
                                                                        </button>
                                                                        <button
                                                                            type="button"
                                                                            onClick={() => handleMoveDown(index)}
                                                                            disabled={index === SORTED_CHAPTERS.length - 1}
                                                                            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-30"
                                                                            title="下移"
                                                                        >
                                                                            <ChevronDown className="h-4 w-4" />
                                                                        </button>
                                                                        <button
                                                                            type="button"
                                                                            onClick={() => handleEditChapter(chapter)}
                                                                            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-blue-50 hover:text-blue-600"
                                                                            title="编辑"
                                                                        >
                                                                            <Edit3 className="h-3.5 w-3.5" />
                                                                        </button>
                                                                        <button
                                                                            type="button"
                                                                            onClick={() => setConfirmAction({ type: "delete-chapter", chapter })}
                                                                            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-600"
                                                                            title="删除"
                                                                        >
                                                                            <Trash2 className="h-3.5 w-3.5" />
                                                                        </button>
                                                                    </>
                                                                )}
                                                            </div>
                                                        </td>
                                                    </tr>
                                                    {!editingChapter || editingChapter.chapter_id !== chapter.chapter_id ? (
                                                        <tr>
                                                            <td colSpan={4} className="px-3 py-2">
                                                                <QuestionGenerationPanel
                                                                    learningContentId={content.learning_content_id}
                                                                    chapterId={chapter.chapter_id}
                                                                    categories={categories}
                                                                />
                                                            </td>
                                                        </tr>
                                                    ) : null}
                                                    </React.Fragment>
                                                ))}
                                            </tbody>
                                        </table>
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
                                        disabled={actionLoading || content.status === "published"}
                                        isLoading={actionLoading}
                                        className="w-full rounded-full"
                                        variant="primary"
                                    >
                                        发布
                                    </Button>
                                    <Button
                                        onClick={() => setConfirmAction({ type: "archive" })}
                                        disabled={actionLoading || content.status === "archived"}
                                        isLoading={actionLoading}
                                        className="w-full rounded-full"
                                        variant="outline"
                                    >
                                        归档
                                    </Button>
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
