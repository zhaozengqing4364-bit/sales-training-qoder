"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import type {
    FoundationActivityCommand,
    FoundationActivityWorkspace,
    FoundationQuizRunner,
} from "@/lib/api/types/newcomer-training";
import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";
import { trackFoundationUxEvent } from "@/lib/newcomer-training/ux-events";
import { getFoundationUserErrorMessage } from "@/lib/newcomer-training/errors";
import type { ActivityRunnerProps } from "./types";

type QuizAnswer = FoundationQuizRunner["answers"][number];

function formatRetryInterval(seconds: number): string {
    if (seconds < 60) return `${seconds} 秒`;
    if (seconds < 3_600) return `${Math.ceil(seconds / 60)} 分钟`;
    if (seconds < 86_400) return `${Math.ceil(seconds / 3_600)} 小时`;
    return `${Math.ceil(seconds / 86_400)} 天`;
}

function quizRuleSummary(
    runner: FoundationQuizRunner,
    estimatedMinutes: number,
): string {
    const attemptPolicy = runner.rules.max_attempts === 1
        ? "仅可作答 1 次"
        : runner.rules.retry_interval_seconds === 0
            ? `最多可作答 ${runner.rules.max_attempts} 次，未通过后可立即再试`
            : `最多可作答 ${runner.rules.max_attempts} 次，未通过后需等待 ${formatRetryInterval(runner.rules.retry_interval_seconds)}后再试`;
    const timePolicy = runner.rules.time_limit_minutes === null
        ? `预计 ${estimatedMinutes} 分钟完成，不限答题时长`
        : `预计 ${estimatedMinutes} 分钟完成，开始后限时 ${runner.rules.time_limit_minutes} 分钟`;
    return `本次共 ${runner.question_count} 题，通过分数为 ${runner.rules.pass_threshold} 分。${attemptPolicy}；${timePolicy}。开始后题目和评分规则会固定到本次作答记录。`;
}

function answersByQuestion(answers: FoundationQuizRunner["answers"]): Record<string, QuizAnswer> {
    return Object.fromEntries(answers.map((answer) => [answer.question_revision_id, answer]));
}

