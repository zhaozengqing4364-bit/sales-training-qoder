import type { SalesTrainerQuestion } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";

export function PaperQuestionPicker({
    isLoading,
    questions,
    selectedQuestionIds,
    toggleQuestion,
}: {
    readonly isLoading: boolean;
    readonly questions: readonly SalesTrainerQuestion[];
    readonly selectedQuestionIds: readonly string[];
    readonly toggleQuestion: (questionId: string) => void;
}) {
    return (
        <GlassCard className="space-y-4 p-6">
            <div>
                <h2 className="text-lg font-bold text-slate-900">选择题目</h2>
                <p className="mt-1 text-sm text-slate-500">只显示已发布且属于新人训练路径范围的题目。</p>
            </div>
            {isLoading ? (
                <div className="rounded-2xl bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">正在加载题目...</div>
            ) : questions.length === 0 ? (
                <div className="rounded-2xl bg-amber-50 px-4 py-8 text-center text-sm text-amber-700">
                    暂无可组卷题目，请先到正式题目库发布题目。
                </div>
            ) : (
                <div className="grid gap-3">
                    {questions.map((question) => (
                        <label key={question.question_id} className="flex gap-3 rounded-2xl border border-slate-100 bg-white px-4 py-3">
                            <input
                                type="checkbox"
                                checked={selectedQuestionIds.includes(question.question_id)}
                                onChange={() => toggleQuestion(question.question_id)}
                            />
                            <span>
                                <span className="block font-medium text-slate-900">{question.title}</span>
                                <span className="mt-1 block text-sm text-slate-500">{question.stem}</span>
                            </span>
                        </label>
                    ))}
                </div>
            )}
        </GlassCard>
    );
}
