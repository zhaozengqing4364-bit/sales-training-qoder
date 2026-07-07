import type {
    NewcomerExamPaperQuestion,
    SalesTrainerQuestionOption,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

const TRUE_FALSE_OPTIONS: readonly SalesTrainerQuestionOption[] = [
    { value: "true", label: "正确" },
    { value: "false", label: "错误" },
];

export type AnswersState = Record<string, unknown>;

export function answerPayload(question: NewcomerExamPaperQuestion, answers: AnswersState): unknown {
    return answers[question.question_id] ?? (question.question_type === "multiple_choice" ? [] : "");
}

function choiceOptions(question: NewcomerExamPaperQuestion): readonly SalesTrainerQuestionOption[] {
    if (question.question_type === "true_false") {
        return TRUE_FALSE_OPTIONS;
    }
    return question.options ?? [];
}

export function initialAnswer(question: NewcomerExamPaperQuestion): unknown {
    if (question.question_type === "multiple_choice") {
        return [];
    }
    return "";
}

export function isQuestionAnswered(question: NewcomerExamPaperQuestion, answers: AnswersState): boolean {
    const value = answerPayload(question, answers);
    if (question.question_type === "multiple_choice") {
        return Array.isArray(value) && value.length > 0;
    }
    return typeof value === "string" && value.trim().length > 0;
}

export function QuestionField({
    question,
    value,
    onChange,
}: {
    readonly question: NewcomerExamPaperQuestion;
    readonly value: unknown;
    readonly onChange: (value: unknown) => void;
}) {
    if (question.question_type === "single_choice" || question.question_type === "true_false") {
        return (
            <div className="space-y-2">
                {choiceOptions(question).map((option) => {
                    const checked = value === option.value;
                    return (
                        <label
                            key={option.value}
                            className={cn(
                                "flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition-colors",
                                checked
                                    ? "border-slate-900 bg-slate-50 text-slate-900"
                                    : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50/50",
                            )}
                        >
                            <input
                                type="radio"
                                name={question.question_id}
                                value={option.value}
                                checked={checked}
                                onChange={() => onChange(option.value)}
                                aria-label={option.label || option.value}
                                className="h-4 w-4 shrink-0 accent-slate-900"
                            />
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-current text-xs font-bold opacity-70">
                                {option.value}
                            </span>
                            <span className="flex-1">{option.label || option.value}</span>
                        </label>
                    );
                })}
            </div>
        );
    }
    if (question.question_type === "multiple_choice") {
        const selectedValues = Array.isArray(value) ? value.map(String) : [];
        return (
            <div className="space-y-2">
                {question.options?.map((option) => {
                    const checked = selectedValues.includes(option.value);
                    return (
                        <label
                            key={option.value}
                            className={cn(
                                "flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition-colors",
                                checked
                                    ? "border-slate-900 bg-slate-50 text-slate-900"
                                    : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50/50",
                            )}
                        >
                            <input
                                type="checkbox"
                                value={option.value}
                                checked={checked}
                                onChange={(event) => {
                                    const next = event.target.checked
                                        ? [...selectedValues, option.value]
                                        : selectedValues.filter((item) => item !== option.value);
                                    onChange(next);
                                }}
                                aria-label={option.label || option.value}
                                className="h-4 w-4 shrink-0 accent-slate-900"
                            />
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-current text-xs font-bold opacity-70">
                                {option.value}
                            </span>
                            <span className="flex-1">{option.label || option.value}</span>
                        </label>
                    );
                })}
            </div>
        );
    }
    return (
        <textarea
            aria-label={question.stem}
            className="min-h-28 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition-colors focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
            value={typeof value === "string" ? value : ""}
            onChange={(event) => onChange(event.target.value)}
        />
    );
}
