"use client";

import { useEffect, useState } from "react";
import { useParams, usePathname } from "next/navigation";

import { AdminDetailShell } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerQuizAnswer, SalesTrainerQuizAttempt } from "@/lib/api/types";

function stringifyAnswer(value: unknown): string {
    if (Array.isArray(value)) {
        return value.join("、");
    }
    if (typeof value === "boolean") {
        return value ? "正确" : "错误";
    }
    if (value === null || value === undefined || value === "") {
        return "未作答";
    }
    return String(value);
}

function stringifyCorrectAnswer(answer: SalesTrainerQuizAnswer): string {
    if (answer.question_type === "short_answer") {
        return answer.reference_answer || "--";
    }
    if (answer.correct_answer === null || answer.correct_answer === undefined || answer.correct_answer === "") {
        return "--";
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

function formatLearner(attempt: SalesTrainerQuizAttempt): string {
    const primary = attempt.user_name || attempt.user_email || attempt.user_id;
    const secondary = attempt.user_department || (
        attempt.user_email && attempt.user_email !== primary ? attempt.user_email : null
    );
    return secondary ? `${primary} · ${secondary}` : primary;
}

function hasPendingScore(attempt: SalesTrainerQuizAttempt): boolean {
    return attempt.total_score == null
        || attempt.max_score == null
        || attempt.answers.some((answer) => answer.is_correct == null || answer.score == null);
}

function getAttemptBadge(attempt: SalesTrainerQuizAttempt): {
    label: string;
    variant: "green" | "orange" | "secondary";
} {
    if (hasPendingScore(attempt)) {
        return { label: "待判分", variant: "orange" };
    }
    if (attempt.passed === true) {
        return { label: "通过", variant: "green" };
    }
    if (attempt.passed === false) {
        return { label: "未通过", variant: "secondary" };
    }
    return { label: "已计分", variant: "secondary" };
}

function getAnswerBadge(answer: SalesTrainerQuizAnswer): {
    label: string;
    variant: "green" | "orange" | "secondary";
} {
    if (answer.is_correct === true) {
        return { label: "正确", variant: "green" };
    }
    if (answer.is_correct === false) {
        return { label: "错误", variant: "secondary" };
    }
    return { label: "待判定", variant: "orange" };
}

export default function SalesTrainerQuizAttemptDetailPage() {
    const params = useParams<{ attemptId: string }>();
    const pathname = usePathname();
    const [attempt, setAttempt] = useState<SalesTrainerQuizAttempt | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function loadAttempt() {
            setIsLoading(true);
            setError(null);
            try {
                const result = await api.admin.salesTrainer.getQuizAttempt(params.attemptId);
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

    const badge = attempt ? getAttemptBadge(attempt) : null;

    return (
        <AdminDetailShell
            backHref="/admin/sales-trainer/score-results"
            title="做题结果详情"
            description="查看提交当时的题目、选项、学员答案、正确或参考答案、解析、得分和 AI 评分反馈快照。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
        >
            {isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载做题结果...</div>
            ) : !attempt ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error || "未找到做题结果。"}
                </div>
            ) : (
                <div className="space-y-6">
                    <GlassCard className="space-y-4 p-6">
                        <div className="flex flex-wrap items-center gap-2">
                            {badge ? <Badge variant={badge.variant}>{badge.label}</Badge> : null}
                            <Badge variant="outline">{attempt.status}</Badge>
                        </div>
                        <div className="grid gap-4 md:grid-cols-4">
                            <div>
                                <p className="text-xs text-slate-500">学员</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">{formatLearner(attempt)}</p>
                                <p className="mt-1 text-xs text-slate-400">{attempt.user_id}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">训练单元</p>
                                <p className="mt-1 text-sm text-slate-900">{attempt.unit_id}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">得分</p>
                                <p className="mt-1 text-2xl font-black text-slate-900">
                                    {attempt.total_score ?? "--"}
                                    <span className="text-base font-semibold text-slate-400"> / {attempt.max_score ?? "--"}</span>
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">提交时间</p>
                                <p className="mt-1 text-sm text-slate-900">{new Date(attempt.submitted_at).toLocaleString()}</p>
                            </div>
                        </div>
                    </GlassCard>

                    <div className="space-y-4">
                        {attempt.answers.map((answer, index) => {
                            const answerBadge = getAnswerBadge(answer);
                            return (
                                <GlassCard key={answer.answer_id} className="space-y-4 p-6">
                                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                        <div>
                                            <p className="text-xs font-semibold uppercase text-slate-400">
                                                第 {index + 1} 题 · {getQuestionTypeLabel(answer.question_type)}
                                            </p>
                                            <h2 className="mt-1 text-lg font-bold text-slate-900">
                                                {answer.question_title || `题目 ${answer.question_id}`}
                                            </h2>
                                        </div>
                                        <Badge variant={answerBadge.variant}>{answerBadge.label}</Badge>
                                    </div>

                                    {answer.question_stem ? (
                                        <p className="text-sm leading-6 text-slate-700">{answer.question_stem}</p>
                                    ) : null}

                                    {answer.options.length ? (
                                        <div className="grid gap-2 md:grid-cols-2">
                                            {answer.options.map((option) => (
                                                <div key={option.value} className="rounded-lg border border-slate-100 bg-white px-4 py-3 text-sm text-slate-700">
                                                    <span className="font-semibold text-slate-900">{option.value}.</span> {option.label}
                                                </div>
                                            ))}
                                        </div>
                                    ) : null}

                                    <div className="grid gap-3 md:grid-cols-3">
                                        <div className="rounded-lg bg-slate-50 px-4 py-3">
                                            <p className="text-xs text-slate-500">学员答案</p>
                                            <p className="mt-1 text-sm font-semibold text-slate-900">{stringifyAnswer(answer.answer_payload)}</p>
                                        </div>
                                        <div className="rounded-lg bg-slate-50 px-4 py-3">
                                            <p className="text-xs text-slate-500">{answer.question_type === "short_answer" ? "参考答案" : "正确答案"}</p>
                                            <p className="mt-1 text-sm font-semibold text-slate-900">
                                                {stringifyCorrectAnswer(answer)}
                                            </p>
                                        </div>
                                        <div className="rounded-lg bg-slate-50 px-4 py-3">
                                            <p className="text-xs text-slate-500">得分</p>
                                            <p className="mt-1 text-sm font-semibold text-slate-900">
                                                {answer.score ?? "--"}
                                                {answer.normalized_score != null ? ` · AI ${answer.normalized_score}` : ""}
                                            </p>
                                        </div>
                                    </div>

                                    {answer.scoring_feedback ? (
                                        <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
                                            {answer.scoring_feedback}
                                        </div>
                                    ) : null}
                                    {answer.explanation ? (
                                        <div className="rounded-lg border border-slate-100 bg-white px-4 py-3 text-sm leading-6 text-slate-700">
                                            <span className="font-semibold text-slate-900">解析：</span>
                                            {answer.explanation}
                                        </div>
                                    ) : null}
                                    {answer.scoring_reason ? (
                                        <p className="text-xs text-slate-500">评分依据：{answer.scoring_reason}</p>
                                    ) : null}
                                </GlassCard>
                            );
                        })}
                    </div>
                </div>
            )}
        </AdminDetailShell>
    );
}
