"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { generateClientToken } from "@/lib/sales-trainer/idempotency";
import type { NewcomerExamPaper } from "@/lib/api/types";

import {
    BUSINESS_SKILLS_ACTIVE_UNIT_MISSING_MESSAGE,
    BUSINESS_SKILLS_ACTIVE_UNIT_NOT_FOUND_MESSAGE,
    BUSINESS_SKILLS_EXAM_COPY,
    BUSINESS_SKILLS_MODULE_KEY,
    businessSkillsArticleErrorMessage,
    findBusinessSkillsModuleFromJourney,
    learningContentIdFromJourneyModule,
    paperIdFromJourneyModule,
    resolveBusinessSkillsUnit,
    unitIdFromJourneyModule,
} from "../config";
import {
    answerPayload,
    type AnswersState,
    initialAnswer,
    isQuestionAnswered,
    QuestionField,
} from "./business-skills-exam-fields";

export default function BusinessSkillsExamPage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const unitId = searchParams.get("unitId");
    const [activeUnitId, setActiveUnitId] = useState<string | null>(unitId);
    const [paper, setPaper] = useState<NewcomerExamPaper | null>(null);
    const [answers, setAnswers] = useState<AnswersState>({});
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [missingPaper, setMissingPaper] = useState(false);
    const [learningRequired, setLearningRequired] = useState(false);
    const [learningMismatch, setLearningMismatch] = useState(false);
    const learningHref = activeUnitId
        ? `/sales-trainer/business-skills?unitId=${encodeURIComponent(activeUnitId)}`
        : "/sales-trainer/business-skills";

    useEffect(() => {
        let isActive = true;
        void Promise.all([
            api.salesTrainer.listUnits(),
            api.salesTrainer.getJourney(),
        ])
            .then(async ([unitResponse, journeyResponse]) => {
                const activeModule = findBusinessSkillsModuleFromJourney(journeyResponse.modules, unitId);
                const nextActiveUnitId = unitIdFromJourneyModule(activeModule);
                if (!activeModule || !nextActiveUnitId) {
                    throw new Error(BUSINESS_SKILLS_ACTIVE_UNIT_MISSING_MESSAGE);
                }
                const selectedUnit = resolveBusinessSkillsUnit(unitResponse.items, nextActiveUnitId);
                if (nextActiveUnitId && !selectedUnit) {
                    throw new Error(BUSINESS_SKILLS_ACTIVE_UNIT_NOT_FOUND_MESSAGE);
                }
                const paperId = paperIdFromJourneyModule(activeModule);
                if (!paperId) {
                    if (!isActive) {
                        return;
                    }
                    setActiveUnitId(nextActiveUnitId);
                    setPaper(null);
                    setMissingPaper(true);
                    setLearningRequired(false);
                    setLearningMismatch(false);
                    setError(null);
                    return;
                }
                const learningContentId = learningContentIdFromJourneyModule(activeModule);
                const [nextArticle, progress] = await Promise.all([
                    api.newcomerTraining.getModuleArticle(
                        BUSINESS_SKILLS_MODULE_KEY,
                        learningContentId ? { learning_content_id: learningContentId } : undefined,
                    ),
                    api.newcomerTraining.getModuleArticleProgress(BUSINESS_SKILLS_MODULE_KEY),
                ]);
                if (!isActive) {
                    return;
                }
                setActiveUnitId(nextActiveUnitId);
                // 后端 gate: 进度完成 && learning_content_id 与文章匹配
                if (!progress.is_completed) {
                    setPaper(null);
                    setMissingPaper(false);
                    setLearningRequired(true);
                    setLearningMismatch(false);
                    setError(null);
                    return;
                }
                if (
                    nextArticle.learning_content_id
                    && progress.learning_content_id
                    && nextArticle.learning_content_id !== progress.learning_content_id
                ) {
                    setPaper(null);
                    setMissingPaper(false);
                    setLearningRequired(false);
                    setLearningMismatch(true);
                    setError(null);
                    return;
                }
                const nextPaper = await api.newcomerTraining.getPaper(paperId);
                setPaper(nextPaper);
                setAnswers(Object.fromEntries(
                    nextPaper.questions.map((question) => [
                        question.question_id,
                        initialAnswer(question),
                    ]),
                ));
                setMissingPaper(false);
                setLearningRequired(false);
                setLearningMismatch(false);
                setError(null);
            }).catch((loadError) => {
                if (!isActive) {
                    return;
                }
                setPaper(null);
                setError(businessSkillsArticleErrorMessage(loadError) || getApiErrorMessage(loadError));
            }).finally(() => {
                if (isActive) {
                    setIsLoading(false);
                }
            });
        return () => {
            isActive = false;
        };
    }, [unitId]);

    async function submitPaper() {
        if (!paper) {
            return;
        }
        const hasAnsweredAllQuestions = paper.questions.every((question) => isQuestionAnswered(question, answers));
        if (!hasAnsweredAllQuestions) {
            setError(BUSINESS_SKILLS_EXAM_COPY.incompleteAnswerError);
            return;
        }
        setIsSubmitting(true);
        setError(null);
        try {
            const result = await api.newcomerTraining.submitPaperAttempt({
                paper_id: paper.paper_id,
                // 幂等键：同一提交流程内生成一次，重复提交返回已存在 attempt。
                client_token: generateClientToken(),
                answers: paper.questions.map((question) => ({
                    question_id: question.question_id,
                    answer_payload: answerPayload(question, answers),
                })),
            });
            router.push(`/sales-trainer/quiz/result/${result.attempt_id}`);
        } catch (submitError) {
            setError(getApiErrorMessage(submitError));
            setIsSubmitting(false);
        }
    }

    const showLearningGate = learningRequired || learningMismatch;
    const canSubmitPaper = paper?.questions.every((question) => isQuestionAnswered(question, answers)) ?? false;
    const gateCopy = learningMismatch
        ? {
            title: BUSINESS_SKILLS_EXAM_COPY.learningMismatchTitle,
            description: BUSINESS_SKILLS_EXAM_COPY.learningMismatchDescription,
            actionLabel: BUSINESS_SKILLS_EXAM_COPY.learningGateActionLabel,
        }
        : {
            title: BUSINESS_SKILLS_EXAM_COPY.learningGateTitle,
            description: BUSINESS_SKILLS_EXAM_COPY.learningGateDescription,
            actionLabel: BUSINESS_SKILLS_EXAM_COPY.learningGateActionLabel,
        };

    return (
        <div className="space-y-6 pb-20">
            <Link
                href={learningHref}
                className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
            >
                <ArrowLeft className="h-4 w-4" />
                {BUSINESS_SKILLS_EXAM_COPY.backLink}
            </Link>

            <div>
                <h1 className="text-3xl font-black tracking-tight text-slate-900">
                    {BUSINESS_SKILLS_EXAM_COPY.pageTitle}
                </h1>
                <p className="mt-1 text-sm text-slate-500">
                    {BUSINESS_SKILLS_EXAM_COPY.pageSubtitle}
                </p>
            </div>

            {error ? <GlassCard className="p-4 text-sm font-medium text-red-700">{error}</GlassCard> : null}

            {isLoading ? (
                <div className="h-48 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
            ) : (
                <GlassCard className="mx-auto max-w-3xl space-y-5 p-6">
                    {missingPaper ? (
                        <div className="space-y-2">
                            <h2 className="text-lg font-bold text-slate-900">
                                {BUSINESS_SKILLS_EXAM_COPY.paperMissingTitle}
                            </h2>
                            <p className="text-sm text-slate-500">
                                {BUSINESS_SKILLS_EXAM_COPY.paperMissingDescription}
                            </p>
                        </div>
                    ) : showLearningGate ? (
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <h2 className="text-lg font-bold text-slate-900">{gateCopy.title}</h2>
                                <p className="text-sm text-slate-500">
                                    {gateCopy.description}
                                </p>
                            </div>
                            <Button asChild className="rounded-full bg-slate-900 text-white">
                                <Link href={learningHref}>
                                    {gateCopy.actionLabel}
                                </Link>
                            </Button>
                        </div>
                    ) : paper ? (
                        <>
                            <div>
                                <h2 className="text-xl font-black text-slate-900">{paper.title}</h2>
                                <p className="mt-1 text-xs text-slate-500">共 {paper.questions.length} 道题</p>
                            </div>
                            <div className="space-y-5">
                                {paper.questions.map((question) => (
                                    <div key={question.question_id} className="space-y-3 rounded-2xl border border-slate-100 p-4">
                                        <p className="text-sm font-semibold text-slate-900">{question.order_index}. {question.stem}</p>
                                        <QuestionField
                                            question={question}
                                            value={answerPayload(question, answers)}
                                            onChange={(value) => setAnswers((current) => ({ ...current, [question.question_id]: value }))}
                                        />
                                    </div>
                                ))}
                            </div>
                            <Button
                                className="w-full rounded-full bg-slate-900 text-white"
                                onClick={() => void submitPaper()}
                                disabled={isSubmitting || !canSubmitPaper}
                            >
                                {BUSINESS_SKILLS_EXAM_COPY.submitButton}
                            </Button>
                            {!canSubmitPaper ? (
                                <p className="text-center text-xs font-medium text-slate-500">
                                    {BUSINESS_SKILLS_EXAM_COPY.incompleteAnswerHint}
                                </p>
                            ) : null}
                        </>
                    ) : null}
                </GlassCard>
            )}
        </div>
    );
}
