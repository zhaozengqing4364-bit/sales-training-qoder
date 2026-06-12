"use client";

import { Bot, Loader2, UserRound } from "lucide-react";

import type {
    AiCoachAnswerPayloadV1,
    AiCoachChatMessagePublicV1,
    AiCoachChatSessionPublicV1,
    AiCoachUiEventPublicV1,
} from "@/lib/api/types";

import { type DraftByEventId } from "./coach-session";
import { GenerativeCard } from "./coach-cards";

type PendingMessage = {
    readonly message_id: "pending-user";
    readonly role: "user";
    readonly content: string;
    readonly order_index: number;
    readonly created_at: string;
};

export function CoachMessageList({
    session,
    pendingUserMessage,
    drafts,
    submittingEventIds,
    isSending,
    isAdvancing,
    activityLabel,
    activeEventId,
    error,
    onFollowupPrompt,
    onDraftChange,
    onSubmitEvent,
}: {
    readonly session: AiCoachChatSessionPublicV1 | null;
    readonly pendingUserMessage: string | null;
    readonly drafts: DraftByEventId;
    readonly submittingEventIds: ReadonlySet<string>;
    readonly isSending: boolean;
    readonly isAdvancing: boolean;
    readonly activityLabel: string | null;
    readonly activeEventId: string | null;
    readonly error: string | null;
    readonly onFollowupPrompt: (prompt: string) => void;
    readonly onDraftChange: (eventId: string, payload: AiCoachAnswerPayloadV1) => void;
    readonly onSubmitEvent: (event: AiCoachUiEventPublicV1) => void;
}) {
    const messages = buildMessages(session, pendingUserMessage);
    const eventsByMessage = groupEventsByMessage(session?.ui_events ?? []);
    return (
        <div
            role="log"
            aria-label="商务技巧 AI 教练对话"
            className="flex-1 space-y-5 overflow-y-auto px-4 py-5 md:px-8"
        >
            {messages.map((message) => (
                <ChatMessage
                    key={message.message_id}
                    message={message}
                    events={eventsByMessage.get(message.message_id) ?? []}
                    activeEventId={activeEventId}
                    drafts={drafts}
                    submittingEventIds={submittingEventIds}
                    onFollowupPrompt={onFollowupPrompt}
                    onDraftChange={onDraftChange}
                    onSubmitEvent={onSubmitEvent}
                />
            ))}
            {isSending || isAdvancing ? (
                <AssistantLoading label={activityLabel ?? "正在推进训练"} />
            ) : null}
            {error ? (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
                    {error}
                </div>
            ) : null}
        </div>
    );
}

function buildMessages(
    session: AiCoachChatSessionPublicV1 | null,
    pendingUserMessage: string | null,
): ReadonlyArray<AiCoachChatMessagePublicV1 | PendingMessage> {
    const messages = [...(session?.messages ?? [])];
    if (pendingUserMessage) {
        messages.push({
            message_id: "pending-user",
            role: "user",
            content: pendingUserMessage,
            order_index: messages.length + 1,
            created_at: new Date().toISOString(),
        });
    }
    return messages;
}

function groupEventsByMessage(events: readonly AiCoachUiEventPublicV1[]) {
    const grouped = new Map<string, AiCoachUiEventPublicV1[]>();
    for (const event of events) {
        grouped.set(event.message_id, [...(grouped.get(event.message_id) ?? []), event]);
    }
    return grouped;
}

function ChatMessage({
    message,
    events,
    activeEventId,
    drafts,
    submittingEventIds,
    onFollowupPrompt,
    onDraftChange,
    onSubmitEvent,
}: {
    readonly message: AiCoachChatMessagePublicV1 | PendingMessage;
    readonly events: readonly AiCoachUiEventPublicV1[];
    readonly activeEventId: string | null;
    readonly drafts: DraftByEventId;
    readonly submittingEventIds: ReadonlySet<string>;
    readonly onFollowupPrompt: (prompt: string) => void;
    readonly onDraftChange: (eventId: string, payload: AiCoachAnswerPayloadV1) => void;
    readonly onSubmitEvent: (event: AiCoachUiEventPublicV1) => void;
}) {
    const isUser = message.role === "user";
    return (
        <article className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
            {!isUser ? <Avatar role="assistant" /> : null}
            <div className={`max-w-[84%] space-y-3 ${isUser ? "items-end" : ""}`}>
                <div
                    className={
                        isUser
                            ? "rounded-2xl bg-slate-950 px-4 py-3 text-sm leading-relaxed text-white"
                            : "rounded-2xl bg-white px-4 py-3 text-sm leading-relaxed text-slate-800 shadow-sm"
                    }
                >
                    {message.content}
                </div>
                {!isUser ? (
                    <div className="space-y-3">
                        {events.map((event) =>
                            shouldRenderEvent(event, activeEventId) ? (
                                <GenerativeCard
                                    key={event.event_id}
                                    event={event}
                                    draft={drafts[event.event_id] ?? null}
                                    isActive={event.event_id === activeEventId}
                                    isSubmitting={submittingEventIds.has(event.event_id)}
                                    onFollowupPrompt={onFollowupPrompt}
                                    onDraftChange={(payload) =>
                                        onDraftChange(event.event_id, payload)
                                    }
                                    onSubmit={() => onSubmitEvent(event)}
                                />
                            ) : null,
                        )}
                    </div>
                ) : null}
            </div>
            {isUser ? <Avatar role="user" /> : null}
        </article>
    );
}

function shouldRenderEvent(
    event: AiCoachUiEventPublicV1,
    activeEventId: string | null,
): boolean {
    if (event.type !== "quiz_card") {
        return true;
    }
    if (event.status !== "pending") {
        return true;
    }
    return activeEventId !== null && event.event_id === activeEventId;
}

function Avatar({ role }: { readonly role: "assistant" | "user" }) {
    const className =
        role === "assistant"
            ? "bg-violet-600 text-white"
            : "bg-slate-900 text-white";
    const Icon = role === "assistant" ? Bot : UserRound;
    return (
        <div className={`mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${className}`}>
            <Icon className="h-4 w-4" />
        </div>
    );
}

function AssistantLoading({ label }: { readonly label: string }) {
    return (
        <article className="flex gap-3">
            <Avatar role="assistant" />
            <div className="rounded-2xl bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
                <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
                {label}
            </div>
        </article>
    );
}
