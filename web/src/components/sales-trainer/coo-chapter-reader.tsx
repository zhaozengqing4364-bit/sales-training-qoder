"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowLeft, ArrowRight, BookOpen, CheckCircle2 } from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { LearnerStudyProgress, LearningChapter } from "@/lib/api/types";
import {
    buildLearnHref,
    DEFAULT_SALES_TRAINER_RETURN,
    readLearnReturn,
} from "@/lib/sales-trainer/coo-learn-navigation";
import { buildHubLearnHref } from "@/lib/sales-trainer/hub-chapters";

const markdownComponents = {
    h1: ({ children }: { children?: ReactNode }) => (
        <h1 className="mb-4 mt-6 text-2xl font-black text-slate-900 first:mt-0">{children}</h1>
    ),
    h2: ({ children }: { children?: ReactNode }) => (
        <h2 className="mb-3 mt-5 text-xl font-bold text-slate-900 first:mt-0">{children}</h2>
    ),
    h3: ({ children }: { children?: ReactNode }) => (
        <h3 className="mb-2 mt-4 text-lg font-bold text-slate-900 first:mt-0">{children}</h3>
    ),
    p: ({ children }: { children?: ReactNode }) => (
        <p className="mb-3 text-sm leading-relaxed text-slate-700 last:mb-0">{children}</p>
    ),
    ul: ({ children }: { children?: ReactNode }) => (
        <ul className="mb-3 list-disc space-y-1 pl-5 text-sm text-slate-700">{children}</ul>
    ),
    ol: ({ children }: { children?: ReactNode }) => (
        <ol className="mb-3 list-decimal space-y-1 pl-5 text-sm text-slate-700">{children}</ol>
    ),
    li: ({ children }: { children?: ReactNode }) => (
        <li className="leading-relaxed">{children}</li>
    ),
    strong: ({ children }: { children?: ReactNode }) => (
        <strong className="font-semibold text-slate-900">{children}</strong>
    ),
    blockquote: ({ children }: { children?: ReactNode }) => (
        <blockquote className="mb-3 border-l-4 border-slate-200 pl-4 text-sm italic text-slate-600">
            {children}
        </blockquote>
    ),
    code: ({ children }: { children?: ReactNode }) => (
        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800">{children}</code>
    ),
    pre: ({ children }: { children?: ReactNode }) => (
        <pre className="mb-3 overflow-x-auto rounded-xl bg-slate-900 p-4 text-xs text-slate-100">{children}</pre>
    ),
    a: ({ href, children }: { href?: string; children?: ReactNode }) => (
        <a href={href} className="font-medium text-blue-600 underline underline-offset-2 hover:text-blue-800">
            {children}
        </a>
    ),
};

export interface CooChapterReaderProps {
    contentId: string;
    contentTitle: string;
    contentSummary: string | null;
    chapter: LearningChapter;
    progress: LearnerStudyProgress;
    pathTitle: string;
    levelTitle: string;
    chapterIndex: number;
    totalChapters: number;
    unitId: string;
    returnTo: string;
    prevUnitId: string | null;
    nextUnitId: string | null;
    hubNavigation?: boolean;
    onProgressUpdated: (progress: LearnerStudyProgress) => void;
}

