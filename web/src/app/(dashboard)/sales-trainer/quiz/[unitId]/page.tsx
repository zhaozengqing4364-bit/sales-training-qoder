"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { generateClientToken } from "@/lib/sales-trainer/idempotency";
import type {
    SalesTrainerQuestionOption,
    SalesTrainerQuizAttemptCreateRequest,
    SalesTrainerUnit,
} from "@/lib/api/types";

function resolveQuestionOptions(options: unknown): SalesTrainerQuestionOption[] {
    if (!Array.isArray(options)) {
        return [];
    }
    return options.map((option, index) => {
        if (typeof option === "string") {
            return { label: option, value: option };
        }
        if (option && typeof option === "object") {
            const raw = option as Record<string, unknown>;
            const value = typeof raw.value === "string" ? raw.value : String(raw.value ?? index);
            const label = typeof raw.label === "string"
                ? raw.label
                : typeof raw.text === "string"
                    ? raw.text
                    : value;
            return { label, value };
        }
        return { label: String(option), value: String(option) };
    });
}

function getDefaultAnswer(questionType: SalesTrainerUnit["questions"][number]["question_type"]): unknown {
    if (questionType === "multiple_choice") {
        return [];
    }
    return "";
}

export default function SalesTrainerQuizPage() {
    const params = useParams<{ unitId: string }>();
    const router = useRouter();
    const [unit, setUnit] = useState<SalesTrainerUnit | null>(null);
    const [answers, setAnswers] = useState<Record<string, unknown>>({});
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function loadUnit() {
            setIsLoading(true);
            setError(null);
            try {
                const result = await api.salesTrainer.getUnit(params.unitId);
                setUnit(result);
            } catch (loadError) {
                setUnit(null);
                setError(getApiErrorMessage(loadError));
            } finally {
                setIsLoading(false);
            }
        }
        void loadUnit();
    }, [params.unitId]);

    const orderedQuestions = useMemo(
        () => [...(unit?.questions ?? [])].sort((left, right) => left.order_index - right.order_index),
        [unit],
    );

    function updateAnswer(questionId: string, value: unknown) {
        setAnswers((current) => ({ ...current, [questionId]: value }));
    }

    async function handleSubmit() {
        if (!unit) {
            return;
        }
        setIsSubmitting(true);
        setError(null);
        try {
            const payload: SalesTrainerQuizAttemptCreateRequest = {
                unit_id: unit.unit_id,
                answers: orderedQuestions.map((question) => ({
                    question_id: question.question_id,
                    answer_payload: answers[question.question_id] ?? getDefaultAnswer(question.question_type),
                })),
                // 幂等键：同一提交流程内生成一次，重复提交返回已存在 attempt。
                client_token: generateClientToken(),
            };
            const result = await api.salesTrainer.submitQuizAttempt(payload);
            router.push(`/sales-trainer/quiz/result/${result.attempt_id}`);
        } catch (submitError) {
            setError(getApiErrorMessage(submitError));
            setIsSubmitting(false);
        }
    }

    if (isLoading) {
        return <div className="py-12 text-center text-sm text-slate-500">正在加载训练单元...</div>;
    }

    if (!unit || unit.unit_type !== "quiz") {
        return (
            <GlassCard className="space-y-4 p-6">
                <p className="text-sm text-red-700">{error || "该训练单元不存在，或不是做题训练。"}</p>
                <Button asChild className="rounded-full">
                    <Link href="/sales-trainer">返回新人训练路径</Link>
                </Button>
            </GlassCard>
        );
    }

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
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">{unit.name}</h1>
                    <p className="mt-1 text-sm text-slate-500">
                        {unit.description || `共 ${orderedQuestions.length} 题，请按顺序完成本次做题训练。`}
                    </p>
                </div>
            </div>

            <div className="space-y-4">
                {orderedQuestions.map((question, index) => {
                    const questionOptions = resolveQuestionOptions((question as { options?: unknown }).options);
                    const currentValue = answers[question.question_id];
                    return (
                        <GlassCard key={question.question_id} className="space-y-4 p-6">
                            <div>
                                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                                    第 {index + 1} 题 · {question.points} 分
                                </p>
                                <h2 className="mt-1 text-lg font-bold text-slate-900">{question.title}</h2>
                                <p className="mt-2 text-sm text-slate-600">{question.stem}</p>
                            </div>

                            {question.question_type === "single_choice" ? (
                                <div className="space-y-2">
                                    {questionOptions.map((option) => (
                                        <label key={option.value} className="flex items-center gap-3 rounded-2xl border border-slate-100 bg-white px-4 py-3 text-sm text-slate-700">
                                            <input
                                                type="radio"
                                                name={question.question_id}
                                                checked={currentValue === option.value}
                                                onChange={() => updateAnswer(question.question_id, option.value)}
                                            />
                                            {option.label}
                                        </label>
                                    ))}
                                </div>
                            ) : null}

                            {question.question_type === "multiple_choice" ? (
                                <div className="space-y-2">
                                    {questionOptions.map((option) => {
                                        const selectedValues = Array.isArray(currentValue) ? currentValue : [];
                                        const isChecked = selectedValues.includes(option.value);
                                        return (
                                            <label key={option.value} className="flex items-center gap-3 rounded-2xl border border-slate-100 bg-white px-4 py-3 text-sm text-slate-700">
                                                <input
                                                    type="checkbox"
                                                    checked={isChecked}
                                                    onChange={(event) => {
                                                        const nextValues = new Set(selectedValues.map((item) => String(item)));
                                                        if (event.target.checked) {
                                                            nextValues.add(option.value);
                                                        } else {
                                                            nextValues.delete(option.value);
                                                        }
                                                        updateAnswer(question.question_id, Array.from(nextValues));
                                                    }}
                                                />
                                                {option.label}
                                            </label>
                                        );
                                    })}
                                </div>
                            ) : null}

                            {question.question_type === "true_false" ? (
                                <div className="space-y-2">
                                    {[
                                        { label: "正确", value: "true" },
                                        { label: "错误", value: "false" },
                                    ].map((option) => (
                                        <label key={option.value} className="flex items-center gap-3 rounded-2xl border border-slate-100 bg-white px-4 py-3 text-sm text-slate-700">
                                            <input
                                                type="radio"
                                                name={question.question_id}
                                                checked={currentValue === option.value}
                                                onChange={() => updateAnswer(question.question_id, option.value)}
                                            />
                                            {option.label}
                                        </label>
                                    ))}
                                </div>
                            ) : null}

                            {question.question_type === "short_answer" ? (
                                <textarea
                                    value={typeof currentValue === "string" ? currentValue : ""}
                                    onChange={(event) => updateAnswer(question.question_id, event.target.value)}
                                    rows={5}
                                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                                    placeholder="输入你的答案"
                                />
                            ) : null}
                        </GlassCard>
                    );
                })}
            </div>

            {error ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                </div>
            ) : null}

            <div className="flex justify-end">
                <Button
                    className="rounded-full bg-slate-900 text-white"
                    onClick={() => void handleSubmit()}
                    disabled={isSubmitting}
                >
                    {isSubmitting ? "提交中..." : "提交答案"}
                </Button>
            </div>
        </div>
    );
}
