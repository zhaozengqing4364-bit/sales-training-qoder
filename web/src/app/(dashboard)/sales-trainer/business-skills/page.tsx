"use client";

import Link from "next/link";
import type { ReactNode, RefObject } from "react";
import { useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
    ArrowLeft,
    ArrowRight,
    BookOpen,
    CheckCircle2,
    ChevronDown,
    ChevronUp,
    ClipboardCheck,
    RotateCcw,
    Target,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { markdownComponents } from "@/components/sales-trainer/coo-markdown-components";
import type {
    BusinessEtiquetteLearningChapter,
    BusinessEtiquetteLearningUnit,
    BusinessEtiquetteQuizQuestion,
    BusinessEtiquetteUnitQuiz,
    BusinessEtiquetteUnitQuizAttempt,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

import {
    BUSINESS_SKILLS_COACH_ACTION_LABEL,
    chapterNavigationLabel,
} from "./config";
import { useBusinessSkillsWorkbench } from "./use-business-skills-workbench";

type LearningUnitVisualState = "completed" | "in_progress" | "not_started";

function learningUnitVisualState(unit: BusinessEtiquetteLearningUnit): LearningUnitVisualState {
    if (unit.progress.is_completed) {
        return "completed";
    }
    if (unit.progress.completed_chapters > 0) {
        return "in_progress";
    }
    return "not_started";
}

function learningUnitStatusLabel(state: LearningUnitVisualState): string {
    if (state === "completed") {
        return "已完成";
    }
    if (state === "in_progress") {
        return "进行中";
    }
    return "未开始";
}

function learningUnitStatusClassName(state: LearningUnitVisualState): string {
    if (state === "completed") {
        return "bg-emerald-50 text-emerald-700 ring-emerald-200";
    }
    if (state === "in_progress") {
        return "bg-amber-50 text-amber-700 ring-amber-200";
    }
    return "bg-slate-100 text-slate-500 ring-slate-200";
}

function learningUnitProgressClassName(state: LearningUnitVisualState): string {
    if (state === "completed") {
        return "bg-emerald-500";
    }
    if (state === "in_progress") {
        return "bg-amber-500";
    }
    return "bg-slate-300";
}

function LearningPathBar({
    selectedUnitKey,
    units,
    onSelect,
}: {
    readonly selectedUnitKey: string | null;
    readonly units: readonly BusinessEtiquetteLearningUnit[];
    readonly onSelect: (unitKey: string) => void;
}) {
    const completedCount = units.filter((unit) => unit.progress.is_completed).length;

    return (
        <section className="rounded-[1.5rem] border border-slate-200 bg-white p-4 shadow-sm" aria-label="商务礼仪训练路径">
            <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-slate-400" />
                    <h2 className="text-sm font-black text-slate-900">训练路径</h2>
                    <span className="rounded-full bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-500 ring-1 ring-slate-100">
                        {completedCount}/{units.length} 小单元
                    </span>
                </div>
                <p className="text-xs text-slate-500">完成阅读后再进入测验，进度以最新记录为准。</p>
            </div>
            <div className="-mx-1 overflow-x-auto px-1 pb-1">
                <div className="flex min-w-max gap-2">
                    {units.map((unit) => {
                        const isSelected = selectedUnitKey === unit.unit_key;
                        const progressText = `${unit.progress.completed_chapters}/${unit.progress.total_chapters}`;
                        const progressPercent = Math.round(
                            (unit.progress.completed_chapters / Math.max(unit.progress.total_chapters, 1)) * 100,
                        );
                        const state = learningUnitVisualState(unit);
                        return (
                            <button
                                key={unit.unit_key}
                                type="button"
                                disabled={!unit.enabled}
                                onClick={() => onSelect(unit.unit_key)}
                                className={cn(
                                    "w-[11.75rem] shrink-0 rounded-2xl border bg-white px-3.5 py-3 text-left transition-colors",
                                    isSelected
                                        ? "border-slate-950 shadow-md shadow-slate-900/10"
                                        : "border-slate-200 hover:border-slate-300 hover:bg-slate-50",
                                    unit.enabled ? "" : "opacity-60",
                                )}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-[11px] font-bold text-slate-400">
                                        第 {unit.order_index} 单元
                                    </span>
                                    <span className={cn(
                                        "rounded-full px-2 py-0.5 text-[11px] font-bold ring-1",
                                        learningUnitStatusClassName(state),
                                    )}
                                    >
                                        {learningUnitStatusLabel(state)}
                                    </span>
                                </div>
                                <p className="mt-2 truncate text-sm font-black text-slate-900">{unit.title}</p>
                                <p className="mt-1 line-clamp-1 text-xs leading-relaxed text-slate-500">
                                    {unit.description || unit.empty_state_message || "暂无小单元说明。"}
                                </p>
                                <div className="mt-3 flex items-center gap-2">
                                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                                        <div
                                            className={cn("h-full rounded-full", learningUnitProgressClassName(state))}
                                            style={{ width: `${progressPercent}%` }}
                                        />
                                    </div>
                                    <span className="shrink-0 text-xs font-bold text-slate-500">阅读 {progressText}</span>
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}

function ChapterList({
    chapters,
    selectedId,
    onSelect,
}: {
    readonly chapters: readonly BusinessEtiquetteLearningChapter[];
    readonly selectedId: string | null;
    readonly onSelect: (chapterId: string) => void;
}) {
    return (
        <nav className="space-y-2" aria-label="商务礼仪原文章节">
            {chapters.map((chapter, index) => {
                const isSelected = selectedId === chapter.chapter_id;
                return (
                    <button
                        key={chapter.chapter_id}
                        type="button"
                        onClick={() => onSelect(chapter.chapter_id)}
                        className={`w-full rounded-xl border px-3 py-2.5 text-left transition-colors ${
                            isSelected
                                ? "border-slate-950 bg-slate-950 text-white"
                                : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                        }`}
                    >
                        <span className="flex items-center gap-2 text-sm font-bold leading-relaxed">
                            {chapter.completed ? <CheckCircle2 className="h-4 w-4" /> : null}
                            {chapterNavigationLabel(index, chapter.title)}
                        </span>
                    </button>
                );
            })}
        </nav>
    );
}

const businessSkillsMarkdownComponents = {
    ...markdownComponents,
    h2: ({ children }: { readonly children?: ReactNode }) => (
        <h2 className="mb-4 mt-9 text-2xl font-black leading-snug text-slate-950 first:mt-0">{children}</h2>
    ),
    h3: ({ children }: { readonly children?: ReactNode }) => (
        <h3 className="mb-3 mt-7 text-xl font-bold leading-snug text-slate-900 first:mt-0">{children}</h3>
    ),
    p: ({ children }: { readonly children?: ReactNode }) => (
        <p className="mb-5 text-[15px] leading-8 text-slate-700 [text-wrap:pretty] last:mb-0">{children}</p>
    ),
    blockquote: ({ children }: { readonly children?: ReactNode }) => (
        <blockquote className="my-7 rounded-2xl border border-emerald-100 border-l-4 border-l-emerald-400 bg-emerald-50/70 px-5 py-4 text-[15px] leading-8 text-slate-700 [&_p]:mb-0">
            {children}
        </blockquote>
    ),
    strong: ({ children }: { readonly children?: ReactNode }) => (
        <strong className="font-black text-slate-950">{children}</strong>
    ),
};

const BUSINESS_SKILLS_CASE_PATTERNS = [
    /^55387/,
    /松下幸之助/,
    /(?:邱|丘)吉尔/,
];

function enhanceBusinessSkillsArticleMarkdown(content: string): string {
    return content
        .split(/\n{2,}/)
        .map((block) => {
            const trimmed = block.trim();
            if (
                !trimmed
                || trimmed.startsWith(">")
                || trimmed.startsWith("#")
                || trimmed.startsWith("!")
                || trimmed.startsWith("|")
                || trimmed.startsWith("- ")
                || /^\d+\./.test(trimmed)
            ) {
                return block;
            }
            if (!BUSINESS_SKILLS_CASE_PATTERNS.some((pattern) => pattern.test(trimmed))) {
                return block;
            }
            return trimmed
                .split("\n")
                .map((line) => `> ${line}`)
                .join("\n");
        })
        .join("\n\n");
}

function formatScoreValue(value: number | null): string {
    if (value === null) {
        return "待评分";
    }
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function questionTypeLabel(questionType: string): string {
    if (questionType === "short_answer") {
        return "简答题";
    }
    if (questionType === "multiple_choice") {
        return "多选题";
    }
    return "单选题";
}

function snapshotText(snapshot: Record<string, unknown>, key: string): string | null {
    const value = snapshot[key];
    return typeof value === "string" && value.trim() ? value : null;
}

function answerPayloadText(value: unknown): string {
    if (value === null || value === undefined || value === "") {
        return "未作答";
    }
    if (Array.isArray(value)) {
        return value.length ? value.map(String).join("、") : "未作答";
    }
    if (typeof value === "object") {
        try {
            return JSON.stringify(value);
        } catch {
            return "复杂答案";
        }
    }
    return String(value);
}

function attemptStatusText(attempt: BusinessEtiquetteUnitQuizAttempt): string {
    if (attempt.status === "submitted" || attempt.passed === null) {
        return "待评分";
    }
    return attempt.passed ? "已达标" : "未达标";
}

function attemptScoreText(attempt: BusinessEtiquetteUnitQuizAttempt): string {
    if (attempt.total_score === null || attempt.max_score === null) {
        return "待评分";
    }
    return `${formatScoreValue(attempt.total_score)} / ${formatScoreValue(attempt.max_score)}`;
}

function formatAttemptTime(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return new Intl.DateTimeFormat("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    }).format(date);
}

function answerAnalysisText(
    answer: BusinessEtiquetteUnitQuizAttempt["answers"][number],
): string {
    if (answer.analysis?.trim()) {
        return answer.analysis.trim();
    }
    const explanation = snapshotText(answer.question_snapshot, "explanation");
    if (explanation) {
        return explanation;
    }
    const referenceAnswer = snapshotText(answer.question_snapshot, "reference_answer");
    if (answer.is_correct === true) {
        return "本题答对了，继续保留这个做法。";
    }
    if (answer.is_correct === false) {
        return referenceAnswer
            ? `本题需要回到参考答案复盘：${referenceAnswer}`
            : "本题暂未配置解析，请结合题干场景复盘商务礼仪的尊重、分寸和顺序要求。";
    }
    return "本题正在等待评分，评分完成后会显示解析。";
}

function answerAnalysisLabel(questionType: string): string {
    return questionType === "short_answer" ? "AI 解析：" : "题目解析：";
}

function formatScoringLatency(ms: number): string {
    if (ms < 1000) {
        return `${ms}ms`;
    }
    return `${(ms / 1000).toFixed(1)} 秒`;
}

function answerScoringSourceText(
    answer: BusinessEtiquetteUnitQuizAttempt["answers"][number],
): string {
    if (answer.scoring_source === "ai_llm") {
        const modelText = answer.scoring_model || answer.scoring_provider;
        const parts = ["AI 评测"];
        if (modelText) {
            parts.push(modelText);
        }
        if (typeof answer.scoring_latency_ms === "number") {
            parts.push(`耗时 ${formatScoringLatency(answer.scoring_latency_ms)}`);
        }
        return parts.join(" · ");
    }
    if (answer.scoring_source === "local_empty_answer") {
        return "未作答校验";
    }
    if (answer.scoring_source === "ai_llm_failed") {
        return "AI 评测未完成";
    }
    if (answer.question_type === "short_answer") {
        return "AI 评测";
    }
    return "规则判分 · 题库标准答案";
}

function QuizAttemptDiagnosis({
    allUnitsCompleted,
    attempt,
    attemptViewLabel,
    coachHref,
    coachHrefError,
    examHref,
    isLatestAttempt,
    isReviewExpanded,
    nextLearningUnitTitle,
    onContinueLearningUnit,
    onRetry,
    onReviewRecommendedChapter,
    onToggleReview,
    passThreshold,
    resultRef,
}: {
    readonly allUnitsCompleted: boolean;
    readonly attempt: BusinessEtiquetteUnitQuizAttempt;
    readonly attemptViewLabel: string;
    readonly coachHref: string | null;
    readonly coachHrefError: string | null;
    readonly examHref: string;
    readonly isLatestAttempt: boolean;
    readonly isReviewExpanded: boolean;
    readonly nextLearningUnitTitle: string | null;
    readonly onContinueLearningUnit: () => void;
    readonly onRetry: () => void;
    readonly onReviewRecommendedChapter: () => void;
    readonly onToggleReview: () => void;
    readonly passThreshold: number | null;
    readonly resultRef: RefObject<HTMLDivElement | null>;
}) {
    const isPending = attempt.status === "submitted" || attempt.passed === null;
    const isPassed = attempt.passed === true;
    const statusLabel = isPending ? "待评分" : isPassed ? "已达标" : "未达标";
    const headline = isPending
        ? "等待评分结果"
        : isPassed
            ? allUnitsCompleted
                ? "本节已达标，可以进入考试"
                : "可进入下一小单元"
            : "建议先补练，再重新小测";
    const summary = isPending
        ? "简答题或 AI 评分还在处理，先保留本次答题记录，不把它误判为未达标。"
        : isPassed
            ? "本节要求已经通过，下一步可以继续学习路径。"
            : "本次小测暴露了薄弱点，建议先回看对应章节或进 AI 教练补练。";
    const scoreText = attempt.total_score === null || attempt.max_score === null
        ? "待评分"
        : `${formatScoreValue(attempt.total_score)} / ${formatScoreValue(attempt.max_score)}`;
    const recommendedText = attempt.recommended_chapter_orders.length
        ? `第 ${attempt.recommended_chapter_orders.join("、")} 章`
        : "暂无指定章节";
    const statusClassName = isPending
        ? "bg-amber-50 text-amber-700 ring-amber-200"
        : isPassed
            ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
            : "bg-rose-50 text-rose-700 ring-rose-200";

    return (
        <div ref={resultRef} tabIndex={-1} className="space-y-4 outline-none">
            <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                <div className="grid gap-4 border-b border-slate-100 p-4 xl:grid-cols-[minmax(0,1fr)_15rem]">
                    <div>
                        <div className="flex flex-wrap items-center gap-2">
                            <span className={`rounded-full px-3 py-1 text-xs font-black ring-1 ${statusClassName}`}>
                                {statusLabel}
                            </span>
                            <span className="text-sm font-black text-slate-900">本节诊断</span>
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-500">
                                当前查看：{attemptViewLabel}{isLatestAttempt ? "（最新提交）" : "（历史记录）"}
                            </span>
                        </div>
                        <h4 className="mt-3 text-2xl font-black tracking-tight text-slate-950">
                            {headline}
                        </h4>
                        {!isLatestAttempt ? (
                            <p className="mt-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-relaxed text-amber-800">
                                你正在查看历史小测记录，不是最新一次提交。请在下方“小测记录”选择最新记录查看刚提交的结果。
                            </p>
                        ) : null}
                        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">
                            {summary}
                        </p>
                    </div>
                    <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs font-bold uppercase tracking-wide text-slate-400">
                            本次得分
                        </p>
                        <p className="mt-2 text-2xl font-black text-slate-950">{scoreText}</p>
                        <p className="mt-1 text-xs text-slate-500">
                            {passThreshold === null ? "按能力点达标线判断" : `通过线 ${passThreshold}`}
                        </p>
                    </div>
                </div>

                <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_16rem]">
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 text-sm font-black text-slate-900">
                            <Target className="h-4 w-4 text-slate-500" />
                            能力点诊断
                        </div>
                        {attempt.capability_scores.length ? (
                            <div className="grid gap-2 2xl:grid-cols-2">
                                {attempt.capability_scores.map((capability) => {
                                    const capabilityStatus = capability.mastered === null
                                        ? "待评分"
                                        : capability.mastered ? "达标" : "需补练";
                                    const capabilityClassName = capability.mastered === null
                                        ? "bg-amber-50 text-amber-700"
                                        : capability.mastered
                                            ? "bg-emerald-50 text-emerald-700"
                                            : "bg-rose-50 text-rose-700";
                                    return (
                                        <div
                                            key={capability.capability_key}
                                            className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-3"
                                        >
                                            <div className="flex items-start justify-between gap-2">
                                                <p className="font-semibold text-slate-900">{capability.display_name}</p>
                                                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold ${capabilityClassName}`}>
                                                    {capabilityStatus}
                                                </span>
                                            </div>
                                            <p className="mt-2 text-sm text-slate-500">
                                                {capability.normalized_score === null
                                                    ? "待评分"
                                                    : `${Math.round(capability.normalized_score)} 分`}
                                                {capability.mastery_level_name ? ` · ${capability.mastery_level_name}` : ""}
                                            </p>
                                            <p className="mt-1 text-xs text-slate-400">
                                                达标线 {capability.threshold}
                                            </p>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <p className="rounded-xl bg-slate-50 px-3 py-3 text-sm text-slate-500">
                                系统还未返回能力点评分。
                            </p>
                        )}
                    </div>

                    <aside className="space-y-3 rounded-xl bg-slate-50 p-3">
                        <p className="text-sm font-black text-slate-900">下一步</p>
                        {!isPending && !isPassed ? (
                            <p className="text-sm leading-relaxed text-slate-500">
                                建议先回看 {recommendedText}，再用 AI 教练补一轮。
                            </p>
                        ) : (
                            <p className="text-sm leading-relaxed text-slate-500">
                                {nextLearningUnitTitle
                                    ? `下一小单元：${nextLearningUnitTitle}`
                                    : allUnitsCompleted ? "阅读任务已完成，可以进入考试。" : "继续完成后续训练。"}
                            </p>
                        )}
                        <div className="flex flex-col gap-2">
                            {!isPending && isPassed && nextLearningUnitTitle ? (
                                <Button
                                    variant="primary"
                                    onClick={onContinueLearningUnit}
                                >
                                    进入下一小单元
                                    <ArrowRight className="ml-2 h-4 w-4" />
                                </Button>
                            ) : null}
                            {!isPending && isPassed && allUnitsCompleted ? (
                                <Button asChild variant="primary">
                                    <Link href={examHref}>
                                        进入考试
                                        <ArrowRight className="ml-2 h-4 w-4" />
                                    </Link>
                                </Button>
                            ) : null}
                            {!isPending && !isPassed && coachHref ? (
                                <Button asChild variant="primary">
                                    <Link href={coachHref}>去 AI 教练补练</Link>
                                </Button>
                            ) : null}
                            {!isPending && !isPassed && !coachHref && coachHrefError ? (
                                <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">
                                    AI 教练入口暂不可用：{coachHrefError}
                                </p>
                            ) : null}
                            {!isPending && !isPassed && attempt.recommended_chapter_orders.length ? (
                                <Button
                                    variant="outline"
                                    className="rounded-full border-slate-200"
                                    onClick={onReviewRecommendedChapter}
                                >
                                    回看推荐章节
                                </Button>
                            ) : null}
                            <Button
                                variant="outline"
                                className="rounded-full border-slate-200"
                                onClick={onRetry}
                            >
                                <RotateCcw className="mr-2 h-4 w-4" />
                                重新小测
                            </Button>
                        </div>
                    </aside>
                </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white">
                <button
                    type="button"
                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
                    onClick={onToggleReview}
                >
                    <span className="inline-flex items-center gap-2 text-sm font-black text-slate-900">
                        <ClipboardCheck className="h-4 w-4 text-slate-500" />
                        答题回看
                    </span>
                    {isReviewExpanded ? (
                        <ChevronUp className="h-4 w-4 text-slate-500" />
                    ) : (
                        <ChevronDown className="h-4 w-4 text-slate-500" />
                    )}
                </button>
                {isReviewExpanded ? (
                    <div className="space-y-3 border-t border-slate-100 p-4">
                        {attempt.answers.length ? (
                            attempt.answers.map((answer, index) => {
                                const snapshot = answer.question_snapshot;
                                const stem = snapshotText(snapshot, "stem") ?? "题目内容未返回";
                                const referenceAnswer = snapshotText(snapshot, "reference_answer");
                                const analysis = answerAnalysisText(answer);
                                const scoringSource = answerScoringSourceText(answer);
                                const answerStatus = answer.is_correct === null
                                    ? "待评分"
                                    : answer.is_correct ? "正确" : "需订正";
                                return (
                                    <article key={`${answer.question_id}-${index}`} className="rounded-xl bg-slate-50 p-3">
                                        <div className="flex flex-wrap items-center gap-2 text-xs font-bold text-slate-400">
                                            <span>{index + 1}</span>
                                            <span>{questionTypeLabel(answer.question_type)}</span>
                                            <span>
                                                {answer.score === null
                                                    ? "待评分"
                                                    : `${formatScoreValue(answer.score)} / ${formatScoreValue(answer.max_score)}`}
                                            </span>
                                            <span>{answerStatus}</span>
                                            <span className="rounded-full bg-white px-2 py-0.5 text-slate-500 ring-1 ring-slate-200">
                                                {scoringSource}
                                            </span>
                                        </div>
                                        <p className="mt-2 text-sm font-semibold leading-relaxed text-slate-900">
                                            {stem}
                                        </p>
                                        <p className="mt-2 text-sm text-slate-500">
                                            你的答案：{answerPayloadText(answer.answer_payload)}
                                        </p>
                                        {referenceAnswer ? (
                                            <p className="mt-1 text-sm text-slate-500">
                                                参考答案：{referenceAnswer}
                                            </p>
                                        ) : null}
                                        <p className="mt-2 rounded-lg bg-white px-3 py-2 text-sm leading-relaxed text-slate-600">
                                            <span className="font-semibold text-slate-900">{answerAnalysisLabel(answer.question_type)}</span>
                                            {analysis}
                                        </p>
                                    </article>
                                );
                            })
                        ) : (
                            <p className="rounded-xl bg-slate-50 px-3 py-3 text-sm text-slate-500">
                                本次提交没有返回逐题明细。
                            </p>
                        )}
                    </div>
                ) : null}
            </section>
        </div>
    );
}

function QuizAttemptHistory({
    attempts,
    currentAttemptId,
    errorMessage,
    isLoading,
    onSelectAttempt,
}: {
    readonly attempts: readonly BusinessEtiquetteUnitQuizAttempt[];
    readonly currentAttemptId: string | null;
    readonly errorMessage: string | null;
    readonly isLoading: boolean;
    readonly onSelectAttempt: (attempt: BusinessEtiquetteUnitQuizAttempt) => void;
}) {
    return (
        <section className="rounded-2xl border border-slate-200 bg-white">
            <div className="flex flex-col gap-2 border-b border-slate-100 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <p className="text-sm font-black text-slate-900">小测记录</p>
                    <p className="mt-1 text-xs text-slate-500">
                        每次提交都会保留答案、得分、能力点诊断和逐题解析。
                    </p>
                </div>
                <span className="rounded-full bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-500">
                    {attempts.length} 次
                </span>
            </div>
            <div className="space-y-2 p-4">
                {isLoading ? (
                    <div className="h-16 animate-pulse rounded-xl bg-slate-50" />
                ) : null}
                {errorMessage ? (
                    <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                        {errorMessage}
                    </p>
                ) : null}
                {!isLoading && !errorMessage && attempts.length === 0 ? (
                    <p className="rounded-xl bg-slate-50 px-3 py-3 text-sm text-slate-500">
                        暂无小测记录。提交后会自动保存到这里。
                    </p>
                ) : null}
                {attempts.map((item, index) => {
                    const isSelected = currentAttemptId === item.attempt_id;
                    return (
                        <button
                            key={item.attempt_id}
                            type="button"
                            className={`flex w-full flex-col gap-2 rounded-xl border px-3 py-3 text-left transition-colors sm:flex-row sm:items-center sm:justify-between ${
                                isSelected
                                    ? "border-slate-900 bg-slate-900 text-white"
                                    : "border-slate-100 bg-slate-50 text-slate-700 hover:border-slate-300"
                            }`}
                            onClick={() => onSelectAttempt(item)}
                        >
                            <span>
                                <span className="block text-sm font-black">
                                    第 {attempts.length - index} 次 · {attemptStatusText(item)}
                                </span>
                                <span className={`mt-1 block text-xs ${isSelected ? "text-slate-200" : "text-slate-500"}`}>
                                    {formatAttemptTime(item.submitted_at)}
                                </span>
                            </span>
                            <span className="text-sm font-black">
                                {attemptScoreText(item)}
                            </span>
                        </button>
                    );
                })}
            </div>
        </section>
    );
}

function QuizPanel({
    allUnitsCompleted,
    answers,
    attempt,
    attempts,
    attemptsErrorMessage,
    coachHref,
    coachHrefError,
    errorMessage,
    examHref,
    isAttemptsLoading,
    isReviewExpanded,
    isSubmitting,
    nextLearningUnitTitle,
    onAnswerChange,
    onContinueLearningUnit,
    onRetry,
    onReturnToReading,
    onReviewRecommendedChapter,
    onSelectAttempt,
    onSubmit,
    onToggleReview,
    quiz,
    resultRef,
}: {
    readonly allUnitsCompleted: boolean;
    readonly answers: Record<string, string | string[]>;
    readonly attempt: BusinessEtiquetteUnitQuizAttempt | null;
    readonly attempts: readonly BusinessEtiquetteUnitQuizAttempt[];
    readonly attemptsErrorMessage: string | null;
    readonly coachHref: string | null;
    readonly coachHrefError: string | null;
    readonly errorMessage: string | null;
    readonly examHref: string;
    readonly isAttemptsLoading: boolean;
    readonly isReviewExpanded: boolean;
    readonly isSubmitting: boolean;
    readonly nextLearningUnitTitle: string | null;
    readonly onAnswerChange: (question: BusinessEtiquetteQuizQuestion, value: string, checked?: boolean) => void;
    readonly onContinueLearningUnit: () => void;
    readonly onRetry: () => void;
    readonly onReturnToReading: () => void;
    readonly onReviewRecommendedChapter: () => void;
    readonly onSelectAttempt: (attempt: BusinessEtiquetteUnitQuizAttempt) => void;
    readonly onSubmit: () => void;
    readonly onToggleReview: () => void;
    readonly quiz: BusinessEtiquetteUnitQuiz;
    readonly resultRef: RefObject<HTMLDivElement | null>;
}) {
    const hasQuestions = quiz.questions.length > 0;
    const selectedAttemptIndex = attempt
        ? attempts.findIndex((item) => item.attempt_id === attempt.attempt_id)
        : -1;
    const attemptViewLabel = selectedAttemptIndex >= 0
        ? `第 ${attempts.length - selectedAttemptIndex} 次`
        : "本次提交";
    const isLatestAttempt = selectedAttemptIndex <= 0;

    return (
        <div className="space-y-5 rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm md:p-6">
            <div className="flex flex-col gap-4 border-b border-slate-100 pb-5 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <p className="text-xs font-bold text-slate-400">
                        独立小测工作区
                    </p>
                    <h3 className="mt-1 text-2xl font-black tracking-tight text-slate-950">小单元测验</h3>
                    <p className="mt-1 text-sm leading-relaxed text-slate-500">
                        {quiz.question_count} 题 · {quiz.capabilities.map((item) => item.display_name).join("、")}
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    {quiz.pass_threshold !== null ? (
                        <span className="rounded-full bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">
                            通过线 {quiz.pass_threshold}
                        </span>
                    ) : null}
                    <Button
                        variant="outline"
                        size="sm"
                        className="border-slate-200"
                        onClick={onReturnToReading}
                    >
                        <ArrowLeft className="mr-2 h-4 w-4" />
                        返回文章
                    </Button>
                </div>
            </div>
            {errorMessage ? (
                <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-800">
                    <p className="font-semibold text-amber-900">小测提交未完成</p>
                    <p className="mt-1">{errorMessage}</p>
                </div>
            ) : null}
            {attempt ? (
                <QuizAttemptDiagnosis
                    allUnitsCompleted={allUnitsCompleted}
                    attempt={attempt}
                    attemptViewLabel={attemptViewLabel}
                    coachHref={coachHref}
                    coachHrefError={coachHrefError}
                    examHref={examHref}
                    isLatestAttempt={isLatestAttempt}
                    isReviewExpanded={isReviewExpanded}
                    nextLearningUnitTitle={nextLearningUnitTitle}
                    onContinueLearningUnit={onContinueLearningUnit}
                    onRetry={onRetry}
                    onReviewRecommendedChapter={onReviewRecommendedChapter}
                    onToggleReview={onToggleReview}
                    passThreshold={quiz.pass_threshold}
                    resultRef={resultRef}
                />
            ) : hasQuestions ? (
                <>
                    <div className="space-y-4">
                        {quiz.questions.map((question) => (
                            <div key={question.question_id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                                <p className="text-xs font-semibold text-slate-400">
                                    {question.order_index}. {questionTypeLabel(question.question_type)}
                                </p>
                                <p className="mt-2 font-semibold leading-7 text-slate-950">{question.stem}</p>
                                {question.question_type === "short_answer" ? (
                                    <textarea
                                        className="mt-3 min-h-28 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 outline-none transition-colors focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                                        value={String(answers[question.question_id] ?? "")}
                                        onChange={(event) => onAnswerChange(question, event.target.value)}
                                    />
                                ) : (
                                    <div className="mt-3 space-y-2">
                                        {question.options.map((option) => {
                                            const current = answers[question.question_id];
                                            const checked = Array.isArray(current)
                                                ? current.includes(option.value)
                                                : current === option.value;
                                            return (
                                                <label
                                                    key={option.value}
                                                    className={cn(
                                                        "flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition-colors",
                                                        checked
                                                            ? "border-slate-900 bg-slate-50 text-slate-900"
                                                            : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50/50",
                                                    )}
                                                >
                                                    <input
                                                        type={question.question_type === "multiple_choice" ? "checkbox" : "radio"}
                                                        checked={checked}
                                                        name={question.question_id}
                                                        onChange={(event) => onAnswerChange(question, option.value, event.target.checked)}
                                                        className="h-4 w-4 shrink-0 accent-slate-900"
                                                    />
                                                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-current text-xs font-bold opacity-70">
                                                        {option.value}
                                                    </span>
                                                    <span className="flex-1">{option.label}</span>
                                                </label>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                    <Button
                        variant="primary"
                        className="w-full sm:w-auto"
                        disabled={isSubmitting}
                        onClick={onSubmit}
                    >
                        {isSubmitting ? "正在提交小测" : "提交小测"}
                    </Button>
                </>
            ) : (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-relaxed text-amber-800">
                    当前小单元还没有可用题目，请联系管理员检查题库和考卷绑定。
                </div>
            )}
            <QuizAttemptHistory
                attempts={attempts}
                currentAttemptId={attempt?.attempt_id ?? null}
                errorMessage={attemptsErrorMessage}
                isLoading={isAttemptsLoading}
                onSelectAttempt={onSelectAttempt}
            />
        </div>
    );
}

export default function BusinessSkillsPage() {
    const searchParams = useSearchParams();
    const unitId = searchParams.get("unitId");
    const requestedLearningUnitKey = searchParams.get("learningUnit");
    const {
        allUnitsCompleted,
        article,
        canStartSelectedUnitQuiz,
        coachHref,
        coachHrefError,
        completingChapterId,
        completeCurrentChapter,
        continueToNextLearningUnit,
        error,
        examHref,
        isLoading,
        isQuizAttemptsLoading,
        isQuizLoading,
        isQuizReviewExpanded,
        isQuizSubmitting,
        loadCurrentQuiz,
        nextLearningUnit,
        quiz,
        quizAnswers,
        quizAttempt,
        quizAttempts,
        quizAttemptsError,
        quizResultRef,
        quizWorkflowError,
        retryCurrentQuiz,
        returnToCurrentReading,
        reviewRecommendedChapter,
        selectLearningUnit,
        selectQuizAttempt,
        selectedArticleChapter,
        selectedChapter,
        selectedLearningUnit,
        setIsQuizReviewExpanded,
        setSelectedChapterId,
        sortedLearningUnits,
        submitCurrentQuiz,
        updateQuizAnswer,
    } = useBusinessSkillsWorkbench({
        requestedLearningUnitKey,
        unitId,
    });
    const completedLearningUnitCount = sortedLearningUnits.filter((unit) => unit.progress.is_completed).length;
    const totalLearningUnitCount = sortedLearningUnits.length;
    const learningProgressPercent = totalLearningUnitCount
        ? Math.round((completedLearningUnitCount / totalLearningUnitCount) * 100)
        : 0;
    const isSelectedChapterCompleted = Boolean(selectedChapter?.completed);
    const shouldEmphasizeQuizAction = Boolean(
        selectedLearningUnit?.require_quiz && canStartSelectedUnitQuiz,
    );

    return (
        <div className="mx-auto max-w-[92rem] space-y-5 pb-20">
            <Link href="/sales-trainer" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900">
                <ArrowLeft className="h-4 w-4" />
                返回新人训练路径
            </Link>

            <div className="overflow-hidden rounded-[1.75rem] border border-slate-200 bg-white px-6 py-6 shadow-sm md:px-7">
                <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <p className="text-xs font-bold text-slate-400">
                            新人训练路径 · 商务技巧
                        </p>
                        <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950 md:text-4xl">商务礼仪训练</h1>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                            按小单元完成阅读、小测和 AI 教练练习，系统保留最新训练进度。
                        </p>
                    </div>
                    {sortedLearningUnits.length ? (
                        <div className="min-w-56 rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600 ring-1 ring-slate-100">
                            <div className="flex items-center justify-between gap-3">
                                <span className="font-semibold text-slate-500">阅读进度</span>
                                <span className="font-black text-slate-900">
                                    {completedLearningUnitCount}/{totalLearningUnitCount}
                                </span>
                            </div>
                            <div className="mt-3 h-2 overflow-hidden rounded-full bg-white">
                                <div
                                    className="h-full rounded-full bg-slate-950"
                                    style={{ width: `${learningProgressPercent}%` }}
                                />
                            </div>
                        </div>
                    ) : null}
                </div>
            </div>

            {error ? (
                <GlassCard className="space-y-2 border-red-100 bg-red-50 p-4 text-sm text-red-700">
                    <p className="font-bold">商务礼仪训练内容暂不可用</p>
                    <p>{error}</p>
                </GlassCard>
            ) : null}

            {isLoading ? (
                <div className="h-64 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
            ) : article && selectedLearningUnit && selectedChapter ? (
                <div className="space-y-5">
                    <LearningPathBar
                        units={sortedLearningUnits}
                        selectedUnitKey={selectedLearningUnit.unit_key}
                        onSelect={selectLearningUnit}
                    />

                    {quiz ? (
                        <main className="mx-auto max-w-5xl">
                            <QuizPanel
                                allUnitsCompleted={allUnitsCompleted}
                                answers={quizAnswers}
                                attempt={quizAttempt}
                                attempts={quizAttempts}
                                attemptsErrorMessage={quizAttemptsError}
                                coachHref={coachHref}
                                coachHrefError={coachHrefError}
                                errorMessage={quizWorkflowError}
                                examHref={examHref}
                                isAttemptsLoading={isQuizAttemptsLoading}
                                isReviewExpanded={isQuizReviewExpanded}
                                isSubmitting={isQuizSubmitting}
                                nextLearningUnitTitle={nextLearningUnit?.title ?? null}
                                onAnswerChange={updateQuizAnswer}
                                onContinueLearningUnit={continueToNextLearningUnit}
                                onRetry={retryCurrentQuiz}
                                onReturnToReading={returnToCurrentReading}
                                onReviewRecommendedChapter={reviewRecommendedChapter}
                                onSelectAttempt={selectQuizAttempt}
                                onSubmit={() => void submitCurrentQuiz()}
                                onToggleReview={() => setIsQuizReviewExpanded((current) => !current)}
                                quiz={quiz}
                                resultRef={quizResultRef}
                            />
                        </main>
                    ) : (
                        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem] xl:items-start">
                            <main className="min-w-0">
                                <article className="rounded-[1.75rem] border border-slate-200 bg-white px-5 py-7 shadow-sm md:px-10 md:py-10">
                                    <div className="mx-auto max-w-[42rem]">
                                        <div className="border-b border-slate-100 pb-6">
                                            <p className="text-sm font-bold text-slate-400">{article.title}</p>
                                            <h2 className="mt-2 text-2xl font-black leading-tight text-slate-950 md:text-3xl">
                                                {selectedChapter.title}
                                            </h2>
                                        </div>
                                        <div className="mt-8 max-w-none [&_img]:my-7 [&_img]:max-h-[30rem] [&_img]:w-full [&_img]:rounded-2xl [&_img]:border [&_img]:border-slate-200 [&_img]:object-cover [&_img]:shadow-sm">
                                            <ReactMarkdown
                                                remarkPlugins={[remarkGfm]}
                                                components={businessSkillsMarkdownComponents}
                                            >
                                                {enhanceBusinessSkillsArticleMarkdown(selectedArticleChapter?.content || "暂无文章内容。")}
                                            </ReactMarkdown>
                                        </div>
                                    </div>
                                </article>
                            </main>

                            <aside className="space-y-4 xl:sticky xl:top-4">
                                <section className="rounded-[1.5rem] border border-slate-200 bg-white p-4 shadow-sm">
                                    <div className="flex items-center justify-between gap-3">
                                        <p className="text-sm font-black text-slate-900">本节任务</p>
                                        <span className={cn(
                                            "rounded-full px-2.5 py-1 text-xs font-bold ring-1",
                                            isSelectedChapterCompleted
                                                ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                                                : "bg-amber-50 text-amber-700 ring-amber-200",
                                        )}
                                        >
                                            {isSelectedChapterCompleted ? "本节已读" : "阅读中"}
                                        </span>
                                    </div>
                                    <h2 className="mt-3 text-lg font-black leading-snug text-slate-950">
                                        {selectedLearningUnit.title}
                                    </h2>
                                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                                        <div
                                            className={cn(
                                                "h-full rounded-full",
                                                selectedLearningUnit.progress.is_completed ? "bg-emerald-500" : "bg-amber-500",
                                            )}
                                            style={{
                                                width: `${Math.round((selectedLearningUnit.progress.completed_chapters / Math.max(selectedLearningUnit.progress.total_chapters, 1)) * 100)}%`,
                                            }}
                                        />
                                    </div>
                                    <p className="mt-2 text-xs font-semibold text-slate-500">
                                        阅读 {selectedLearningUnit.progress.completed_chapters}/{selectedLearningUnit.progress.total_chapters}
                                    </p>
                                    {selectedLearningUnit.capabilities.length ? (
                                        <div className="mt-3 flex flex-wrap gap-2">
                                            {selectedLearningUnit.capabilities.map((capability) => (
                                                <span
                                                    key={capability.capability_key}
                                                    className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700"
                                                >
                                                    {capability.display_name}
                                                </span>
                                            ))}
                                        </div>
                                    ) : null}
                                    <div className="mt-4 border-t border-slate-100 pt-4">
                                        <p className="mb-2 text-xs font-bold text-slate-400">章节</p>
                                        <ChapterList
                                            chapters={selectedLearningUnit.chapters}
                                            selectedId={selectedChapter.chapter_id}
                                            onSelect={setSelectedChapterId}
                                        />
                                    </div>
                                </section>

                                <section className="rounded-[1.5rem] border border-slate-200 bg-white p-4 shadow-sm">
                                    <p className="text-sm font-black text-slate-900">下一步</p>
                                    <p className="mt-1 text-sm leading-6 text-slate-500">
                                        {isSelectedChapterCompleted
                                            ? "本节已标记完成，可以进入小测或继续后续训练。"
                                            : "先完成本节阅读标记，再进入小测和 AI 教练。"}
                                    </p>
                                    <div className="mt-4 grid gap-2">
                                        {!isSelectedChapterCompleted ? (
                                            <Button
                                                variant="primary"
                                                disabled={completingChapterId === selectedChapter.chapter_id}
                                                onClick={() => void completeCurrentChapter()}
                                            >
                                                {completingChapterId === selectedChapter.chapter_id ? "正在标记本节" : "完成本节"}
                                            </Button>
                                        ) : null}
                                        {selectedLearningUnit.require_quiz ? (
                                            <Button
                                                variant={shouldEmphasizeQuizAction ? "primary" : "outline"}
                                                className="rounded-full border-slate-200"
                                                disabled={isQuizLoading || !canStartSelectedUnitQuiz}
                                                onClick={() => void loadCurrentQuiz()}
                                            >
                                                {isQuizLoading
                                                    ? "正在加载小测"
                                                    : canStartSelectedUnitQuiz ? "开始小测" : "读完后小测"}
                                            </Button>
                                        ) : null}
                                        {coachHref && selectedLearningUnit.require_ai_coach ? (
                                            <Button asChild variant="outline" className="rounded-full border-slate-200">
                                                <Link href={coachHref}>
                                                    {BUSINESS_SKILLS_COACH_ACTION_LABEL}
                                                </Link>
                                            </Button>
                                        ) : null}
                                        {allUnitsCompleted ? (
                                            <Button asChild variant={shouldEmphasizeQuizAction ? "outline" : "primary"} className="rounded-full border-slate-200">
                                                <Link href={examHref}>
                                                    完成学习，进入考试
                                                    <ArrowRight className="ml-2 h-4 w-4" />
                                                </Link>
                                            </Button>
                                        ) : null}
                                    </div>
                                    {!allUnitsCompleted ? (
                                        <p className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-500">
                                            完成要求阅读的小单元后开放考试入口。
                                        </p>
                                    ) : null}
                                    {selectedLearningUnit.require_quiz && !canStartSelectedUnitQuiz ? (
                                        <p className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-500">
                                            先完成当前小单元的要求阅读，再进入小测。
                                        </p>
                                    ) : null}
                                    {!coachHref && coachHrefError && selectedLearningUnit.require_ai_coach ? (
                                        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-relaxed text-amber-800">
                                            AI 教练入口暂不可用：{coachHrefError}
                                        </p>
                                    ) : null}
                                    {quizWorkflowError ? (
                                        <div role="alert" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-800">
                                            <p className="font-semibold text-amber-900">小测暂不可用</p>
                                            <p className="mt-1">{quizWorkflowError}</p>
                                        </div>
                                    ) : null}
                                </section>
                            </aside>
                        </div>
                    )}
                </div>
            ) : error ? null : (
                <GlassCard className="p-6 text-sm text-slate-500">当前商务礼仪训练包没有可用小单元，请管理员检查路径配置。</GlassCard>
            )}
        </div>
    );
}