export function CooChapterReader({
    contentId,
    contentTitle,
    contentSummary,
    chapter,
    progress,
    pathTitle,
    levelTitle,
    chapterIndex,
    totalChapters,
    unitId,
    returnTo,
    prevUnitId,
    nextUnitId,
    hubNavigation = false,
    onProgressUpdated,
}: CooChapterReaderProps) {
    const router = useRouter();
    const chapterLearnHref = (targetUnitId: string) => (
        hubNavigation ? buildHubLearnHref(targetUnitId) : buildLearnHref(targetUnitId, returnTo)
    );
    const [completeError, setCompleteError] = useState<string | null>(null);
    const [isCompleting, setIsCompleting] = useState(false);

    const completedIds = new Set(progress.completed_chapter_ids ?? []);
    const isChapterCompleted = completedIds.has(chapter.chapter_id);
    const backHref = readLearnReturn(returnTo);

    async function handleCompleteChapter() {
        setIsCompleting(true);
        setCompleteError(null);
        try {
            const result = await api.learnerStudy.completeChapter(contentId, chapter.chapter_id);
            onProgressUpdated(result.progress);
        } catch (err) {
            setCompleteError(`标记完成失败：${getApiErrorMessage(err)}`);
        } finally {
            setIsCompleting(false);
        }
    }

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <Button
                variant="ghost"
                className="w-fit gap-2 pl-0 text-slate-500 hover:bg-transparent hover:text-slate-900"
                onClick={() => router.push(backHref)}
            >
                <ArrowLeft className="h-4 w-4" />
                返回
            </Button>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{pathTitle}</p>
                    <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-900 sm:text-3xl">
                        {contentTitle}
                    </h1>
                    {contentSummary ? (
                        <p className="mt-1 text-sm text-slate-500">{contentSummary}</p>
                    ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <Badge className="bg-slate-100 text-slate-700">{levelTitle}</Badge>
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-600">
                        <BookOpen className="h-3.5 w-3.5" />
                        第 {chapterIndex}/{totalChapters} 章
                    </span>
                    {isChapterCompleted ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-600">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            已读
                        </span>
                    ) : null}
                </div>
            </div>

            <GlassCard className="p-6">
                <div className="mb-4 flex flex-wrap items-center gap-2">
                    <h2 className="text-xl font-bold text-slate-900">{chapter.title}</h2>
                    {isChapterCompleted ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-600">
                            <CheckCircle2 className="h-3 w-3" />
                            已完成
                        </span>
                    ) : null}
                </div>

                <div className="max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                        {chapter.content}
                    </ReactMarkdown>
                </div>

                {completeError ? (
                    <div
                        role="alert"
                        className="mt-4 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700"
                    >
                        {completeError}
                    </div>
                ) : null}

                <div className="mt-6 border-t border-slate-100 pt-4">
                    <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                        <div className="flex flex-wrap items-center gap-2">
                            <Button
                                variant="outline"
                                onClick={() => router.push(backHref)}
                                className="rounded-full"
                            >
                                <ArrowLeft className="mr-2 h-4 w-4" />
                                返回
                            </Button>
                            {prevUnitId ? (
                                <Link href={chapterLearnHref(prevUnitId)}>
                                    <Button variant="secondary" className="rounded-full">
                                        <ArrowLeft className="mr-2 h-4 w-4" />
                                        上一章
                                    </Button>
                                </Link>
                            ) : null}
                            {nextUnitId ? (
                                <Link href={chapterLearnHref(nextUnitId)}>
                                    <Button variant="secondary" className="rounded-full">
                                        下一章
                                        <ArrowRight className="ml-2 h-4 w-4" />
                                    </Button>
                                </Link>
                            ) : null}
                        </div>
                        <div className="flex flex-wrap items-center gap-2 xl:justify-end">
                            {isChapterCompleted ? (
                                <span className="rounded-full bg-slate-50 px-4 py-2 text-sm text-slate-500">
                                    本章已标记已读
                                </span>
                            ) : (
                                <Button
                                    variant="outline"
                                    onClick={() => void handleCompleteChapter()}
                                    disabled={isCompleting}
                                    isLoading={isCompleting}
                                    className="rounded-full"
                                >
                                    <CheckCircle2 className="mr-2 h-4 w-4" />
                                    标记本章已读
                                </Button>
                            )}
                            <Link href={`/sales-trainer/quiz/${unitId}`}>
                                <Button className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
                                    开始本章测验
                                </Button>
                            </Link>
                        </div>
                    </div>
                </div>
            </GlassCard>
        </div>
    );
}

export function CooChapterReaderTerminal({
    title,
    message,
    returnTo = DEFAULT_SALES_TRAINER_RETURN,
}: {
    title: string;
    message: string;
    returnTo?: string;
}) {
    const router = useRouter();
    const backHref = readLearnReturn(returnTo);

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            <GlassCard className="p-8 text-center">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-amber-50 text-amber-600">
                    <BookOpen className="h-8 w-8" />
                </div>
                <h3 className="mb-2 text-lg font-bold text-slate-900">{title}</h3>
                <p className="mb-4 text-sm text-slate-500">{message}</p>
                <Button onClick={() => router.push(backHref)} className="rounded-full">
                    返回销售训练
                </Button>
            </GlassCard>
        </div>
    );
}
