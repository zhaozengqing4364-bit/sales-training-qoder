"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { ArrowLeft, ArrowRight, CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api } from "@/lib/api/client";
import type { NewcomerArticle, NewcomerArticleChapter, SalesTrainerUnit } from "@/lib/api/types";

import {
    BUSINESS_SKILLS_MODULE_KEY,
    businessSkillsArticleErrorMessage,
    businessSkillsExamHref,
    chapterDisplayLabel,
    learningContentIdFromUnit,
    readBusinessSkillsCompletedChapterIds,
    resolveBusinessSkillsUnit,
    saveBusinessSkillsCompletedChapterIds,
} from "./config";

function sortChapters(chapters: readonly NewcomerArticleChapter[]): NewcomerArticleChapter[] {
    return [...chapters].sort((left, right) => left.order_index - right.order_index);
}

function ChapterList({
    chapters,
    completedIds,
    selectedId,
    onSelect,
}: {
    readonly chapters: readonly NewcomerArticleChapter[];
    readonly completedIds: ReadonlySet<string>;
    readonly selectedId: string | null;
    readonly onSelect: (chapterId: string) => void;
}) {
    return (
        <nav className="space-y-2" aria-label="商务技巧章节">
            {chapters.map((chapter, index) => {
                const isSelected = selectedId === chapter.chapter_id;
                const isCompleted = completedIds.has(chapter.chapter_id);
                return (
                    <button
                        key={chapter.chapter_id}
                        type="button"
                        onClick={() => onSelect(chapter.chapter_id)}
                        className={`w-full rounded-2xl border px-4 py-3 text-left transition-colors ${
                            isSelected
                                ? "border-slate-900 bg-slate-900 text-white"
                                : "border-slate-100 bg-white text-slate-700 hover:border-slate-300"
                        }`}
                    >
                        <span className="flex items-center gap-2 text-sm font-bold">
                            {isCompleted ? <CheckCircle2 className="h-4 w-4" /> : null}
                            {chapterDisplayLabel(index)} {chapter.title}
                        </span>
                    </button>
                );
            })}
        </nav>
    );
}

