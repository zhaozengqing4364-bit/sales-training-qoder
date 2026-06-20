"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/lib/api/client";
import type {
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
    BUSINESS_SKILLS_MODULE_KEY,
    businessSkillsArticleErrorMessage,
    businessSkillsExamHref,
    learningContentIdFromUnit,
    resolveBusinessSkillsUnit,
} from "./config";

type BusinessSkillsWorkbenchInput = {
    readonly requestedLearningUnitKey: string | null;
    readonly unitId: string | null;
};

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

export function useBusinessSkillsWorkbench({
    requestedLearningUnitKey,
    unitId,
}: BusinessSkillsWorkbenchInput) {
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
        if (!selectedLearningUnit || !canStartSelectedUnitQuiz || isQuizLoading) {
            return;
        }
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
        if (!selectedLearningUnit || !quiz || isQuizSubmitting) {
            return;
        }
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

    return {
        allUnitsCompleted,
        article,
        canStartSelectedUnitQuiz,
        coachHref,
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
    };
}
