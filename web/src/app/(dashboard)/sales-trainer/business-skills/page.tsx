"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowLeft, ArrowRight, BookOpen, CheckCircle2 } from "lucide-react";

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
    chapterDisplayLabel,
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
                            {chapterDisplayLabel(index)} {chapter.title}
                        </span>
                    </button>
                );
            })}
        </nav>
    );
}

function QuizPanel({
    answers,
    attempt,
    errorMessage,
    isSubmitting,
    onAnswerChange,
    onSubmit,
    quiz,
}: {
    readonly answers: Record<string, string | string[]>;
    readonly attempt: BusinessEtiquetteUnitQuizAttempt | null;
    readonly errorMessage: string | null;
    readonly isSubmitting: boolean;
    readonly onAnswerChange: (question: BusinessEtiquetteQuizQuestion, value: string, checked?: boolean) => void;
    readonly onSubmit: () => void;
    readonly quiz: BusinessEtiquetteUnitQuiz;
}) {
    const hasQuestions = quiz.questions.length > 0;

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
            {hasQuestions ? (
                <div className="space-y-3">
                    {quiz.questions.map((question) => (
                        <div key={question.question_id} className="rounded-xl bg-white p-4">
                            <p className="text-sm font-semibold text-slate-400">
                                {question.order_index}. {question.question_type === "short_answer" ? "简答题" : question.question_type === "multiple_choice" ? "多选题" : "单选题"}
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
            ) : (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-relaxed text-amber-800">
                    当前小单元还没有可用题目，请联系管理员检查题库和考卷绑定。
                </div>
            )}
            <Button
                className="rounded-full bg-slate-900 text-white"
                disabled={isSubmitting || !hasQuestions}
                onClick={onSubmit}
            >
                {isSubmitting ? "正在提交小测" : "提交小测"}
            </Button>
            {attempt ? (
                <div className="rounded-2xl bg-white p-4">
                    <p className="font-black text-slate-900">
                        {attempt.passed ? "小测已达标" : "小测未达标"}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                        得分 {attempt.total_score ?? "-"} / {attempt.max_score ?? "-"}
                    </p>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {attempt.capability_scores.map((capability) => (
                            <div key={capability.capability_key} className="rounded-xl border border-slate-100 px-3 py-2 text-sm">
                                <p className="font-semibold text-slate-900">{capability.display_name}</p>
                                <p className="text-slate-500">
                                    {capability.normalized_score === null ? "待评分" : `${Math.round(capability.normalized_score)} 分`}
                                    {capability.mastery_level_name ? ` · ${capability.mastery_level_name}` : ""}
                                </p>
                            </div>
                        ))}
                    </div>
                    {!attempt.passed && attempt.recommended_chapter_orders.length ? (
                        <p className="mt-3 text-sm text-slate-500">
                            建议回看第 {attempt.recommended_chapter_orders.join("、")} 章。
                        </p>
                    ) : null}
                </div>
            ) : null}
        </div>
    );
}

export default function BusinessSkillsPage() {
    const searchParams = useSearchParams();
    const unitId = searchParams.get("unitId");
    const requestedLearningUnitKey = searchParams.get("learningUnit");
    const [units, setUnits] = useState<SalesTrainerUnit[]>([]);
    const [article, setArticle] = useState<NewcomerArticle | null>(null);
    const [learningUnits, setLearningUnits] = useState<BusinessEtiquetteLearningUnit[]>([]);
    const [selectedLearningUnitKey, setSelectedLearningUnitKey] = useState<string | null>(null);
    const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null);
    const [coachHref, setCoachHref] = useState<string | null>(null);
    const [quiz, setQuiz] = useState<BusinessEtiquetteUnitQuiz | null>(null);
    const [quizAttempt, setQuizAttempt] = useState<BusinessEtiquetteUnitQuizAttempt | null>(null);
    const [quizAnswers, setQuizAnswers] = useState<Record<string, string | string[]>>({});
    const [isLoading, setIsLoading] = useState(true);
    const [isQuizLoading, setIsQuizLoading] = useState(false);
    const [isQuizSubmitting, setIsQuizSubmitting] = useState(false);
    const [completingChapterId, setCompletingChapterId] = useState<string | null>(null);
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
        setQuizAnswers({});
        setQuizWorkflowError(null);
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
            setQuizAnswers({});
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
                                    answers={quizAnswers}
                                    attempt={quizAttempt}
                                    errorMessage={quizWorkflowError}
                                    isSubmitting={isQuizSubmitting}
                                    onAnswerChange={updateQuizAnswer}
                                    onSubmit={() => void submitCurrentQuiz()}
                                    quiz={quiz}
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
