"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
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
import { api } from "@/lib/api/client";
import type {
    BusinessEtiquetteLearningChapter,
    BusinessEtiquetteLearningUnit,
    BusinessEtiquetteQuizQuestion,
    BusinessEtiquetteUnitQuiz,
    BusinessEtiquetteUnitQuizAttempt,
    NewcomerArticle,
    NewcomerArticleChapter,
    SalesTrainerUnit,
} from "@/lib/api/types";
import { findBusinessSkillsCoachHref } from "@/lib/sales-trainer/ai-coach-availability";

import {
    BUSINESS_SKILLS_COACH_ACTION_LABEL,
    BUSINESS_SKILLS_MODULE_KEY,
    businessSkillsArticleErrorMessage,
    businessSkillsExamHref,
    chapterNavigationLabel,
    learningContentIdFromUnit,
    resolveBusinessSkillsUnit,
} from "./config";

function sortArticleChapters(chapters: readonly NewcomerArticleChapter[]): NewcomerArticleChapter[] {
    return [...chapters].sort((left, right) => left.order_index - right.order_index);
}

function sortLearningUnits(
    units: readonly BusinessEtiquetteLearningUnit[],
): BusinessEtiquetteLearningUnit[] {
    return [...units].sort((left, right) => left.order_index - right.order_index);
}

async function resolveCoachHref(unitId: string | null): Promise<string | null> {
    try {
        const pathResponse = await api.salesTrainer.listPaths();
        return findBusinessSkillsCoachHref(pathResponse.items, unitId);
    } catch (loadError) {
        if (loadError instanceof Error) {
            return null;
        }
        throw loadError;
    }
}

