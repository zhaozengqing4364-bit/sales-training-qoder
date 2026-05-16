"use client";

import { useState } from "react";
import { Sparkles, Send, X } from "lucide-react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type { QuestionCategory, QuestionGenerationDraft } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { debug } from "@/lib/debug";

interface QuestionGenerationPanelProps {
    learningContentId: string;
    chapterId: string;
    categories: QuestionCategory[];
}

function mapPreviewError(error: unknown): string {
    const msg = getApiErrorMessage(error);
    if (msg.includes("QUESTION_GENERATION_UNSAFE_CONTENT")) {
        return "内容包含疑似注入指令，未生成。";
    }
    if (msg.includes("QUESTION_GENERATION_FAILED")) {
        return "考题生成失败，请稍后重试。";
    }
    return msg;
}

export function QuestionGenerationPanel({
    learningContentId,
    chapterId,
    categories,
}: QuestionGenerationPanelProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [drafts, setDrafts] = useState<QuestionGenerationDraft[]>([]);
    const [categoryId, setCategoryId] = useState("");
    const [isSaving, setIsSaving] = useState(false);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [savedCount, setSavedCount] = useState<number | null>(null);

    const handlePreview = async () => {
        setIsOpen(true);
        setIsLoading(true);
        setError(null);
        setDrafts([]);
        setSaveError(null);
        setSavedCount(null);
        try {
            const result = await api.testBank.previewQuestionGeneration({
                learning_content_id: learningContentId,
                chapter_id: chapterId,
            });
            setDrafts(result.drafts);
            if (result.drafts.length === 0) {
                setError("未生成可用考题，请检查章节内容。");
            }
        } catch (err) {
            debug.error("Preview generation failed:", err);
            setError(mapPreviewError(err));
        } finally {
            setIsLoading(false);
        }
    };

    const handleUpdateDraft = (
        index: number,
        field: keyof QuestionGenerationDraft,
        value: unknown,
    ) => {
        setDrafts((prev) =>
            prev.map((d, i) => (i === index ? { ...d, [field]: value } : d)),
        );
    };

    const handleUpdateDraftArrayField = (
        index: number,
        field: "scoring_dimensions" | "tags",
        value: string,
    ) => {
        const items = value
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
        handleUpdateDraft(index, field, items);
    };

    const handleUpdateScoringCriteria = (index: number, value: string) => {
        try {
            const parsed = JSON.parse(value);
            if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
                handleUpdateDraft(index, "scoring_criteria", parsed);
            }
        } catch {
            // ignore invalid JSON
        }
    };

    const handleConfirm = async () => {
        if (!categoryId || drafts.length === 0) return;
        setIsSaving(true);
        setSaveError(null);
        try {
            const result = await api.testBank.confirmQuestionGeneration({
                category_id: categoryId,
                drafts,
            });
            setSavedCount(result.total);
            setDrafts([]);
        } catch (err) {
            debug.error("Confirm generation failed:", err);
            setSaveError(`保存失败: ${getApiErrorMessage(err)}`);
        } finally {
            setIsSaving(false);
        }
    };

    if (!isOpen) {
        return (
            <Button
                variant="outline"
                size="sm"
                className="rounded-full"
                onClick={() => void handlePreview()}
                disabled={isLoading}
            >
                <Sparkles className="mr-1 h-3.5 w-3.5" />
                AI 生成考题
            </Button>
        );
    }

    return (
        <div className="space-y-4">
            {isLoading ? (
                <GlassCard className="p-6 text-center">
                    <div className="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900" />
                    <p className="text-sm text-slate-500">生成中...</p>
                </GlassCard>
            ) : null}

            {error && !isLoading ? (
                <GlassCard className="p-4">
                    <div className="flex items-start justify-between">
                        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                            {error}
                        </div>
                        <button
                            type="button"
                            onClick={() => setIsOpen(false)}
                            className="ml-2 inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>
                </GlassCard>
            ) : null}

            {savedCount !== null ? (
                <GlassCard className="p-4">
                    <div className="flex items-start justify-between">
                        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                            已保存 {savedCount} 道题目到试题库。
                        </div>
                        <button
                            type="button"
                            onClick={() => setIsOpen(false)}
                            className="ml-2 inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>
                </GlassCard>
            ) : null}

            {!isLoading && drafts.length > 0 && savedCount === null ? (
                <>
                    <div className="flex items-center justify-between">
                        <h3 className="text-sm font-bold text-slate-700">
                            考题草稿 ({drafts.length})
                        </h3>
                        <button
                            type="button"
                            onClick={() => setIsOpen(false)}
                            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>

                    {drafts.map((draft, index) => (
                        <GlassCard key={index} className="space-y-3 p-4">
                            <div>
                                <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                    标题
                                </label>
                                <input
                                    type="text"
                                    value={draft.title}
                                    onChange={(e) => handleUpdateDraft(index, "title", e.target.value)}
                                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                />
                            </div>
                            <div>
                                <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                    题干
                                </label>
                                <textarea
                                    value={draft.stem}
                                    onChange={(e) => handleUpdateDraft(index, "stem", e.target.value)}
                                    rows={2}
                                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                />
                            </div>
                            <div>
                                <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                    参考答案
                                </label>
                                <textarea
                                    value={draft.reference_answer}
                                    onChange={(e) =>
                                        handleUpdateDraft(index, "reference_answer", e.target.value)
                                    }
                                    rows={2}
                                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                />
                            </div>
                            <div className="grid gap-3 sm:grid-cols-2">
                                <div>
                                    <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                        评分维度 (逗号分隔)
                                    </label>
                                    <input
                                        type="text"
                                        value={draft.scoring_dimensions.join(",")}
                                        onChange={(e) =>
                                            handleUpdateDraftArrayField(
                                                index,
                                                "scoring_dimensions",
                                                e.target.value,
                                            )
                                        }
                                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                    />
                                </div>
                                <div>
                                    <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                        标签 (逗号分隔)
                                    </label>
                                    <input
                                        type="text"
                                        value={draft.tags.join(",")}
                                        onChange={(e) =>
                                            handleUpdateDraftArrayField(index, "tags", e.target.value)
                                        }
                                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                    评分标准 (JSON)
                                </label>
                                <textarea
                                    value={JSON.stringify(draft.scoring_criteria, null, 2)}
                                    onChange={(e) =>
                                        handleUpdateScoringCriteria(index, e.target.value)
                                    }
                                    rows={3}
                                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                />
                            </div>
                            <div>
                                <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                    难度
                                </label>
                                <select
                                    value={draft.difficulty}
                                    onChange={(e) =>
                                        handleUpdateDraft(index, "difficulty", e.target.value)
                                    }
                                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                                >
                                    <option value="easy">简单</option>
                                    <option value="medium">中等</option>
                                    <option value="hard">困难</option>
                                </select>
                            </div>
                        </GlassCard>
                    ))}

                    {saveError ? (
                        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                            {saveError}
                        </div>
                    ) : null}

                    <GlassCard className="flex items-end gap-4 p-4">
                        <div className="flex-1">
                            <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                                保存到分类
                            </label>
                            <select
                                value={categoryId}
                                onChange={(e) => setCategoryId(e.target.value)}
                                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                            >
                                <option value="">请选择分类</option>
                                {categories.map((c) => (
                                    <option key={c.category_id} value={c.category_id}>
                                        {c.name}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <Button
                            onClick={() => void handleConfirm()}
                            disabled={!categoryId || drafts.length === 0 || isSaving}
                            isLoading={isSaving}
                            className="rounded-full"
                        >
                            <Send className="mr-1.5 h-4 w-4" />
                            确认保存到试题库
                        </Button>
                    </GlassCard>
                </>
            ) : null}
        </div>
    );
}
