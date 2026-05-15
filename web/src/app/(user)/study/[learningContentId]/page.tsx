"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { BookOpen, CheckCircle2, RefreshCcw } from "lucide-react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type { LearnerStudyContent, LearnerStudyProgress, LearningChapter } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

function ChapterSidebar({
    chapters,
    completedIds,
    selectedId,
    onSelect,
}: {
    chapters: LearningChapter[];
    completedIds: Set<string>;
    selectedId: string | null;
    onSelect: (id: string) => void;
}) {
    return (
        <nav className="space-y-1" aria-label="章节列表">
            {chapters.map((chapter, index) => {
                const isActive = chapter.chapter_id === selectedId;
                const isCompleted = completedIds.has(chapter.chapter_id);
                return (
                    <button
                        key={chapter.chapter_id}
                        type="button"
                        onClick={() => onSelect(chapter.chapter_id)}
                        className={`w-full cursor-pointer rounded-xl px-4 py-3 text-left text-sm font-medium transition-colors ${
                            isActive
                                ? "bg-blue-50 text-blue-700 border border-blue-200"
                                : "text-slate-700 hover:bg-slate-50 border border-transparent"
                        }`}
                    >
                        <div className="flex items-center gap-2">
                            {isCompleted ? (
                                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                            ) : (
                                <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-400">
                                    {index + 1}
                                </span>
                            )}
                            <span className="truncate">{chapter.title}</span>
                        </div>
                    </button>
                );
            })}
        </nav>
    );
}

