"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerQuizAnswer, SalesTrainerQuizAttempt } from "@/lib/api/types";
import { SalesTrainerNextStepPanel } from "../../../next-step-panel";

function stringifyAnswer(value: unknown): string {
    if (Array.isArray(value)) {
        return value.join("、");
    }
    if (typeof value === "boolean") {
        return value ? "true" : "false";
    }
    if (value === null || value === undefined || value === "") {
        return "未作答";
    }
    return String(value);
}

function stringifyCorrectAnswer(answer: SalesTrainerQuizAnswer): string {
    if (answer.question_type === "true_false") {
        return answer.correct_answer === true ? "正确" : answer.correct_answer === false ? "错误" : "--";
    }
    return stringifyAnswer(answer.correct_answer);
}

function getQuestionTypeLabel(type: SalesTrainerQuizAnswer["question_type"]): string {
    const labels: Record<SalesTrainerQuizAnswer["question_type"], string> = {
        single_choice: "单选题",
        multiple_choice: "多选题",
        true_false: "判断题",
        short_answer: "简答题",
    };
    return labels[type] ?? type;
}

function hasPendingScore(attempt: SalesTrainerQuizAttempt): boolean {
    return attempt.total_score == null
        || attempt.max_score == null
        || attempt.answers.some((answer) => answer.is_correct == null || answer.score == null);
}

function getAttemptResultBadge(attempt: SalesTrainerQuizAttempt): {
    label: string;
    className: string;
} {
    if (hasPendingScore(attempt)) {
        return { label: "待判分", className: "bg-amber-100 text-amber-700" };
    }
    if (attempt.passed === true) {
        return { label: "已通过", className: "bg-emerald-100 text-emerald-700" };
    }
    if (attempt.passed === false) {
        return { label: "未通过", className: "bg-slate-100 text-slate-700" };
    }
    return { label: "仅计分", className: "bg-blue-100 text-blue-700" };
}

export default function SalesTrainerQuizResultPage() {
    const params = useParams<{ attemptId: string }>();
    const [attempt, setAttempt] = useState<SalesTrainerQuizAttempt | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function loadAttempt() {
            setIsLoading(true);
            setError(null);
            try {
                const result = await api.salesTrainer.getQuizAttempt(params.attemptId);
                setAttempt(result);
            } catch (loadError) {
                setAttempt(null);
                setError(getApiErrorMessage(loadError));
            } finally {
                setIsLoading(false);
            }
        }
        void loadAttempt();
    }, [params.attemptId]);

    if (isLoading) {
        return <div className="py-12 text-center text-sm text-slate-500">正在加载做题结果...</div>;
    }

    if (!attempt) {
        return (
            <GlassCard className="space-y-4 p-6">
                <p className="text-sm text-red-700">{error || "做题结果不存在。"}</p>
                <Button asChild className="rounded-full">
                    <Link href="/sales-trainer">返回新人训练路径</Link>
                </Button>
            </GlassCard>
        );
    }

    const resultBadge = getAttemptResultBadge(attempt);

    return (
        <div className="space-y-6 pb-20">
            <div className="space-y-4">
                <Link
                    href="/sales-trainer"
                    className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
                >
                    <ArrowLeft className="h-4 w-4" />
                    返回新人训练路径
                </Link>
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                        <h1 className="text-3xl font-black tracking-tight text-slate-900">做题结果</h1>
                        <p className="mt-1 text-sm text-slate-500">提交时间：{new Date(attempt.submitted_at).toLocaleString()}</p>
                    </div>
                    <Badge className={resultBadge.className}>
                        {resultBadge.label}
                    </Badge>
                </div>
            </div>

            <GlassCard className="grid gap-4 p-6 md:grid-cols-3">
                <div>
                    <p className="text-xs text-slate-500">总分</p>
                    <p className="mt-1 text-2xl font-black text-slate-900">{attempt.total_score ?? "--"}</p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">满分</p>
                    <p className="mt-1 text-2xl font-black text-slate-900">{attempt.max_score ?? "--"}</p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">状态</p>
                    <p className="mt-1 text-2xl font-black text-slate-900">{attempt.status}</p>
                </div>
            </GlassCard>

            <SalesTrainerNextStepPanel unitId={attempt.unit_id} />

            <div className="space-y-4">
                {attempt.answers.map((answer, index) => (
                    <GlassCard key={answer.answer_id} className="space-y-4 p-6">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                                    第 {index + 1} 题 · {getQuestionTypeLabel(answer.question_type)}
                                </p>
                                <h2 className="mt-1 text-lg font-bold text-slate-900">
                                    {answer.question_title || `题目 ${answer.question_id}`}
                                </h2>
                            </div>
                            <Badge className={answer.is_correct ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-700"}>
                                {answer.is_correct === null ? "待人工判定" : answer.is_correct ? "正确" : "错误"}
                            </Badge>
                        </div>
                        {answer.question_stem ? (
                            <p className="text-sm leading-6 text-slate-700">{answer.question_stem}</p>
                        ) : null}
                        {answer.options.length ? (
                            <div className="grid gap-2 md:grid-cols-2">
                                {answer.options.map((option) => (
                                    <div key={option.value} className="rounded-2xl border border-slate-100 bg-white px-4 py-3 text-sm text-slate-700">
                                        <span className="font-semibold text-slate-900">{option.value}.</span> {option.label}
                                    </div>
                                ))}
                            </div>
                        ) : null}
                        <div className="grid gap-3 md:grid-cols-3">
                            <div className="rounded-2xl bg-slate-50 px-4 py-3">
                                <p className="text-xs text-slate-500">我的答案</p>
                                <p className="mt-1 text-sm font-semibold text-slate-900">{stringifyAnswer(answer.answer_payload)}</p>
                            </div>
                            <div className="rounded-2xl bg-slate-50 px-4 py-3">
                                <p className="text-xs text-slate-500">{answer.question_type === "short_answer" ? "参考答案" : "正确答案"}</p>
                                <p className="mt-1 text-sm font-semibold text-slate-900">
                                    {answer.question_type === "short_answer" ? (answer.reference_answer || "--") : stringifyCorrectAnswer(answer)}
                                </p>
                            </div>
                            <div className="rounded-2xl bg-slate-50 px-4 py-3">
                                <p className="text-xs text-slate-500">得分</p>
                                <p className="mt-1 text-sm font-semibold text-slate-900">
                                    {answer.score ?? "--"}
                                    {answer.normalized_score != null ? ` · AI ${answer.normalized_score}` : ""}
                                </p>
                            </div>
                        </div>
                        {answer.scoring_feedback ? (
                            <div className="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
                                {answer.scoring_feedback}
                            </div>
                        ) : null}
                        {answer.explanation ? (
                            <div className="rounded-2xl border border-slate-100 bg-white px-4 py-3 text-sm leading-6 text-slate-700">
                                <span className="font-semibold text-slate-900">解析：</span>
                                {answer.explanation}
                            </div>
                        ) : null}
                        {answer.scoring_reason ? (
                            <p className="text-xs text-slate-500">评分依据：{answer.scoring_reason}</p>
                        ) : null}
                    </GlassCard>
                ))}
            </div>
        </div>
    );
}
