"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    NewcomerExamPaper,
    NewcomerPaperAttempt,
} from "@/lib/api/types";

import {
    BUSINESS_SKILLS_MODULE_KEY,
    BUSINESS_SKILLS_EXAM_GATE_COPY,
    businessSkillsArticleErrorMessage,
    fallbackPaperId,
    hasCompletedBusinessSkillsChapters,
    learningContentIdFromUnit,
    paperIdFromUnit,
    resolveBusinessSkillsUnit,
} from "../config";
import {
    answerPayload,
    type AnswersState,
    initialAnswer,
    QuestionField,
} from "./business-skills-exam-fields";

export default function BusinessSkillsExamPage() {
    const searchParams = useSearchParams();
    const unitId = searchParams.get("unitId");
    const [paper, setPaper] = useState<NewcomerExamPaper | null>(null);
    const [answers, setAnswers] = useState<AnswersState>({});
    const [attempt, setAttempt] = useState<NewcomerPaperAttempt | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [missingPaper, setMissingPaper] = useState(false);
    const [learningRequired, setLearningRequired] = useState(false);
    const learningHref = unitId
        ? `/sales-trainer/business-skills?unitId=${encodeURIComponent(unitId)}`
        : "/sales-trainer/business-skills";

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        setMissingPaper(false);
        setLearningRequired(false);
        try {
            const unitResponse = await api.salesTrainer.listUnits();
            const selectedUnit = resolveBusinessSkillsUnit(unitResponse.items, unitId);
            const paperId = paperIdFromUnit(selectedUnit) ?? fallbackPaperId(unitResponse.items);
            if (!paperId) {
                setPaper(null);
                setMissingPaper(true);
                return;
            }
            const learningContentId = learningContentIdFromUnit(selectedUnit);
            const article = await api.newcomerTraining.getModuleArticle(
                BUSINESS_SKILLS_MODULE_KEY,
                learningContentId ? { learning_content_id: learningContentId } : undefined,
            );
            if (!hasCompletedBusinessSkillsChapters(article.learning_content_id, article.chapters)) {
                setPaper(null);
                setLearningRequired(true);
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
        } catch (loadError) {
            setPaper(null);
            setError(businessSkillsArticleErrorMessage(loadError) || getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, [unitId]);

    useEffect(() => {
        void load();
    }, [load]);

    async function submitPaper() {
        if (!paper) {
            return;
        }
        setIsSubmitting(true);
        setError(null);
        try {
            const result = await api.newcomerTraining.submitPaperAttempt({
                paper_id: paper.paper_id,
                answers: paper.questions.map((question) => ({
                    question_id: question.question_id,
                    answer_payload: answerPayload(question, answers),
                })),
            });
            setAttempt(result);
        } catch (submitError) {
            setError(getApiErrorMessage(submitError));
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <div className="space-y-6 pb-20">
            <Link
                href={learningHref}
                className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
            >
                <ArrowLeft className="h-4 w-4" />
                返回商务技巧学习
            </Link>

            <div>
                <h1 className="text-3xl font-black tracking-tight text-slate-900">商务技巧考试</h1>
                <p className="mt-1 text-sm text-slate-500">完成学习后提交商务技巧考卷。</p>
            </div>

            {error ? <GlassCard className="p-4 text-sm font-medium text-red-700">{error}</GlassCard> : null}

            {isLoading ? (
                <div className="h-48 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
            ) : (
                <GlassCard className="mx-auto max-w-3xl space-y-5 p-6">
                    {missingPaper ? (
                        <div className="space-y-2">
                            <h2 className="text-lg font-bold text-slate-900">暂未绑定商务技巧考卷</h2>
                            <p className="text-sm text-slate-500">
                                请管理员到 新人训练路径配置中心 → 商务技巧 → 考卷管理 绑定已发布考卷。
                            </p>
                        </div>
                    ) : learningRequired ? (
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <h2 className="text-lg font-bold text-slate-900">{BUSINESS_SKILLS_EXAM_GATE_COPY.title}</h2>
                                <p className="text-sm text-slate-500">
                                    {BUSINESS_SKILLS_EXAM_GATE_COPY.description}
                                </p>
                            </div>
                            <Button asChild className="rounded-full bg-slate-900 text-white">
                                <Link href={learningHref}>
                                    {BUSINESS_SKILLS_EXAM_GATE_COPY.actionLabel}
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
                            <Button className="w-full rounded-full bg-slate-900 text-white" onClick={() => void submitPaper()} disabled={isSubmitting}>
                                提交考卷
                            </Button>
                            {attempt ? (
                                <p className="text-sm font-medium text-emerald-700">
                                    已提交：{attempt.total_score ?? "--"}/{attempt.max_score ?? "--"}
                                </p>
                            ) : null}
                        </>
                    ) : null}
                </GlassCard>
            )}
        </div>
    );
}
