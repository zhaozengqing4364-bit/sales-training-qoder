"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, BookOpenCheck, CircleHelp, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import type {
    FoundationActivityCommand,
    FoundationCoachCard,
} from "@/lib/api/types/newcomer-training";
import { generateClientId } from "@/lib/client-id";
import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";
import { trackFoundationUxEvent } from "@/lib/newcomer-training/ux-events";
import { getFoundationUserErrorMessage } from "@/lib/newcomer-training/errors";
import type { ActivityRunnerProps } from "./types";

type CoachAnswer = Extract<FoundationActivityCommand, { command_type: "submit_coach_answer" }>["payload"]["answer"];

function isChoiceCard(card: FoundationCoachCard): card is Extract<FoundationCoachCard, { card_type: "single_choice" | "multiple_choice" | "scenario_choice" }> {
    return ["single_choice", "multiple_choice", "scenario_choice"].includes(card.card_type);
}

export function CoachRunner({ detail, onRefresh }: ActivityRunnerProps) {
    const runner = detail.runner.kind === "ai_coach" ? detail.runner : null;
    const [selectedOptionIds, setSelectedOptionIds] = useState<string[]>([]);
    const [orderedItemIds, setOrderedItemIds] = useState<string[]>([]);
    const [textAnswer, setTextAnswer] = useState("");
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [online, setOnline] = useState(true);
    const commandTokens = useRef(createIdempotencyTokenStore());
    const answerTokens = useRef<Record<string, string>>({});
    const currentCardId = runner?.current_card?.card_id ?? null;
    const initialOrderingKey = runner?.current_card?.card_type === "ordering"
        ? runner.current_card.items.map((item) => item.item_id).join("\u001f")
        : "";

    useEffect(() => {
        const update = () => setOnline(window.navigator.onLine);
        update();
        window.addEventListener("online", update);
        window.addEventListener("offline", update);
        return () => {
            window.removeEventListener("online", update);
            window.removeEventListener("offline", update);
        };
    }, []);

    useEffect(() => {
        setSelectedOptionIds([]);
        setTextAnswer("");
        setOrderedItemIds(initialOrderingKey ? initialOrderingKey.split("\u001f") : []);
    }, [currentCardId, initialOrderingKey]);

    if (!runner) {
        return <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">活动类型不匹配，请返回训练路径后重试。</p>;
    }

    const execute = async (command: FoundationActivityCommand, inputKey: string) => {
        const result = await api.newcomerTraining.executeCommand(
            detail.activity.id,
            command,
            commandTokens.current.tokenFor(inputKey),
        );
        commandTokens.current.complete(inputKey);
        onRefresh?.(result);
        return result;
    };

    const run = async (action: () => Promise<unknown>) => {
        setPending(true);
        setError(null);
        try {
            await action();
        } catch (cause) {
            setError(getFoundationUserErrorMessage(cause));
        } finally {
            setPending(false);
        }
    };

    const start = () => run(async () => {
        await execute({
            command_type: "start",
            attempt_id: null,
            expected_enrollment_version: detail.enrollment_version,
            expected_attempt_version: null,
            payload: { relearn_of_detail_id: null },
        }, `${detail.activity.id}:start:${detail.enrollment_version}`);
        trackFoundationUxEvent("activity_started", "ai_coach");
    });

    const answerFor = (card: FoundationCoachCard): CoachAnswer | null => {
        if (isChoiceCard(card)) {
            if (selectedOptionIds.length === 0) return null;
            return { answer_type: "choice", selected_option_ids: selectedOptionIds };
        }
        if (card.card_type === "ordering") {
            if (orderedItemIds.length !== card.items.length) return null;
            return { answer_type: "ordering", ordered_item_ids: orderedItemIds };
        }
        if (!textAnswer.trim()) return null;
        return { answer_type: "text", text: textAnswer.trim() };
    };

    const submit = () => run(async () => {
        if (!online) throw new Error("当前网络已断开，回答仍保留在本页；恢复网络后再提交。");
        if (!detail.attempt || !runner.current_card) throw new Error("当前训练卡尚未准备完成。");
        const answer = answerFor(runner.current_card);
        if (!answer) throw new Error("请先完成当前训练卡的回答。");
        const cardId = runner.current_card.card_id;
        answerTokens.current[cardId] ??= generateClientId();
        await execute({
            command_type: "submit_coach_answer",
            attempt_id: detail.attempt.attempt_id,
            expected_enrollment_version: null,
            expected_attempt_version: runner.version,
            payload: {
                card_id: cardId,
                client_token: answerTokens.current[cardId],
                answer,
            },
        }, `${detail.attempt.attempt_id}:answer:${runner.version}:${cardId}:${JSON.stringify(answer)}`);
        trackFoundationUxEvent("progress_saved", "ai_coach");
    });

    const continueTraining = () => run(async () => {
        if (!detail.attempt) throw new Error("训练记录尚未开始。");
        await execute({
            command_type: "continue_coach",
            attempt_id: detail.attempt.attempt_id,
            expected_enrollment_version: null,
            expected_attempt_version: runner.version,
            payload: {},
        }, `${detail.attempt.attempt_id}:continue:${runner.version}`);
        if (runner.status === "remediation_required") {
            trackFoundationUxEvent("remediation_started", "ai_coach");
        }
    });

    const retry = () => run(async () => {
        if (!detail.attempt) throw new Error("训练记录尚未开始。");
        await execute({
            command_type: "retry_coach",
            attempt_id: detail.attempt.attempt_id,
            expected_enrollment_version: null,
            expected_attempt_version: runner.version,
            payload: {},
        }, `${detail.attempt.attempt_id}:retry:${runner.version}`);
    });

    const requestAssistance = (assistanceType: "explain" | "example") => run(async () => {
        if (!detail.attempt || !runner.current_card) throw new Error("当前没有可讲解的训练卡。");
        await execute({
            command_type: "request_coach_assistance",
            attempt_id: detail.attempt.attempt_id,
            expected_enrollment_version: null,
            expected_attempt_version: runner.version,
            payload: {
                assistance_type: assistanceType,
                card_id: runner.current_card.card_id,
            },
        }, `${detail.attempt.attempt_id}:assistance:${runner.version}:${runner.current_card.card_id}:${assistanceType}`);
    });

    const cancel = () => run(async () => {
        if (!detail.attempt) return;
        await execute({
            command_type: "cancel",
            attempt_id: detail.attempt.attempt_id,
            expected_enrollment_version: null,
            expected_attempt_version: runner.version,
            payload: {},
        }, `${detail.attempt.attempt_id}:cancel:${runner.version}`);
    });

    const refresh = () => run(async () => {
        const next = await api.newcomerTraining.getActivity(detail.activity.id);
        onRefresh?.(next);
    });

    const moveOrderingItem = (index: number, direction: -1 | 1) => {
        const target = index + direction;
        if (target < 0 || target >= orderedItemIds.length) return;
        setOrderedItemIds((current) => {
            const next = [...current];
            [next[index], next[target]] = [next[target], next[index]];
            return next;
        });
    };

    const canSubmit = detail.available_commands.includes("submit_coach_answer");
    const canContinue = detail.available_commands.includes("continue_coach");
    const canRetry = detail.available_commands.includes("retry_coach");
    const canAssist = detail.available_commands.includes("request_coach_assistance");
    const canCancel = detail.available_commands.includes("cancel");

    return <div className="flex min-h-0 flex-col md:max-h-[calc(100dvh-8rem)]">
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain pr-1">
        {error ? <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
        {!online ? <p role="status" className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">当前处于离线状态。未提交的回答保留在本页，恢复网络后可继续。</p> : null}

        {runner.status === "not_started" ? <section className="rounded-2xl border border-blue-100 bg-blue-50 p-5"><h2 className="font-semibold text-blue-950">{runner.profile_title}</h2><p className="mt-2 text-sm leading-6 text-blue-900">开始后将依次完成三个检查点；每轮只显示当前训练卡，回答和正式反馈都会保存。</p><Button className="mt-4" isLoading={pending} onClick={() => void start()}>开始结构化训练</Button></section> : null}

        {runner.status !== "not_started" ? <header className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wide text-blue-700">检查点 {runner.checkpoint.current} / {runner.checkpoint.total}</p><h2 className="mt-1 text-lg font-semibold text-slate-950">{runner.checkpoint.title}</h2>{runner.checkpoint.objective ? <p className="mt-1 text-sm leading-6 text-slate-600">{runner.checkpoint.objective}</p> : null}</div><p className="text-sm text-slate-600">本轮已完成 {runner.progress.completed_cards} / {runner.progress.total_cards} 张</p></div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200" aria-label={`本轮已完成 ${runner.progress.completed_cards} / ${runner.progress.total_cards} 张`}><div className="h-full rounded-full bg-blue-600" style={{ width: runner.progress.total_cards === 0 ? "0%" : `${Math.round(runner.progress.completed_cards * 100 / runner.progress.total_cards)}%` }} /></div>
            <p className="mt-3 text-xs text-slate-500">掌握标准和补练上限来自本次训练配置：达到 {runner.mastery.threshold_percent}% 掌握度；最多自动补练 {runner.mastery.maximum_automatic_cycles} 轮。</p>
        </header> : null}

        {runner.source_context.length > 0 ? <section aria-labelledby="coach-context-title" className="rounded-2xl border border-slate-200 p-4"><h3 id="coach-context-title" className="flex items-center gap-2 text-sm font-semibold text-slate-900"><BookOpenCheck className="h-4 w-4 text-blue-600" />本轮训练依据</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-600">{runner.source_context.map((source) => <li key={`${source.resource_type}:${source.label}`}>{source.label}</li>)}</ul>{runner.weaknesses.length > 0 ? <div className="mt-3 border-t border-slate-100 pt-3"><p className="text-xs font-semibold text-slate-700">重点巩固</p><ul className="mt-1 space-y-1 text-sm text-slate-600">{runner.weaknesses.map((weakness) => <li key={`${weakness.competency_key}:${weakness.summary}`}>{weakness.summary}</li>)}</ul></div> : null}</section> : null}

        {runner.status === "preparing" || runner.status === "evaluating" ? <section role="status" aria-live="polite" className="rounded-2xl border border-blue-100 bg-blue-50 p-5 text-blue-950"><h3 className="font-semibold">{runner.status === "preparing" ? "正在准备当前训练卡" : "回答已保存，正在生成反馈"}</h3><p className="mt-2 text-sm leading-6">你可以离开本页，稍后回来会从已保存进度继续。</p><Button className="mt-3" variant="secondary" disabled={pending} onClick={() => void refresh()}><RefreshCw className="mr-2 h-4 w-4" />刷新进度</Button></section> : null}

        {runner.current_card && ["awaiting_answer", "feedback_ready"].includes(runner.status) ? <section aria-labelledby="coach-card-title" className="rounded-2xl border border-slate-200 p-5"><p className="text-xs font-semibold text-blue-700">当前训练卡</p><h3 id="coach-card-title" className="mt-2 text-lg font-semibold leading-7 text-slate-950">{runner.current_card.prompt}</h3>{runner.current_card.sources.length > 0 ? <p className="mt-2 text-xs text-slate-500">依据：{runner.current_card.sources.join("、")}</p> : null}<div className="mt-5"><CoachCardInput card={runner.current_card} disabled={pending || runner.status !== "awaiting_answer"} selectedOptionIds={selectedOptionIds} orderedItemIds={orderedItemIds} textAnswer={textAnswer} onSelectedOptionIds={setSelectedOptionIds} onTextAnswer={setTextAnswer} onMoveOrderingItem={moveOrderingItem} /></div></section> : null}

        {runner.last_feedback ? <section aria-labelledby="coach-feedback-title" className={`rounded-2xl border p-5 ${runner.last_feedback.mastered ? "border-emerald-100 bg-emerald-50" : "border-amber-100 bg-amber-50"}`}><p className="text-xs font-medium text-slate-600">结果来源：{runner.last_feedback.evaluation_kind === "deterministic" ? "规则判断" : "语言理解评估（AI 推断）"}</p><h3 id="coach-feedback-title" className="mt-1 font-semibold text-slate-950">{runner.last_feedback.mastered ? "当前回答已达到要求" : "当前回答还需巩固"}</h3>{runner.last_feedback.feedback ? <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{runner.last_feedback.feedback}</p> : null}{runner.last_feedback.evidence_from_answer?.length ? <FeedbackList title="做得好的具体点" items={runner.last_feedback.evidence_from_answer} /> : null}{runner.last_feedback.missing_points?.length ? <FeedbackList title="缺失或需要修正的点" items={runner.last_feedback.missing_points} /> : null}{runner.last_feedback.improvement_action ? <p className="mt-3 text-sm font-medium text-slate-800">下一步：{runner.last_feedback.improvement_action}</p> : null}</section> : null}

        {runner.assistance ? <section role="status" className="rounded-2xl border border-violet-100 bg-violet-50 p-4 text-sm text-violet-950">{runner.assistance.status === "queued" ? "正在准备补充讲解…" : runner.assistance.status === "completed" ? runner.assistance.result?.explanation : "补充讲解暂时失败，不影响正式训练进度。"}</section> : null}

        {runner.status === "failed_recoverable" ? <section role="alert" className="rounded-2xl border border-red-100 bg-red-50 p-5"><h3 className="font-semibold text-red-950">当前步骤未完成</h3><p className="mt-2 text-sm leading-6 text-red-800">{runner.failure?.message ?? "系统暂时无法完成当前步骤。"}{runner.failure?.answer_preserved ? " 已提交回答仍然保留。" : ""}</p></section> : null}

        {runner.status === "needs_human_help" && runner.human_help ? <section role="status" className="rounded-2xl border border-amber-200 bg-amber-50 p-5"><h3 className="font-semibold text-amber-950">{runner.human_help.title}</h3><p className="mt-2 text-sm leading-6 text-amber-900">{runner.human_help.message}</p>{runner.human_help.next_action?.guidance ? <p className="mt-3 rounded-xl bg-white/70 p-3 text-sm text-amber-950">培训负责人指导：{runner.human_help.next_action.guidance}</p> : null}</section> : null}

        {runner.status === "cancelled" ? <p role="status" className="rounded-2xl bg-slate-100 p-4 text-sm text-slate-700">本次教练训练已取消，已提交回答和历史反馈仍被保留。</p> : null}
        {runner.status === "completed" ? <p role="status" className="rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-900">三个检查点均已完成。结果将进入后续能力证据和人工复核，不会单独决定正式达标。</p> : null}

        </div>
        {(canSubmit || canAssist || canContinue || canRetry || canCancel) ? <div aria-label="当前训练操作" className="mt-4 flex shrink-0 flex-wrap gap-2 border-t border-slate-200 bg-white pt-4">
            {canAssist && runner.current_card ? <><Button variant="secondary" disabled={pending} onClick={() => void requestAssistance("explain")}><CircleHelp className="mr-2 h-4 w-4" />解释一下</Button><Button variant="secondary" disabled={pending} onClick={() => void requestAssistance("example")}>给一个例子</Button></> : null}
            {canSubmit ? <Button disabled={!online} isLoading={pending} onClick={() => void submit()}>提交当前回答</Button> : null}
            {canContinue ? <Button isLoading={pending} onClick={() => void continueTraining()}>{runner.status === "feedback_ready" ? "继续下一张" : runner.status === "remediation_required" ? "开始针对性补练" : runner.checkpoint.current === runner.checkpoint.total ? "完成本次教练训练" : "进入下一检查点"}</Button> : null}
            {canRetry ? <Button isLoading={pending} onClick={() => void retry()}>重试当前步骤</Button> : null}
            {canCancel && !canSubmit && !canContinue && !canRetry ? <Button variant="secondary" disabled={pending} onClick={() => void cancel()}>取消本次训练</Button> : null}
        </div> : null}
    </div>;
}

function CoachCardInput({
    card,
    disabled,
    selectedOptionIds,
    orderedItemIds,
    textAnswer,
    onSelectedOptionIds,
    onTextAnswer,
    onMoveOrderingItem,
}: {
    card: FoundationCoachCard;
    disabled: boolean;
    selectedOptionIds: string[];
    orderedItemIds: string[];
    textAnswer: string;
    onSelectedOptionIds: (value: string[]) => void;
    onTextAnswer: (value: string) => void;
    onMoveOrderingItem: (index: number, direction: -1 | 1) => void;
}) {
    if (isChoiceCard(card)) {
        const multiple = card.card_type === "multiple_choice";
        return <fieldset disabled={disabled}><legend className="text-sm font-semibold text-slate-800">{multiple ? "请选择所有符合要求的选项" : "请选择一个最合适的选项"}</legend>{card.scenario ? <p className="mt-2 rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-700">{card.scenario}</p> : null}<div className="mt-3 space-y-2">{card.options.map((option) => <label key={option.option_id} className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-3 text-sm leading-6 hover:bg-slate-50"><input className="mt-1 h-4 w-4" type={multiple ? "checkbox" : "radio"} name={`coach-card-${card.card_id}`} checked={selectedOptionIds.includes(option.option_id)} onChange={(event) => onSelectedOptionIds(multiple ? event.target.checked ? [...selectedOptionIds.filter((id) => id !== option.option_id), option.option_id] : selectedOptionIds.filter((id) => id !== option.option_id) : [option.option_id])} /><span>{option.text}</span></label>)}</div></fieldset>;
    }
    if (card.card_type === "ordering") {
        const byId = Object.fromEntries(card.items.map((item) => [item.item_id, item]));
        return <fieldset disabled={disabled}><legend className="text-sm font-semibold text-slate-800">请把步骤调整为正确顺序</legend><ol className="mt-3 space-y-2">{orderedItemIds.map((itemId, index) => <li key={itemId} className="flex items-center gap-3 rounded-xl border border-slate-200 p-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">{index + 1}</span><span className="min-w-0 flex-1 text-sm text-slate-700">{byId[itemId]?.text}</span><Button type="button" size="icon" variant="ghost" aria-label={`上移“${byId[itemId]?.text}”`} disabled={disabled || index === 0} onClick={() => onMoveOrderingItem(index, -1)}><ArrowUp className="h-4 w-4" /></Button><Button type="button" size="icon" variant="ghost" aria-label={`下移“${byId[itemId]?.text}”`} disabled={disabled || index === orderedItemIds.length - 1} onClick={() => onMoveOrderingItem(index, 1)}><ArrowDown className="h-4 w-4" /></Button></li>)}</ol></fieldset>;
    }
    return <div><label htmlFor={`coach-answer-${card.card_id}`} className="text-sm font-semibold text-slate-800">{card.card_type === "short_answer_rewrite" ? card.instruction : card.card_type === "summary" ? card.scope : "请用自己的话完成回答"}</label>{card.card_type === "key_points_completion" && card.hints.length > 0 ? <p className="mt-2 text-sm text-slate-500">提示：{card.hints.join("、")}</p> : null}{card.card_type === "example_comparison" ? <div className="mt-3 grid gap-2">{card.examples.map((example, index) => <p key={`${index}-${example}`} className="rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-700">示例 {index + 1}：{example}</p>)}</div> : null}<textarea id={`coach-answer-${card.card_id}`} disabled={disabled} className="mt-3 min-h-32 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm leading-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:bg-slate-50" value={textAnswer} onChange={(event) => onTextAnswer(event.target.value)} /></div>;
}

function FeedbackList({ title, items }: { title: string; items: string[] }) {
    return <div className="mt-3"><h4 className="text-sm font-semibold text-slate-800">{title}</h4><ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">{items.map((item) => <li key={item}>{item}</li>)}</ul></div>;
}
