"use client";

import type { FormEvent } from "react";
import { Bot, CheckCircle2, ClipboardList, RefreshCw, RotateCcw, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import type {
    AiCoachAnswerPayloadV1,
    AiCoachChatSessionPublicV1,
    AiCoachUiEventPublicV1,
} from "@/lib/api/types";

import {
    activeEventIdForSession,
    activeQuizEventForSession,
    type CoachCommand,
    type DraftByEventId,
} from "./coach-session";
import { CoachMessageList } from "./coach-message-list";

interface AiCoachChatSurfaceProps {
    readonly session: AiCoachChatSessionPublicV1 | null;
    readonly input: string;
    readonly drafts: DraftByEventId;
    readonly pendingUserMessage: string | null;
    readonly isStarting: boolean;
    readonly isSending: boolean;
    readonly pendingCommand: CoachCommand | null;
    readonly submittingEventIds: ReadonlySet<string>;
    readonly streamActivityLabel: string | null;
    readonly error: string | null;
    readonly onInputChange: (value: string) => void;
    readonly onSend: () => void;
    readonly onCoachCommand: (command: CoachCommand) => void;
    readonly onFollowupPrompt: (prompt: string) => void;
    readonly onDraftChange: (eventId: string, payload: AiCoachAnswerPayloadV1) => void;
    readonly onSubmitEvent: (event: AiCoachUiEventPublicV1) => void;
    readonly onResume: () => void;
    readonly onNewSession: () => void;
}

export function AiCoachChatSurface({
    session,
    input,
    drafts,
    pendingUserMessage,
    isStarting,
    isSending,
    pendingCommand,
    submittingEventIds,
    streamActivityLabel,
    error,
    onInputChange,
    onSend,
    onCoachCommand,
    onFollowupPrompt,
    onDraftChange,
    onSubmitEvent,
    onResume,
    onNewSession,
}: AiCoachChatSurfaceProps) {
    const isAdvancing = submittingEventIds.size > 0;
    const isBusy = isStarting || isSending || isAdvancing;
    const activeEventId = activeEventIdForSession(session);
    const activeQuiz = activeQuizEventForSession(session);
    const activityLabel = streamActivityLabel
        ?? activityLabelFor(pendingCommand, isSending, isAdvancing, isStarting);
    return (
        <section className="mx-auto flex h-[calc(100dvh-7rem)] min-h-0 w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-[#f8fafc] shadow-sm">
            <header className="shrink-0 flex flex-col gap-4 border-b border-slate-200 bg-white/90 px-5 py-4 backdrop-blur lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-950 text-white">
                        <Bot className="h-5 w-5" />
                    </div>
                    <div>
                        <h1 className="text-lg font-semibold text-slate-950">
                            商务技巧 AI 教练
                        </h1>
                        <p className="text-xs text-slate-500">
                            {session ? "教练主导训练局" : "正在建立训练局"}
                        </p>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        className="rounded-xl"
                        disabled={isBusy}
                        onClick={onResume}
                    >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        {isStarting ? "处理中" : "继续当前局"}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        className="rounded-xl"
                        disabled={isBusy}
                        onClick={onNewSession}
                    >
                        <RotateCcw className="mr-2 h-4 w-4" />
                        {isStarting ? "新开中" : "新开一局"}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        className="rounded-xl border-amber-200 text-amber-700 hover:bg-amber-50"
                        disabled={!session || isBusy}
                        onClick={() => onCoachCommand("end")}
                    >
                        <ClipboardList className="mr-2 h-4 w-4" />
                        结束并总结
                    </Button>
                </div>
            </header>
            {session?.coach_state ? <CoachStateBar session={session} /> : null}
            <CoachMessageList
                session={session}
                pendingUserMessage={pendingUserMessage}
                drafts={drafts}
                submittingEventIds={submittingEventIds}
                isStarting={isStarting}
                isSending={isSending}
                isAdvancing={isAdvancing}
                activityLabel={activityLabel}
                activeEventId={activeEventId}
                error={error}
                onFollowupPrompt={onFollowupPrompt}
                onDraftChange={onDraftChange}
                onSubmitEvent={onSubmitEvent}
            />
            <CoachCommandBar
                disabled={!session || isBusy}
                hasActiveQuiz={activeQuiz !== null}
                pendingCommand={pendingCommand}
                onCommand={onCoachCommand}
            />
            <Composer
                value={input}
                disabled={!session || isBusy}
                hasActiveQuiz={activeQuiz !== null}
                onChange={onInputChange}
                onSubmit={onSend}
            />
        </section>
    );
}

function CoachStateBar({
    session,
}: {
    readonly session: AiCoachChatSessionPublicV1;
}) {
    const state = session.coach_state;
    if (!state) {
        return null;
    }
    const difficultyLabel = {
        warmup: "热身",
        normal: "标准",
        challenge: "挑战",
    }[state.difficulty];
    const phaseLabel = {
        starting: "准备开局",
        answering: "作答中",
        reviewing: "复盘中",
        choosing: "等你选择",
        summarizing: "本轮总结",
        completed: "已结束",
    }[state.session_phase];
    const actionLabel = state.last_action ? nextActionLabel(state.last_action) : "准备第一题";
    return (
        <div className="grid shrink-0 gap-3 border-b border-slate-200 bg-slate-50/80 px-5 py-4 text-sm text-slate-700 md:grid-cols-4">
            <StatusTile label="当前阶段" value={phaseLabel} />
            <StatusTile label="训练主题" value={state.current_focus || "商务技巧"} />
            <StatusTile label="难度/进度" value={`${difficultyLabel} · 已完成 ${state.answered_card_count} 题`} />
            <StatusTile label="下一步" value={actionLabel} />
        </div>
    );
}

function StatusTile({
    label,
    value,
}: {
    readonly label: string;
    readonly value: string;
}) {
    return (
        <div className="rounded-xl bg-white px-3 py-2 shadow-sm">
            <p className="text-[11px] font-semibold text-slate-400">{label}</p>
            <p className="mt-1 truncate font-medium text-slate-900">{value}</p>
        </div>
    );
}

function CoachCommandBar({
    disabled,
    hasActiveQuiz,
    pendingCommand,
    onCommand,
}: {
    readonly disabled: boolean;
    readonly hasActiveQuiz: boolean;
    readonly pendingCommand: CoachCommand | null;
    readonly onCommand: (command: CoachCommand) => void;
}) {
    const commands: readonly {
        readonly command: CoachCommand;
        readonly label: string;
        readonly disabled?: boolean;
    }[] = [
        { command: "continue", label: "继续下一题", disabled: hasActiveQuiz },
        { command: "explain", label: "讲解一下" },
        { command: "switch_scenario", label: "换个场景" },
        { command: "summarize", label: "总结本轮" },
    ];
    return (
        <div className="shrink-0 border-t border-slate-200 bg-white/90 px-4 py-3 md:px-8">
            <div className="flex flex-wrap items-center gap-2">
                <span className="mr-1 inline-flex items-center text-xs font-semibold text-slate-500">
                    <CheckCircle2 className="mr-1 h-4 w-4 text-emerald-600" />
                    教练动作
                </span>
                {commands.map((item) => (
                    <Button
                        key={item.command}
                        type="button"
                        variant={item.command === "continue" ? "primary" : "outline"}
                        size="sm"
                        className="rounded-xl"
                        disabled={disabled || item.disabled === true}
                        onClick={() => onCommand(item.command)}
                    >
                        {pendingCommand === item.command ? "处理中" : item.label}
                    </Button>
                ))}
            </div>
        </div>
    );
}

function Composer({
    value,
    disabled,
    hasActiveQuiz,
    onChange,
    onSubmit,
}: {
    readonly value: string;
    readonly disabled: boolean;
    readonly hasActiveQuiz: boolean;
    readonly onChange: (value: string) => void;
    readonly onSubmit: () => void;
}) {
    const submit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        onSubmit();
    };
    return (
        <form
            onSubmit={submit}
            className="shrink-0 border-t border-slate-200 bg-white/95 px-4 py-4 backdrop-blur md:px-8"
        >
            <div className="flex items-end gap-3 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm">
                <textarea
                    value={value}
                    disabled={disabled}
                    onChange={(event) => onChange(event.target.value)}
                    placeholder={
                        hasActiveQuiz
                            ? "作答卡片是主流程；这里可以问教练一句"
                            : "问教练一句，或使用上方操作"
                    }
                    rows={1}
                    className="max-h-32 min-h-11 flex-1 resize-none bg-transparent px-3 py-2 text-sm leading-relaxed text-slate-900 outline-none placeholder:text-slate-400"
                />
                <Button
                    type="submit"
                    disabled={disabled || !value.trim()}
                    className="h-11 rounded-xl bg-slate-950 px-4 hover:bg-slate-800"
                    aria-label="发送"
                >
                    <Send className="h-4 w-4" />
                </Button>
            </div>
        </form>
    );
}

function activityLabelFor(
    pendingCommand: CoachCommand | null,
    isSending: boolean,
    isAdvancing: boolean,
    isStarting: boolean,
): string | null {
    if (isStarting) {
        return "正在准备训练局";
    }
    if (isAdvancing) {
        return "正在批改，并判断下一步训练";
    }
    if (!isSending) {
        return null;
    }
    switch (pendingCommand) {
        case "explain":
            return "正在生成补救讲解";
        case "switch_scenario":
            return "正在准备新场景";
        case "summarize":
        case "end":
            return "正在总结本轮";
        case "continue":
        case "retry":
            return "正在准备下一题";
        case null:
            return "正在回应你的问题";
    }
}

function nextActionLabel(action: string): string {
    const labels: Record<string, string> = {
        continue_drill: "继续同主题训练",
        increase_difficulty: "提高情境难度",
        remediate: "先讲解再重练",
        switch_scenario: "切换训练场景",
        summarize: "总结本轮表现",
        ask_user_choice: "等你选择方向",
        end_session: "结束并总结",
    };
    return labels[action] ?? "继续训练";
}
