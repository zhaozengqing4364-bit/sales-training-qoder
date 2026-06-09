import type {
    NewcomerExamPaperQuestion,
    SalesTrainerQuestionOption,
} from "@/lib/api/types";

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

function firstOptionValue(options: readonly SalesTrainerQuestionOption[] | undefined): string {
    return options?.[0]?.value ?? "";
}

export function initialAnswer(question: NewcomerExamPaperQuestion): unknown {
    if (question.question_type === "single_choice") {
        return firstOptionValue(question.options);
    }
    if (question.question_type === "true_false") {
        return firstOptionValue(TRUE_FALSE_OPTIONS);
    }
    if (question.question_type === "multiple_choice") {
        return [];
    }
    return "";
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
                {choiceOptions(question).map((option) => (
                    <label key={option.value} className="flex items-center gap-2 text-sm text-slate-700">
                        <input
                            type="radio"
                            name={question.question_id}
                            value={option.value}
                            checked={value === option.value}
                            onChange={() => onChange(option.value)}
                        />
                        <span>{option.label || option.value}</span>
                    </label>
                ))}
            </div>
        );
    }
    if (question.question_type === "multiple_choice") {
        const selectedValues = Array.isArray(value) ? value.map(String) : [];
        return (
            <div className="space-y-2">
                {question.options?.map((option) => (
                    <label key={option.value} className="flex items-center gap-2 text-sm text-slate-700">
                        <input
                            type="checkbox"
                            value={option.value}
                            checked={selectedValues.includes(option.value)}
                            onChange={(event) => {
                                const next = event.target.checked
                                    ? [...selectedValues, option.value]
                                    : selectedValues.filter((item) => item !== option.value);
                                onChange(next);
                            }}
                        />
                        <span>{option.label || option.value}</span>
                    </label>
                ))}
            </div>
        );
    }
    return (
        <textarea
            className="min-h-28 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-slate-400"
            value={typeof value === "string" ? value : ""}
            onChange={(event) => onChange(event.target.value)}
        />
    );
}