export default function BusinessSkillsPage() {
    const searchParams = useSearchParams();
    const unitId = searchParams.get("unitId");
    const [units, setUnits] = useState<SalesTrainerUnit[]>([]);
    const [article, setArticle] = useState<NewcomerArticle | null>(null);
    const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null);
    const [completedChapterIds, setCompletedChapterIds] = useState<readonly string[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const selectedUnit = useMemo(() => resolveBusinessSkillsUnit(units, unitId), [unitId, units]);
    const examHref = businessSkillsExamHref(selectedUnit?.unit_id ?? unitId);
    const sortedChapters = useMemo(
        () => article ? sortChapters(article.chapters) : [],
        [article],
    );
    const selectedChapter = sortedChapters.find((chapter) => chapter.chapter_id === selectedChapterId)
        ?? sortedChapters[0]
        ?? null;
    const currentCompletedIds = useMemo(
        () => {
            const currentChapterIds = new Set(sortedChapters.map((chapter) => chapter.chapter_id));
            return new Set(completedChapterIds.filter((chapterId) => currentChapterIds.has(chapterId)));
        },
        [completedChapterIds, sortedChapters],
    );
    const allChaptersCompleted = sortedChapters.length > 0
        && sortedChapters.every((chapter) => currentCompletedIds.has(chapter.chapter_id));

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        setArticle(null);
        try {
            const unitResponse = await api.salesTrainer.listUnits();
            const nextSelectedUnit = resolveBusinessSkillsUnit(unitResponse.items, unitId);
            const learningContentId = learningContentIdFromUnit(nextSelectedUnit);
            const nextArticle = await api.newcomerTraining.getModuleArticle(
                BUSINESS_SKILLS_MODULE_KEY,
                learningContentId ? { learning_content_id: learningContentId } : undefined,
            );
            const nextChapters = sortChapters(nextArticle.chapters);
            setUnits(unitResponse.items);
            setArticle(nextArticle);
            setCompletedChapterIds(readBusinessSkillsCompletedChapterIds(nextArticle.learning_content_id));
            setSelectedChapterId(nextChapters[0]?.chapter_id ?? null);
        } catch (loadError) {
            setError(businessSkillsArticleErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, [unitId]);

    useEffect(() => {
        void load();
    }, [load]);

    function completeCurrentChapter(): void {
        if (!article || !selectedChapter) {
            return;
        }
        const nextCompletedIds = sortedChapters
            .filter((chapter) => currentCompletedIds.has(chapter.chapter_id) || chapter.chapter_id === selectedChapter.chapter_id)
            .map((chapter) => chapter.chapter_id);
        setCompletedChapterIds(nextCompletedIds);
        saveBusinessSkillsCompletedChapterIds(article.learning_content_id, nextCompletedIds);
        const selectedIndex = sortedChapters.findIndex((chapter) => chapter.chapter_id === selectedChapter.chapter_id);
        const nextChapter = selectedIndex >= 0 ? sortedChapters[selectedIndex + 1] : undefined;
        if (nextChapter) {
            setSelectedChapterId(nextChapter.chapter_id);
        }
    }

    return (
        <div className="space-y-6 pb-20">
            <Link href="/sales-trainer" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900">
                <ArrowLeft className="h-4 w-4" />
                返回新人训练路径
            </Link>

            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">商务技巧学习</h1>
                    <p className="mt-1 text-sm text-slate-500">先按章节完成学习，再进入商务技巧考试。</p>
                </div>
            </div>

            {error ? (
                <GlassCard className="space-y-2 border-red-100 bg-red-50 p-4 text-sm text-red-700">
                    <p className="font-bold">商务技巧学习内容暂不可用</p>
                    <p>{error}</p>
                </GlassCard>
            ) : null}

            {isLoading ? (
                <div className="h-64 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
            ) : article && selectedChapter ? (
                <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
                    <GlassCard className="p-4">
                        <p className="mb-3 text-xs font-bold uppercase text-slate-400">
                            {currentCompletedIds.size}/{sortedChapters.length} 已完成
                        </p>
                        <ChapterList
                            chapters={sortedChapters}
                            completedIds={currentCompletedIds}
                            selectedId={selectedChapter.chapter_id}
                            onSelect={setSelectedChapterId}
                        />
                    </GlassCard>
                    <GlassCard className="p-6 md:p-8">
                        <article className="mx-auto max-w-3xl space-y-6">
                            <div>
                                <p className="text-sm font-bold text-slate-400">{article.title}</p>
                                <h2 className="mt-1 text-2xl font-black text-slate-900">{selectedChapter.title}</h2>
                            </div>
                            <div className="prose prose-slate max-w-none prose-img:rounded-2xl prose-img:border prose-img:border-slate-200 prose-img:shadow-sm">
                                <ReactMarkdown>{selectedChapter.content || "暂无文章内容。"}</ReactMarkdown>
                            </div>
                            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-6">
                                <Button className="rounded-full bg-slate-900 text-white" onClick={completeCurrentChapter}>
                                    完成本节
                                </Button>
                                {allChaptersCompleted ? (
                                    <Button asChild className="rounded-full bg-slate-900 text-white">
                                        <Link href={examHref}>
                                            完成学习，进入考试
                                            <ArrowRight className="ml-2 h-4 w-4" />
                                        </Link>
                                    </Button>
                                ) : (
                                    <p className="text-sm text-slate-500">完成全部章节后开放考试入口。</p>
                                )}
                            </div>
                        </article>
                    </GlassCard>
                </div>
            ) : error ? null : (
                <GlassCard className="p-6 text-sm text-slate-500">当前文章没有章节，请管理员添加学习章节。</GlassCard>
            )}
        </div>
    );
}
