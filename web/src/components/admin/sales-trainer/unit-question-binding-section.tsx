"use client";

import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import type {
    QuestionItem,
    SalesTrainerQuestion,
    SalesTrainerUnitQuestionBinding,
} from "@/lib/api/types";

type QuestionSelection = SalesTrainerUnitQuestionBinding;

interface UnitQuestionBindingSectionProps {
    readonly availableQuestions: readonly (QuestionItem | SalesTrainerQuestion)[];
    readonly canEdit: boolean;
    readonly isSubmitting: boolean;
    readonly selectedQuestionIds: ReadonlySet<string>;
    readonly selectedQuestions: readonly QuestionSelection[];
    readonly toggleQuestion: (questionId: string) => void;
    readonly updateQuestionPoints: (questionId: string, value: string) => void;
}

export function UnitQuestionBindingSection({
    availableQuestions,
    canEdit,
    isSubmitting,
    selectedQuestionIds,
    selectedQuestions,
    toggleQuestion,
    updateQuestionPoints,
}: UnitQuestionBindingSectionProps) {
    return (
        <GlassCard className="space-y-4 p-6">
            <div>
                <h2 className="text-lg font-bold text-slate-900">绑定题目</h2>
                <p className="mt-1 text-sm text-slate-500">
                    列表页不内嵌编辑，本页只负责选择已发布题目并设置分值。
                </p>
            </div>
            <div className="space-y-3">
                {availableQuestions.length === 0 ? (
                    <p className="text-sm text-slate-500">暂无已发布题目。</p>
                ) : availableQuestions.map((question) => {
                    const selectedQuestion = selectedQuestions.find(
                        (item) => item.question_id === question.question_id,
                    );
                    return (
                        <div
                            key={question.question_id}
                            className="rounded-2xl border border-slate-100 bg-white p-4"
                        >
                            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                <label className="flex items-start gap-3 text-sm text-slate-700">
                                    <input
                                        type="checkbox"
                                        checked={selectedQuestionIds.has(question.question_id)}
                                        onChange={() => toggleQuestion(question.question_id)}
                                        disabled={isSubmitting || !canEdit}
                                    />
                                    <span>
                                        <span className="block font-semibold text-slate-900">
                                            {question.title}
                                        </span>
                                        <span className="mt-1 block text-slate-500">
                                            {question.stem}
                                        </span>
                                    </span>
                                </label>
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-slate-500">分值</span>
                                    <Input
                                        type="number"
                                        min={1}
                                        value={selectedQuestion?.points ?? 10}
                                        onChange={(event) => updateQuestionPoints(question.question_id, event.target.value)}
                                        disabled={!selectedQuestion || isSubmitting || !canEdit}
                                        className="w-24"
                                    />
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </GlassCard>
    );
}