export function QuizRunner({ detail, onRefresh }: ActivityRunnerProps) {
    const runner = detail.runner.kind === "quiz" ? detail.runner : null;
    const [answers, setAnswers] = useState<Record<string, QuizAnswer>>(
        runner ? answersByQuestion(runner.answers) : {},
    );
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const tokenStore = useRef(createIdempotencyTokenStore());

    useEffect(() => {
        if (runner) {
            setAnswers(answersByQuestion(runner.answers));
        }
    }, [runner]);

    if (!runner) {
        return <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">活动类型不匹配，请返回训练路径后重试。</p>;
    }

    const execute = async (command: FoundationActivityCommand, inputKey: string) => {
        const result = await api.newcomerTraining.executeCommand(
            detail.activity.id,
            command,
            tokenStore.current.tokenFor(inputKey),
        );
        tokenStore.current.complete(inputKey);
        if (command.command_type === "start") {
            trackFoundationUxEvent("activity_started", "quiz");
        } else if (command.command_type === "save_answers") {
            trackFoundationUxEvent("progress_saved", "quiz");
        }
        onRefresh?.(result);
        return result;
    };

    const start = async () => {
        setPending(true);
        setError(null);
        try {
            await execute({
                command_type: "start",
                attempt_id: null,
                expected_enrollment_version: detail.enrollment_version,
                expected_attempt_version: null,
                payload: { relearn_of_detail_id: runner.status === "invalidated" ? runner.detail_id : null },
            }, `${detail.activity.id}:start:${detail.enrollment_version}:${runner.status}`);
        } catch (cause) {
            setError(getFoundationUserErrorMessage(cause));
        } finally {
            setPending(false);
        }
    };

    const answerPayload = () => runner.questions.map((question) => answers[question.question_revision_id]).filter((answer): answer is QuizAnswer => Boolean(answer));

    const save = async (workspace: FoundationActivityWorkspace = detail) => {
        if (!workspace.attempt || workspace.runner.kind !== "quiz") {
            throw new Error("测验尚未开始");
        }
        const payload = answerPayload();
        if (payload.length === 0) {
            throw new Error("请至少完成一道题后再保存。");
        }
        const serialized = JSON.stringify(payload);
        return execute({
            command_type: "save_answers",
            attempt_id: workspace.attempt.attempt_id,
            expected_enrollment_version: null,
            expected_attempt_version: workspace.runner.version,
            payload: { answers: payload },
        }, `${workspace.attempt.attempt_id}:save:${workspace.runner.version}:${serialized}`);
    };

    const saveAnswers = async () => {
        setPending(true);
        setError(null);
        try {
            await save();
        } catch (cause) {
            setError(getFoundationUserErrorMessage(cause));
        } finally {
            setPending(false);
        }
    };

    const submit = async () => {
        const missing = runner.questions.some((question) => {
            const answer = answers[question.question_revision_id];
            return !answer || (answer.selected_option_ids.length === 0 && !answer.text_answer?.trim());
        });
        if (missing) {
            setError("请完成全部题目后提交。");
            return;
        }
        setPending(true);
        setError(null);
        try {
            let current: FoundationActivityWorkspace = detail;
            const currentPayload = answerPayload();
            if (JSON.stringify(runner.answers) !== JSON.stringify(currentPayload)) {
                current = await save(current);
            }
            if (!current.attempt || current.runner.kind !== "quiz") {
                throw new Error("测验尚未开始");
            }
            await execute({
                command_type: "submit",
                attempt_id: current.attempt.attempt_id,
                expected_enrollment_version: null,
                expected_attempt_version: current.runner.version,
                payload: {},
            }, `${current.attempt.attempt_id}:submit:${current.runner.version}`);
        } catch (cause) {
            setError(getFoundationUserErrorMessage(cause));
        } finally {
            setPending(false);
        }
    };

    const updateOption = (questionId: string, optionId: string, multiple: boolean, checked: boolean) => {
        setAnswers((current) => {
            const previous = current[questionId]?.selected_option_ids ?? [];
            const selected = multiple
                ? checked ? [...previous.filter((id) => id !== optionId), optionId] : previous.filter((id) => id !== optionId)
                : [optionId];
            return { ...current, [questionId]: { question_revision_id: questionId, selected_option_ids: selected, text_answer: null } };
        });
    };

    const canStart = detail.available_commands.includes("start");
    const canSave = detail.available_commands.includes("save_answers");
    const canSubmit = detail.available_commands.includes("submit");

    return <div className="space-y-5">
        {error ? <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
        {canStart ? <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4"><p className="text-sm leading-6 text-blue-900">{quizRuleSummary(runner, detail.activity.estimated_minutes)}</p><Button className="mt-3" isLoading={pending} onClick={() => void start()}>开始答题</Button></div> : null}

        {runner.questions.length > 0 ? <form className="space-y-5" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
            {runner.questions.map((question, index) => <fieldset key={question.question_revision_id} disabled={pending} className="rounded-2xl border border-slate-200 p-4 disabled:opacity-70">
                <legend className="px-1 font-semibold text-slate-900">{index + 1}. {question.stem}<span className="ml-2 text-xs font-normal text-slate-500">{question.points} 分</span></legend>
                {question.question_type === "short_answer"
                    ? <textarea aria-label={`第 ${index + 1} 题答案`} className="mt-3 min-h-28 w-full rounded-xl border border-slate-200 px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500" value={answers[question.question_revision_id]?.text_answer ?? ""} onChange={(event) => setAnswers((current) => ({ ...current, [question.question_revision_id]: { question_revision_id: question.question_revision_id, selected_option_ids: [], text_answer: event.target.value } }))} />
                    : <div className="mt-3 space-y-2">{question.options.map((option) => {
                        const multiple = question.question_type === "multiple_choice";
                        const checked = answers[question.question_revision_id]?.selected_option_ids.includes(option.option_id) ?? false;
                        return <label key={option.option_id} className="flex items-start gap-2 text-sm leading-6 text-slate-700"><input className="mt-1" type={multiple ? "checkbox" : "radio"} name={question.question_revision_id} checked={checked} onChange={(event) => updateOption(question.question_revision_id, option.option_id, multiple, event.target.checked)} /><span>{option.text}</span></label>;
                    })}</div>}
            </fieldset>)}
            <div className="flex flex-wrap gap-3">{canSave ? <Button type="button" variant="secondary" disabled={pending} onClick={() => void saveAnswers()}>保存答案</Button> : null}{canSubmit ? <Button type="submit" isLoading={pending}>提交答案</Button> : null}</div>
        </form> : null}
    </div>;
}