function LearningUnitList({
    selectedUnitKey,
    units,
    onSelect,
}: {
    readonly selectedUnitKey: string | null;
    readonly units: readonly BusinessEtiquetteLearningUnit[];
    readonly onSelect: (unitKey: string) => void;
}) {
    return (
        <section className="space-y-2" aria-label="商务礼仪训练小单元">
            {units.map((unit) => {
                const isSelected = selectedUnitKey === unit.unit_key;
                const progressText = `${unit.progress.completed_chapters}/${unit.progress.total_chapters}`;
                const capabilityNames = unit.capabilities.map((capability) => capability.display_name);
                return (
                    <button
                        key={unit.unit_key}
                        type="button"
                        disabled={!unit.enabled}
                        onClick={() => onSelect(unit.unit_key)}
                        className={`w-full rounded-xl border px-3 py-3 text-left transition-colors ${
                            isSelected
                                ? "border-slate-900 bg-slate-900 text-white"
                                : "border-slate-200 bg-white text-slate-700 hover:border-slate-400"
                        } ${unit.enabled ? "" : "opacity-60"}`}
                    >
                        <div className="flex items-center justify-between gap-2">
                            <span className="text-[11px] font-bold uppercase opacity-70">
                                小单元 {unit.order_index}
                            </span>
                            {unit.progress.is_completed ? <CheckCircle2 className="h-4 w-4" /> : null}
                        </div>
                        <p className="mt-1 text-sm font-black">{unit.title}</p>
                        <p className={`mt-1 line-clamp-2 text-xs leading-relaxed ${isSelected ? "text-slate-200" : "text-slate-500"}`}>
                            {unit.description || unit.empty_state_message || "暂无小单元说明。"}
                        </p>
                        {capabilityNames.length ? (
                            <div className="mt-2 flex flex-wrap gap-1">
                                {capabilityNames.slice(0, 2).map((name) => (
                                    <span
                                        key={name}
                                        className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                                            isSelected
                                                ? "bg-white/15 text-white"
                                                : "bg-slate-100 text-slate-600"
                                        }`}
                                    >
                                        {name}
                                    </span>
                                ))}
                            </div>
                        ) : null}
                        <p className={`mt-2 text-xs font-bold ${isSelected ? "text-slate-200" : "text-slate-400"}`}>
                            阅读 {progressText}
                        </p>
                    </button>
                );
            })}
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
                                ? "border-slate-900 bg-slate-900 text-white"
                                : "border-slate-200 bg-white text-slate-700 hover:border-slate-400"
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
                                    className="rounded-full bg-slate-900 text-white"
                                    onClick={onContinueLearningUnit}
                                >
                                    进入下一小单元
                                    <ArrowRight className="ml-2 h-4 w-4" />
                                </Button>
                            ) : null}
                            {!isPending && isPassed && allUnitsCompleted ? (
                                <Button asChild className="rounded-full bg-slate-900 text-white">
                                    <Link href={examHref}>
                                        进入考试
                                        <ArrowRight className="ml-2 h-4 w-4" />
                                    </Link>
                                </Button>
                            ) : null}
                            {!isPending && !isPassed && coachHref ? (
                                <Button asChild className="rounded-full bg-slate-900 text-white">
                                    <Link href={coachHref}>去 AI 教练补练</Link>
                                </Button>
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
    errorMessage,
    examHref,
    isAttemptsLoading,
    isReviewExpanded,
    isSubmitting,
    nextLearningUnitTitle,
    onAnswerChange,
    onContinueLearningUnit,
    onRetry,
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
    readonly errorMessage: string | null;
    readonly examHref: string;
    readonly isAttemptsLoading: boolean;
    readonly isReviewExpanded: boolean;
    readonly isSubmitting: boolean;
    readonly nextLearningUnitTitle: string | null;
    readonly onAnswerChange: (question: BusinessEtiquetteQuizQuestion, value: string, checked?: boolean) => void;
    readonly onContinueLearningUnit: () => void;
    readonly onRetry: () => void;
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
        <div className="mt-6 space-y-4 rounded-2xl border border-slate-100 bg-slate-50 p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <h3 className="text-lg font-black text-slate-900">小单元测验</h3>
                    <p className="text-sm text-slate-500">
                        {quiz.question_count} 题 · {quiz.capabilities.map((item) => item.display_name).join("、")}
                    </p>
                </div>
                {quiz.pass_threshold !== null ? (
                    <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600">
                        通过线 {quiz.pass_threshold}
                    </span>
                ) : null}
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
                    <div className="space-y-3">
                        {quiz.questions.map((question) => (
                            <div key={question.question_id} className="rounded-xl bg-white p-4">
                                <p className="text-sm font-semibold text-slate-400">
                                    {question.order_index}. {questionTypeLabel(question.question_type)}
                                </p>
                                <p className="mt-1 font-semibold text-slate-900">{question.stem}</p>
                                {question.question_type === "short_answer" ? (
                                    <textarea
                                        className="mt-3 min-h-24 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
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
                                                    className="flex items-center gap-2 rounded-lg border border-slate-100 px-3 py-2 text-sm text-slate-700"
                                                >
                                                    <input
                                                        type={question.question_type === "multiple_choice" ? "checkbox" : "radio"}
                                                        checked={checked}
                                                        name={question.question_id}
                                                        onChange={(event) => onAnswerChange(question, option.value, event.target.checked)}
                                                    />
                                                    <span>{option.value}. {option.label}</span>
                                                </label>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                    <Button
                        className="rounded-full bg-slate-900 text-white"
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
    const quizResultRef = useRef<HTMLDivElement | null>(null);
    const [units, setUnits] = useState<SalesTrainerUnit[]>([]);
    const [article, setArticle] = useState<NewcomerArticle | null>(null);
    const [learningUnits, setLearningUnits] = useState<BusinessEtiquetteLearningUnit[]>([]);
    const [selectedLearningUnitKey, setSelectedLearningUnitKey] = useState<string | null>(null);
    const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null);
    const [coachHref, setCoachHref] = useState<string | null>(null);
    const [quiz, setQuiz] = useState<BusinessEtiquetteUnitQuiz | null>(null);
    const [quizAttempt, setQuizAttempt] = useState<BusinessEtiquetteUnitQuizAttempt | null>(null);
    const [quizAttempts, setQuizAttempts] = useState<BusinessEtiquetteUnitQuizAttempt[]>([]);
    const [quizAnswers, setQuizAnswers] = useState<Record<string, string | string[]>>({});
    const [isQuizReviewExpanded, setIsQuizReviewExpanded] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [isQuizLoading, setIsQuizLoading] = useState(false);
    const [isQuizAttemptsLoading, setIsQuizAttemptsLoading] = useState(false);
    const [isQuizSubmitting, setIsQuizSubmitting] = useState(false);
    const [completingChapterId, setCompletingChapterId] = useState<string | null>(null);
    const [quizAttemptsError, setQuizAttemptsError] = useState<string | null>(null);
    const [quizWorkflowError, setQuizWorkflowError] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const selectedUnit = useMemo(() => resolveBusinessSkillsUnit(units, unitId), [unitId, units]);
    const examHref = businessSkillsExamHref(selectedUnit?.unit_id ?? unitId);
    const sortedArticleChapters = useMemo(
        () => article ? sortArticleChapters(article.chapters) : [],
        [article],
    );
    const articleChaptersById = useMemo(
        () => new Map(sortedArticleChapters.map((chapter) => [chapter.chapter_id, chapter])),
        [sortedArticleChapters],
    );
    const sortedLearningUnits = useMemo(
        () => sortLearningUnits(learningUnits),
        [learningUnits],
    );
    const selectedLearningUnit = sortedLearningUnits.find((unit) => unit.unit_key === selectedLearningUnitKey)
        ?? sortedLearningUnits[0]
        ?? null;
    const selectedLearningUnitIndex = selectedLearningUnit
        ? sortedLearningUnits.findIndex((unit) => unit.unit_key === selectedLearningUnit.unit_key)
        : -1;
    const nextLearningUnit = selectedLearningUnitIndex >= 0
        ? sortedLearningUnits.slice(selectedLearningUnitIndex + 1).find((unit) => unit.enabled) ?? null
        : null;
    const selectedChapter = selectedLearningUnit?.chapters.find((chapter) => chapter.chapter_id === selectedChapterId)
        ?? selectedLearningUnit?.chapters[0]
        ?? null;
    const selectedArticleChapter = selectedChapter
        ? articleChaptersById.get(selectedChapter.chapter_id) ?? null
        : null;
    const allUnitsCompleted = sortedLearningUnits.length > 0
        && sortedLearningUnits
            .filter((unit) => unit.enabled && unit.require_reading)
            .every((unit) => unit.progress.is_completed || unit.allow_skip_reading);
    const canStartSelectedUnitQuiz = selectedLearningUnit
        ? !selectedLearningUnit.require_reading
            || selectedLearningUnit.progress.is_completed
            || selectedLearningUnit.allow_skip_reading
        : false;

    useEffect(() => {
        let isActive = true;
        void api.salesTrainer.listUnits()
            .then(async (unitResponse) => {
                const nextSelectedUnit = resolveBusinessSkillsUnit(unitResponse.items, unitId);
                const learningContentId = learningContentIdFromUnit(nextSelectedUnit);
                const [nextArticle, learningUnitResponse, nextCoachHref] = await Promise.all([
                    api.newcomerTraining.getModuleArticle(
                        BUSINESS_SKILLS_MODULE_KEY,
                        learningContentId ? { learning_content_id: learningContentId } : undefined,
                    ),
                    api.newcomerTraining.getBusinessEtiquetteLearningUnits(),
                    resolveCoachHref(nextSelectedUnit?.unit_id ?? unitId),
                ]);
                return { learningUnitResponse, nextArticle, nextCoachHref, unitResponse };
            }).then(({ learningUnitResponse, nextArticle, nextCoachHref, unitResponse }) => {
                if (!isActive) {
                    return;
                }
                const nextLearningUnits = sortLearningUnits(learningUnitResponse.units);
                const nextSelectedUnit = nextLearningUnits.find((unit) => unit.unit_key === requestedLearningUnitKey)
                    ?? nextLearningUnits.find((unit) => unit.enabled)
                    ?? nextLearningUnits[0]
                    ?? null;
                setUnits(unitResponse.items);
                setArticle(nextArticle);
                setLearningUnits(nextLearningUnits);
                setCoachHref(nextCoachHref);
                setSelectedLearningUnitKey(nextSelectedUnit?.unit_key ?? null);
                setSelectedChapterId(nextSelectedUnit?.chapters[0]?.chapter_id ?? null);
                setError(null);
            }).catch((loadError) => {
                if (!isActive) {
                    return;
                }
                setError(businessSkillsArticleErrorMessage(loadError));
            }).finally(() => {
                if (isActive) {
                    setIsLoading(false);
                }
            });
        return () => {
            isActive = false;
        };
    }, [requestedLearningUnitKey, unitId]);

    function selectLearningUnit(unitKey: string) {
        const nextUnit = sortedLearningUnits.find((unit) => unit.unit_key === unitKey) ?? null;
        setSelectedLearningUnitKey(unitKey);
        setSelectedChapterId(nextUnit?.chapters[0]?.chapter_id ?? null);
        setQuiz(null);
        setQuizAttempt(null);
        setQuizAttempts([]);
        setQuizAnswers({});
        setIsQuizReviewExpanded(false);
        setQuizAttemptsError(null);
        setQuizWorkflowError(null);
    }

    function retryCurrentQuiz() {
        setQuizAttempt(null);
        setQuizAnswers({});
        setIsQuizReviewExpanded(false);
        setQuizWorkflowError(null);
    }

    function continueToNextLearningUnit() {
        if (!nextLearningUnit) {
            return;
        }
        selectLearningUnit(nextLearningUnit.unit_key);
    }

    function reviewRecommendedChapter() {
        const chapterOrder = quizAttempt?.recommended_chapter_orders[0];
        if (!selectedLearningUnit || chapterOrder === undefined) {
            return;
        }
        const targetChapter = selectedLearningUnit.chapters.find((chapter) => chapter.order_index === chapterOrder);
        if (targetChapter) {
            setSelectedChapterId(targetChapter.chapter_id);
        }
    }

    function selectQuizAttempt(attempt: BusinessEtiquetteUnitQuizAttempt) {
        setQuizAttempt(attempt);
        setIsQuizReviewExpanded(true);
        window.setTimeout(() => {
            quizResultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 0);
    }

    async function loadQuizAttemptHistory(unitKey: string): Promise<void> {
        setIsQuizAttemptsLoading(true);
        setQuizAttemptsError(null);
        try {
            const response = await api.newcomerTraining.listMyBusinessEtiquetteUnitQuizAttempts(
                unitKey,
                { limit: 20, offset: 0 },
            );
            setQuizAttempts(response.items);
        } catch (attemptError) {
            setQuizAttemptsError(businessSkillsArticleErrorMessage(attemptError));
        } finally {
            setIsQuizAttemptsLoading(false);
        }
    }

    async function completeCurrentChapter(): Promise<void> {
        if (!article || !selectedChapter) {
            return;
        }
        setCompletingChapterId(selectedChapter.chapter_id);
        try {
            await api.newcomerTraining.completeModuleArticleChapter(
                BUSINESS_SKILLS_MODULE_KEY,
                selectedChapter.chapter_id,
                { learning_content_id: article.learning_content_id },
            );
            const learningUnitResponse = await api.newcomerTraining.getBusinessEtiquetteLearningUnits();
            const nextLearningUnits = sortLearningUnits(learningUnitResponse.units);
            setLearningUnits(nextLearningUnits);
            const currentUnit = nextLearningUnits.find((unit) => unit.unit_key === selectedLearningUnitKey)
                ?? nextLearningUnits[0]
                ?? null;
            const selectedIndex = currentUnit?.chapters.findIndex((chapter) => chapter.chapter_id === selectedChapter.chapter_id) ?? -1;
            const nextChapter = selectedIndex >= 0 ? currentUnit?.chapters[selectedIndex + 1] : undefined;
            setSelectedChapterId(nextChapter?.chapter_id ?? selectedChapter.chapter_id);
            setQuizWorkflowError(null);
        } catch (completeError) {
            setError(businessSkillsArticleErrorMessage(completeError));
        } finally {
            setCompletingChapterId(null);
        }
    }

    async function loadCurrentQuiz(): Promise<void> {
        if (!selectedLearningUnit || !canStartSelectedUnitQuiz) return;
        setIsQuizLoading(true);
        setQuizWorkflowError(null);
        try {
            const nextQuiz = await api.newcomerTraining.getBusinessEtiquetteUnitQuiz(
                selectedLearningUnit.unit_key,
            );
            setQuiz(nextQuiz);
            setQuizAttempt(null);
            setQuizAttempts([]);
            setQuizAnswers({});
            setIsQuizReviewExpanded(false);
            void loadQuizAttemptHistory(selectedLearningUnit.unit_key);
            setError(null);
        } catch (quizError) {
            setQuizWorkflowError(businessSkillsArticleErrorMessage(quizError));
        } finally {
            setIsQuizLoading(false);
        }
    }

    function updateQuizAnswer(
        question: BusinessEtiquetteQuizQuestion,
        value: string,
        checked?: boolean,
    ) {
        setQuizAnswers((current) => {
            if (question.question_type === "multiple_choice") {
                const currentValues = Array.isArray(current[question.question_id])
                    ? current[question.question_id] as string[]
                    : [];
                const nextValues = checked
                    ? [...currentValues, value]
                    : currentValues.filter((item) => item !== value);
                return { ...current, [question.question_id]: nextValues };
            }
            return { ...current, [question.question_id]: value };
        });
    }

    async function submitCurrentQuiz(): Promise<void> {
        if (!selectedLearningUnit || !quiz) return;
        setIsQuizSubmitting(true);
        setQuizWorkflowError(null);
        try {
            const result = await api.newcomerTraining.submitBusinessEtiquetteUnitQuizAttempt(
                selectedLearningUnit.unit_key,
                {
                    answers: quiz.questions.map((question) => ({
                        question_id: question.question_id,
                        answer_payload: quizAnswers[question.question_id] ?? (
                            question.question_type === "multiple_choice" ? [] : ""
                        ),
                    })),
                },
            );
            setQuizAttempt(result);
            setQuizAttempts((current) => [
                result,
                ...current.filter((item) => item.attempt_id !== result.attempt_id),
            ]);
            setIsQuizReviewExpanded(false);
            window.setTimeout(() => {
                quizResultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
            }, 0);
            setError(null);
        } catch (quizError) {
            setQuizWorkflowError(businessSkillsArticleErrorMessage(quizError));
        } finally {
            setIsQuizSubmitting(false);
        }
    }

    return (
        <div className="mx-auto max-w-7xl space-y-6 pb-20">
            <Link href="/sales-trainer" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900">
                <ArrowLeft className="h-4 w-4" />
                返回新人训练路径
            </Link>

            <div className="rounded-2xl border border-slate-200 bg-white px-5 py-5 shadow-sm">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <p className="text-xs font-bold uppercase tracking-wide text-slate-400">
                            新人训练路径 · 商务技巧
                        </p>
                        <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-900">商务礼仪训练</h1>
                        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">
                            先按小单元读原文章节，再进入小测和 AI 教练。正文区域按 Markdown 文章渲染，目录只负责定位。
                        </p>
                    </div>
                    {sortedLearningUnits.length ? (
                        <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
                            <span className="font-black text-slate-900">
                                {sortedLearningUnits.filter((unit) => unit.progress.is_completed).length}
                            </span>
                            /{sortedLearningUnits.length} 小单元阅读完成
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
                <div className="grid gap-5 lg:grid-cols-[19rem_minmax(0,1fr)]">
                    <aside className="contents lg:block lg:space-y-4 lg:sticky lg:top-4 lg:self-start">
                        <section className="order-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:order-none">
                            <div className="mb-3 flex items-center justify-between gap-3">
                                <div>
                                    <p className="text-xs font-bold uppercase tracking-wide text-slate-400">
                                        训练路径
                                    </p>
                                    <h2 className="mt-1 text-base font-black text-slate-900">
                                        7 个小单元
                                    </h2>
                                </div>
                                <BookOpen className="h-5 w-5 text-slate-400" />
                            </div>
                            <div className="max-h-56 overflow-y-auto pr-1 lg:max-h-none lg:overflow-visible lg:pr-0">
                                <LearningUnitList
                                    units={sortedLearningUnits}
                                    selectedUnitKey={selectedLearningUnit.unit_key}
                                    onSelect={selectLearningUnit}
                                />
                            </div>
                        </section>
                        <section className="order-1 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:order-none">
                            <p className="text-xs font-bold uppercase tracking-wide text-slate-400">
                                当前阅读
                            </p>
                            <h2 className="mt-1 text-lg font-black text-slate-900">
                                {selectedLearningUnit.title}
                            </h2>
                            <p className="mt-1 text-sm text-slate-500">
                                {selectedLearningUnit.progress.completed_chapters}/{selectedLearningUnit.progress.total_chapters} 已完成
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
                            <div className="mt-4">
                                <ChapterList
                                    chapters={selectedLearningUnit.chapters}
                                    selectedId={selectedChapter.chapter_id}
                                    onSelect={setSelectedChapterId}
                                />
                            </div>
                        </section>
                    </aside>

                    <main className="order-2 min-w-0 space-y-4 lg:order-none">
                        <article className="rounded-2xl border border-slate-200 bg-white px-5 py-6 shadow-sm md:px-10 md:py-9">
                            <div className="mx-auto max-w-3xl">
                                <div className="border-b border-slate-100 pb-5">
                                    <p className="text-sm font-bold text-slate-400">{article.title}</p>
                                    <h2 className="mt-2 text-2xl font-black leading-tight text-slate-950 md:text-3xl">
                                        {selectedChapter.title}
                                    </h2>
                                </div>
                                <div className="mt-6 max-w-none [&_img]:my-6 [&_img]:max-h-[32rem] [&_img]:w-full [&_img]:rounded-2xl [&_img]:border [&_img]:border-slate-200 [&_img]:object-cover [&_img]:shadow-sm">
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        components={markdownComponents}
                                    >
                                        {selectedArticleChapter?.content || "暂无文章内容。"}
                                    </ReactMarkdown>
                                </div>
                            </div>
                        </article>

                        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                                <div>
                                    <p className="text-sm font-bold text-slate-900">
                                        下一步
                                    </p>
                                    <p className="mt-1 text-sm text-slate-500">
                                        标记本节后，继续阅读、小测或进入 AI 教练练习。
                                    </p>
                                </div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <Button
                                        className="rounded-full bg-slate-900 text-white"
                                        disabled={completingChapterId === selectedChapter.chapter_id}
                                        onClick={() => void completeCurrentChapter()}
                                    >
                                        {completingChapterId === selectedChapter.chapter_id ? "正在标记本节" : "完成本节"}
                                    </Button>
                                    {selectedLearningUnit.require_quiz ? (
                                        <Button
                                            variant="outline"
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
                                        <Button asChild className="rounded-full bg-slate-900 text-white">
                                            <Link href={examHref}>
                                                完成学习，进入考试
                                                <ArrowRight className="ml-2 h-4 w-4" />
                                            </Link>
                                        </Button>
                                    ) : null}
                                </div>
                            </div>
                            {!allUnitsCompleted ? (
                                <p className="mt-3 text-sm text-slate-500">完成要求阅读的小单元后开放考试入口。</p>
                            ) : null}
                            {selectedLearningUnit.require_quiz && !canStartSelectedUnitQuiz ? (
                                <p className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-500">
                                    先完成当前小单元的要求阅读，再进入小测。
                                </p>
                            ) : null}
                            {quizWorkflowError && !quiz ? (
                                <div role="alert" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-800">
                                    <p className="font-semibold text-amber-900">小测暂不可用</p>
                                    <p className="mt-1">{quizWorkflowError}</p>
                                </div>
                            ) : null}
                            {quiz ? (
                                <QuizPanel
                                    allUnitsCompleted={allUnitsCompleted}
                                    answers={quizAnswers}
                                    attempt={quizAttempt}
                                    attempts={quizAttempts}
                                    attemptsErrorMessage={quizAttemptsError}
                                    coachHref={coachHref}
                                    errorMessage={quizWorkflowError}
                                    examHref={examHref}
                                    isAttemptsLoading={isQuizAttemptsLoading}
                                    isReviewExpanded={isQuizReviewExpanded}
                                    isSubmitting={isQuizSubmitting}
                                    nextLearningUnitTitle={nextLearningUnit?.title ?? null}
                                    onAnswerChange={updateQuizAnswer}
                                    onContinueLearningUnit={continueToNextLearningUnit}
                                    onRetry={retryCurrentQuiz}
                                    onReviewRecommendedChapter={reviewRecommendedChapter}
                                    onSelectAttempt={selectQuizAttempt}
                                    onSubmit={() => void submitCurrentQuiz()}
                                    onToggleReview={() => setIsQuizReviewExpanded((current) => !current)}
                                    quiz={quiz}
                                    resultRef={quizResultRef}
                                />
                            ) : null}
                        </section>
                    </main>
                </div>
            ) : error ? null : (
                <GlassCard className="p-6 text-sm text-slate-500">当前商务礼仪训练包没有可用小单元，请管理员检查路径配置。</GlassCard>
            )}
        </div>
    );
}
