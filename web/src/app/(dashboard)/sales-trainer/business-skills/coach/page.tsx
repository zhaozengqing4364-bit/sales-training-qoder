"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    AiCoachAnswerPayloadV1,
    AiCoachChatSessionPublicV1,
    AiCoachChatStreamEvent,
    AiCoachUiEventPublicV1,
} from "@/lib/api/types";

import { AiCoachChatSurface } from "./coach-conversation";
import {
    activeEventIdForSession,
    type CoachCommand,
    type DraftByEventId,
    MODULE_KEY,
} from "./coach-session";

type ResumeStrategy = "latest_active_or_new" | "latest_in_progress" | "new";

export default function AiCoachPage() {
    const [session, setSession] = useState<AiCoachChatSessionPublicV1 | null>(null);
    const [input, setInput] = useState("");
    const [drafts, setDrafts] = useState<DraftByEventId>({});
    const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
    const [pendingCommand, setPendingCommand] = useState<CoachCommand | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isStarting, setIsStarting] = useState(false);
    const [isSending, setIsSending] = useState(false);
    const [submittingEventIds, setSubmittingEventIds] = useState<ReadonlySet<string>>(
        () => new Set(),
    );
    const [streamActivityLabel, setStreamActivityLabel] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const streamOperationRef = useRef(0);
    const streamAbortRef = useRef<AbortController | null>(null);

    const applyStreamEvent = useCallback((event: AiCoachChatStreamEvent) => {
        if (event.type === "status") {
            setStreamActivityLabel(event.message);
            return;
        }
        if (event.type === "session_snapshot") {
            setSession(event.session);
            setIsLoading(false);
            setError(null);
            return;
        }
        setStreamActivityLabel(null);
        setError(event.message);
    }, []);

    const beginStreamOperation = useCallback(() => {
        streamAbortRef.current?.abort();
        const controller = new AbortController();
        streamAbortRef.current = controller;
        streamOperationRef.current += 1;
        return {
            controller,
            operationId: streamOperationRef.current,
        };
    }, []);

    const isCurrentStreamOperation = useCallback((operationId: number) => {
        return streamOperationRef.current === operationId;
    }, []);

    const startSession = useCallback(async (
        resumeStrategy: ResumeStrategy = "latest_active_or_new",
        options: {
            readonly initialLoad?: boolean;
            readonly clearOnError?: boolean;
        } = {},
    ) => {
        const { controller, operationId } = beginStreamOperation();
        setError(null);
        setIsStarting(true);
        setStreamActivityLabel(
            resumeStrategy === "new" ? "正在新开训练局" : "正在恢复训练局",
        );
        setPendingUserMessage(null);
        setPendingCommand(null);
        if (options.initialLoad) {
            setIsLoading(true);
        }
        try {
            const events = api.newcomerTraining.startAiCoachChatSessionStream(
                {
                    module_key: MODULE_KEY,
                    resume_strategy: resumeStrategy,
                },
                controller.signal,
            );
            for await (const event of events) {
                if (!isCurrentStreamOperation(operationId)) {
                    return;
                }
                applyStreamEvent(event);
            }
            if (isCurrentStreamOperation(operationId)) {
                setDrafts({});
            }
        } catch (startError) {
            if (!isCurrentStreamOperation(operationId)) {
                return;
            }
            if (startError instanceof Error && startError.name === "AbortError") {
                return;
            }
            if (options.clearOnError) {
                setSession(null);
            }
            setError(getApiErrorMessage(startError));
        } finally {
            if (isCurrentStreamOperation(operationId)) {
                setIsStarting(false);
                setIsLoading(false);
                setStreamActivityLabel(null);
            }
        }
    }, [applyStreamEvent, beginStreamOperation, isCurrentStreamOperation]);

    useEffect(() => {
        void startSession("latest_active_or_new", {
            initialLoad: true,
            clearOnError: true,
        });
        return () => {
            streamAbortRef.current?.abort();
        };
    }, [startSession]);

    const updateDraft = useCallback(
        (eventId: string, payload: AiCoachAnswerPayloadV1) => {
            setDrafts((current) => ({ ...current, [eventId]: payload }));
        },
        [],
    );

    const sendText = useCallback(async (content: string) => {
        if (!session || isSending || isStarting) {
            return;
        }
        const message = content.trim();
        if (!message) {
            return;
        }
        const { controller, operationId } = beginStreamOperation();
        setInput("");
        setError(null);
        setIsSending(true);
        setPendingUserMessage(message);
        setStreamActivityLabel("正在发送给教练");
        try {
            const events = api.newcomerTraining.sendAiCoachChatMessageStream(
                session.session_id,
                { content: message },
                controller.signal,
            );
            for await (const event of events) {
                if (!isCurrentStreamOperation(operationId)) {
                    return;
                }
                applyStreamEvent(event);
            }
            if (isCurrentStreamOperation(operationId)) {
                setDrafts({});
            }
        } catch (sendError) {
            if (!isCurrentStreamOperation(operationId)) {
                return;
            }
            if (sendError instanceof Error && sendError.name === "AbortError") {
                return;
            }
            setError(getApiErrorMessage(sendError));
        } finally {
            if (isCurrentStreamOperation(operationId)) {
                setPendingUserMessage(null);
                setIsSending(false);
                setStreamActivityLabel(null);
            }
        }
    }, [
        applyStreamEvent,
        beginStreamOperation,
        isCurrentStreamOperation,
        isSending,
        isStarting,
        session,
    ]);

    const sendCommand = useCallback(async (command: CoachCommand) => {
        if (!session || isSending || isStarting) {
            return;
        }
        const { controller, operationId } = beginStreamOperation();
        setError(null);
        setIsSending(true);
        setPendingCommand(command);
        setStreamActivityLabel(null);
        try {
            const activeEventId = activeEventIdForSession(session);
            const events = api.newcomerTraining.sendAiCoachChatMessageStream(
                session.session_id,
                {
                    command,
                    event_id: activeEventId ?? undefined,
                },
                controller.signal,
            );
            for await (const event of events) {
                if (!isCurrentStreamOperation(operationId)) {
                    return;
                }
                applyStreamEvent(event);
            }
            if (isCurrentStreamOperation(operationId)) {
                setDrafts({});
            }
        } catch (sendError) {
            if (!isCurrentStreamOperation(operationId)) {
                return;
            }
            if (sendError instanceof Error && sendError.name === "AbortError") {
                return;
            }
            setError(getApiErrorMessage(sendError));
        } finally {
            if (isCurrentStreamOperation(operationId)) {
                setPendingCommand(null);
                setIsSending(false);
                setStreamActivityLabel(null);
            }
        }
    }, [
        applyStreamEvent,
        beginStreamOperation,
        isCurrentStreamOperation,
        isSending,
        isStarting,
        session,
    ]);

    const sendMessage = useCallback(async () => {
        await sendText(input);
    }, [sendText, input]);

    const submitEvent = useCallback(
        async (event: AiCoachUiEventPublicV1) => {
            if (!session || event.type !== "quiz_card") {
                return;
            }
            const answerPayload = drafts[event.event_id];
            if (!answerPayload) {
                return;
            }
            const { controller, operationId } = beginStreamOperation();
            setError(null);
            setStreamActivityLabel("正在批改你的答案");
            setSubmittingEventIds((current) => new Set(current).add(event.event_id));
            try {
                const events = api.newcomerTraining.submitAiCoachChatEventAnswerStream(
                    session.session_id,
                    event.event_id,
                    { answer_payload: answerPayload },
                    controller.signal,
                );
                for await (const streamEvent of events) {
                    if (!isCurrentStreamOperation(operationId)) {
                        return;
                    }
                    applyStreamEvent(streamEvent);
                }
                if (isCurrentStreamOperation(operationId)) {
                    setDrafts((current) => {
                        const nextDrafts = { ...current };
                        delete nextDrafts[event.event_id];
                        return nextDrafts;
                    });
                }
            } catch (submitError) {
                if (!isCurrentStreamOperation(operationId)) {
                    return;
                }
                if (submitError instanceof Error && submitError.name === "AbortError") {
                    return;
                }
                setError(getApiErrorMessage(submitError));
            } finally {
                if (isCurrentStreamOperation(operationId)) {
                    setSubmittingEventIds((current) => {
                        const next = new Set(current);
                        next.delete(event.event_id);
                        return next;
                    });
                    setStreamActivityLabel(null);
                }
            }
        },
        [
            applyStreamEvent,
            beginStreamOperation,
            drafts,
            isCurrentStreamOperation,
            session,
        ],
    );

    if (isLoading) {
        return (
            <div className="space-y-6 pb-10">
                <div className="h-[70vh] animate-pulse rounded-2xl border border-violet-100 bg-violet-50" />
            </div>
        );
    }

    if (!session) {
        return (
            <div className="space-y-6 pb-20">
                <Link
                    href="/sales-trainer"
                    className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
                >
                    <ArrowLeft className="h-4 w-4" />
                    返回新人训练路径
                </Link>
                <GlassCard className="space-y-4 p-6">
                    <h1 className="text-xl font-semibold text-slate-950">
                        商务技巧 AI 教练暂不可用
                    </h1>
                    <p className="text-sm leading-relaxed text-red-700">
                        {error || "AI 教练配置缺失或未启用。"}
                    </p>
                    <Button
                        variant="outline"
                        className="rounded-full"
                        onClick={() => void startSession()}
                    >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        重试
                    </Button>
                </GlassCard>
            </div>
        );
    }

    return (
        <div className="space-y-4 pb-4">
            <Link
                href="/sales-trainer"
                className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
            >
                <ArrowLeft className="h-4 w-4" />
                返回新人训练路径
            </Link>
            <AiCoachChatSurface
                session={session}
                input={input}
                drafts={drafts}
                pendingUserMessage={pendingUserMessage}
                isStarting={isStarting}
                isSending={isSending}
                pendingCommand={pendingCommand}
                submittingEventIds={submittingEventIds}
                streamActivityLabel={streamActivityLabel}
                error={error}
                onInputChange={setInput}
                onSend={() => void sendMessage()}
                onCoachCommand={(command) => void sendCommand(command)}
                onFollowupPrompt={(prompt) => void sendText(prompt)}
                onDraftChange={updateDraft}
                onSubmitEvent={(event) => void submitEvent(event)}
                onResume={() => void startSession("latest_in_progress")}
                onNewSession={() => void startSession("new")}
            />
        </div>
    );
}
