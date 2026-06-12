"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    AiCoachAnswerPayloadV1,
    AiCoachChatSessionPublicV1,
    AiCoachUiEventPublicV1,
} from "@/lib/api/types";

import { AiCoachChatSurface } from "./coach-conversation";
import {
    activeEventIdForSession,
    type CoachCommand,
    type DraftByEventId,
    MODULE_KEY,
} from "./coach-session";

export default function AiCoachPage() {
    const [session, setSession] = useState<AiCoachChatSessionPublicV1 | null>(null);
    const [input, setInput] = useState("");
    const [drafts, setDrafts] = useState<DraftByEventId>({});
    const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
    const [pendingCommand, setPendingCommand] = useState<CoachCommand | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSending, setIsSending] = useState(false);
    const [submittingEventIds, setSubmittingEventIds] = useState<ReadonlySet<string>>(
        () => new Set(),
    );
    const [error, setError] = useState<string | null>(null);

    const startSession = useCallback(async (resumeStrategy: "latest_in_progress" | "new" = "latest_in_progress") => {
        setIsLoading(true);
        setError(null);
        setDrafts({});
        setPendingUserMessage(null);
        setPendingCommand(null);
        try {
            const next = await api.newcomerTraining.startAiCoachChatSession({
                module_key: MODULE_KEY,
                resume_strategy: resumeStrategy,
            });
            setSession(next);
        } catch (startError) {
            setSession(null);
            setError(getApiErrorMessage(startError));
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        let isActive = true;
        void api.newcomerTraining.startAiCoachChatSession({
            module_key: MODULE_KEY,
            resume_strategy: "latest_in_progress",
        })
            .then((next) => {
                if (!isActive) {
                    return;
                }
                setSession(next);
                setError(null);
            })
            .catch((startError) => {
                if (!isActive) {
                    return;
                }
                setSession(null);
                setError(getApiErrorMessage(startError));
            })
            .finally(() => {
                if (isActive) {
                    setIsLoading(false);
                }
            });
        return () => {
            isActive = false;
        };
    }, []);

    const updateDraft = useCallback(
        (eventId: string, payload: AiCoachAnswerPayloadV1) => {
            setDrafts((current) => ({ ...current, [eventId]: payload }));
        },
        [],
    );

    const sendText = useCallback(async (content: string) => {
        if (!session || isSending) {
            return;
        }
        const message = content.trim();
        if (!message) {
            return;
        }
        setInput("");
        setError(null);
        setIsSending(true);
        setPendingUserMessage(message);
        try {
            const next = await api.newcomerTraining.sendAiCoachChatMessage(
                session.session_id,
                { content: message },
            );
            setSession(next);
            setDrafts({});
        } catch (sendError) {
            setError(getApiErrorMessage(sendError));
        } finally {
            setPendingUserMessage(null);
            setIsSending(false);
        }
    }, [session, isSending]);

    const sendCommand = useCallback(async (command: CoachCommand) => {
        if (!session || isSending) {
            return;
        }
        setError(null);
        setIsSending(true);
        setPendingCommand(command);
        try {
            const activeEventId = activeEventIdForSession(session);
            const next = await api.newcomerTraining.sendAiCoachChatMessage(
                session.session_id,
                {
                    command,
                    event_id: activeEventId ?? undefined,
                },
            );
            setSession(next);
            setDrafts({});
        } catch (sendError) {
            setError(getApiErrorMessage(sendError));
        } finally {
            setPendingCommand(null);
            setIsSending(false);
        }
    }, [session, isSending]);

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
            setError(null);
            setSubmittingEventIds((current) => new Set(current).add(event.event_id));
            try {
                const next = await api.newcomerTraining.submitAiCoachChatEventAnswer(
                    session.session_id,
                    event.event_id,
                    { answer_payload: answerPayload },
                );
                setSession(next);
                setDrafts((current) => {
                    const nextDrafts = { ...current };
                    delete nextDrafts[event.event_id];
                    return nextDrafts;
                });
            } catch (submitError) {
                setError(getApiErrorMessage(submitError));
            } finally {
                setSubmittingEventIds((current) => {
                    const next = new Set(current);
                    next.delete(event.event_id);
                    return next;
                });
            }
        },
        [session, drafts],
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
                isSending={isSending}
                pendingCommand={pendingCommand}
                submittingEventIds={submittingEventIds}
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