export default function StudyPage() {
    const { learningContentId } = useParams<{ learningContentId: string }>();

    const [content, setContent] = useState<LearnerStudyContent | null>(null);
    const [progress, setProgress] = useState<LearnerStudyProgress | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null);
    const [completingId, setCompletingId] = useState<string | null>(null);

    const sortedChapters = content?.chapters
        ? [...content.chapters].sort((a, b) => a.order_index - b.order_index)
        : [];

    const selectedChapter = sortedChapters.find((c) => c.chapter_id === selectedChapterId) ?? null;

    const completedIds = new Set(progress?.completed_chapter_ids ?? []);

    const loadContent = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await api.learnerStudy.getContent(learningContentId);
            setContent(data);
            setProgress(data.progress);
            if (data.chapters.length > 0 && !selectedChapterId) {
                setSelectedChapterId(data.chapters.sort((a, b) => a.order_index - b.order_index)[0].chapter_id);
            }
        } catch (err) {
            setError(getApiErrorMessage(err));
            setContent(null);
            setProgress(null);
        } finally {
            setIsLoading(false);
        }
    }, [learningContentId, selectedChapterId]);

    useEffect(() => {
        void loadContent();
    }, [learningContentId]);

    const handleCompleteChapter = async (chapterId: string) => {
        setCompletingId(chapterId);
        try {
            const result = await api.learnerStudy.completeChapter(learningContentId, chapterId);
            setProgress(result.progress);
        } catch {
            // ignore completion errors — progress stays intact
        } finally {
            setCompletingId(null);
        }
    };

    if (isLoading) {
        return (
            <div className="space-y-6 animate-in fade-in duration-300">
                <GlassCard className="p-8 text-center" role="status" aria-live="polite" aria-busy="true">
                    <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900" />
                    <p className="text-slate-500">加载讲义中...</p>
                </GlassCard>
            </div>
        );
    }

    if (error || content === null) {
        return (
            <div className="space-y-6 animate-in fade-in duration-300">
                <GlassCard className="p-8 text-center">
                    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-50 text-red-500">
                        <BookOpen className="h-8 w-8" />
                    </div>
                    <h3 className="mb-2 text-lg font-bold text-slate-900">加载失败</h3>
                    <p className="mb-4 text-sm text-slate-500">{error ?? "无法读取讲义内容。"}</p>
                    <Button onClick={() => void loadContent()} className="rounded-full">
                        <RefreshCcw className="mr-2 h-4 w-4" /> 重试
                    </Button>
                </GlassCard>
            </div>
        );
    }

    if (sortedChapters.length === 0) {
        return (
            <div className="space-y-6 animate-in fade-in duration-300">
                <EmptyState
                    title="暂无章节"
                    description="该讲义尚未配置章节内容，请联系管理员添加章节。"
                />
            </div>
        );
    }

    const isCompleted = progress?.is_completed ?? false;
    const showExamCTA = progress?.state === "completed";

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-2xl font-black tracking-tight text-slate-900 sm:text-3xl">
                        {content.title}
                    </h1>
                    {content.summary && (
                        <p className="mt-1 text-sm text-slate-500">{content.summary}</p>
                    )}
                </div>
                <div className="flex items-center gap-3">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-600">
                        <BookOpen className="h-3.5 w-3.5" />
                        阅读进度 {progress?.completed_count ?? 0}/{progress?.total_chapters ?? sortedChapters.length}
                    </span>
                    {isCompleted && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-600">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            已完成
                        </span>
                    )}
                </div>
            </div>

            <div className="block lg:hidden">
                <label htmlFor="chapter-select" className="sr-only">
                    选择章节
                </label>
                <select
                    id="chapter-select"
                    value={selectedChapterId ?? ""}
                    onChange={(e) => setSelectedChapterId(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-900 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                    aria-label="选择章节"
                >
                    {sortedChapters.map((chapter, index) => (
                        <option key={chapter.chapter_id} value={chapter.chapter_id}>
                            {completedIds.has(chapter.chapter_id) ? "✓ " : ""}
                            第{index + 1}章 · {chapter.title}
                        </option>
                    ))}
                </select>
            </div>

            <div className="grid gap-6 lg:grid-cols-4">
                <div className="hidden lg:block lg:col-span-1">
                    <GlassCard className="p-4">
                        <h2 className="mb-3 text-sm font-bold text-slate-500 uppercase tracking-wider">章节</h2>
                        <ChapterSidebar
                            chapters={sortedChapters}
                            completedIds={completedIds}
                            selectedId={selectedChapterId}
                            onSelect={setSelectedChapterId}
                        />
                    </GlassCard>
                </div>

                <div className="lg:col-span-3 space-y-6">
                    {selectedChapter ? (
                        <GlassCard className="p-6">
                            <div className="mb-4 flex items-center gap-3">
                                <h2 className="text-xl font-bold text-slate-900">{selectedChapter.title}</h2>
                                {completedIds.has(selectedChapter.chapter_id) && (
                                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-600">
                                        <CheckCircle2 className="h-3 w-3" />
                                        已完成
                                    </span>
                                )}
                            </div>
                            <div className="max-w-none whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                                {selectedChapter.content}
                            </div>

                            <div className="mt-6 flex items-center gap-3 border-t border-slate-100 pt-4">
                                {completedIds.has(selectedChapter.chapter_id) ? (
                                    <span className="text-sm text-slate-400">本章已完成</span>
                                ) : (
                                    <Button
                                        onClick={() => void handleCompleteChapter(selectedChapter.chapter_id)}
                                        disabled={completingId === selectedChapter.chapter_id}
                                        isLoading={completingId === selectedChapter.chapter_id}
                                        className="rounded-full"
                                    >
                                        <CheckCircle2 className="mr-2 h-4 w-4" />
                                        标记完成
                                    </Button>
                                )}
                            </div>
                        </GlassCard>
                    ) : (
                        <GlassCard className="p-8 text-center">
                            <p className="text-slate-500">请从章节列表中选择一章开始阅读。</p>
                        </GlassCard>
                    )}

                    {showExamCTA && (
                        <GlassCard className="p-6 border border-emerald-100 bg-emerald-50/80">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                                <div>
                                    <h3 className="text-lg font-bold text-emerald-800">学习完成</h3>
                                    <p className="text-sm text-emerald-600">
                                        你已阅读完所有章节。考试功能即将上线，敬请期待。
                                    </p>
                                </div>
                                <Button disabled className="rounded-full cursor-not-allowed opacity-60">
                                    即将上线
                                </Button>
                            </div>
                        </GlassCard>
                    )}
                </div>
            </div>
        </div>
    );
}
