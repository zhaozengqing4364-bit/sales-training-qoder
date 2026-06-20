"use client";

import { useCallback, useEffect, useMemo, useRef, type ReactNode, type Ref } from "react";
import { Bot, UserRound } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type {
    AiCoachAnswerPayloadV1,
    AiCoachChatMessagePublicV1,
    AiCoachChatSessionPublicV1,
    AiCoachUiEventPublicV1,
} from "@/lib/api/types";

import { type DraftByEventId } from "./coach-session";
import { GenerativeCard } from "./coach-cards";
import { BUSINESS_SKILLS_COACH_WORKBENCH_COPY } from "./coach-workbench-config";

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
    isStarting,
    isSending,
    isAdvancing,
    activityLabel,
    activeEventId,
    hiddenEventIds,
    error,
    autoScrollKey,
    trailingNode,
    className,
    onFollowupPrompt,
    onDraftChange,
    onSubmitEvent,
}: {
    readonly session: AiCoachChatSessionPublicV1 | null;
    readonly pendingUserMessage: string | null;
    readonly drafts: DraftByEventId;
    readonly submittingEventIds: ReadonlySet<string>;
    readonly isStarting: boolean;
    readonly isSending: boolean;
    readonly isAdvancing: boolean;
    readonly activityLabel: string | null;
    readonly activeEventId: string | null;
    readonly hiddenEventIds?: ReadonlySet<string>;
    readonly error: string | null;
    readonly autoScrollKey?: string | number;
    readonly trailingNode?: ReactNode;
    readonly className?: string;
    readonly onFollowupPrompt: (prompt: string) => void;
    readonly onDraftChange: (eventId: string, payload: AiCoachAnswerPayloadV1) => void;
    readonly onSubmitEvent: (event: AiCoachUiEventPublicV1) => void;
}) {
    const messages = buildMessages(session, pendingUserMessage);
    const eventsByMessage = groupEventsByMessage(session?.ui_events ?? []);
    const logRef = useRef<HTMLDivElement | null>(null);
    const latestTurnRef = useRef<HTMLElement | null>(null);
    const shouldFollowLatestRef = useRef(true);
    const lastPendingMessageRef = useRef<string | null>(null);
    const eventScrollKey = useMemo(
        () =>
            (session?.ui_events ?? [])
                .map((event) => `${event.event_id}:${event.status}:${event.score_result?.mastered ?? ""}`)
                .join("|"),
        [session?.ui_events],
    );

    const latestTurnTop = useCallback((log: HTMLDivElement, target: HTMLElement) => (
        Math.max(0, target.offsetTop - log.clientHeight * 0.18)
    ), []);

    useEffect(() => {
        if (pendingUserMessage && pendingUserMessage !== lastPendingMessageRef.current) {
            shouldFollowLatestRef.current = true;
            lastPendingMessageRef.current = pendingUserMessage;
        }
        if (!pendingUserMessage) {
            lastPendingMessageRef.current = null;
        }
    }, [pendingUserMessage]);

    useEffect(() => {
        const log = logRef.current;
        const target = latestTurnRef.current;
        if (!log || !target || !shouldFollowLatestRef.current) {
            return;
        }
        const top = latestTurnTop(log, target);
        if (typeof log.scrollTo === "function") {
            log.scrollTo({ top, behavior: "smooth" });
            return;
        }
        log.scrollTop = top;
    }, [
        activeEventId,
        error,
        eventScrollKey,
        isAdvancing,
        isSending,
        isStarting,
        messages.length,
        autoScrollKey,
        latestTurnTop,
    ]);

    return (
        <div
            ref={logRef}
            role="log"
            aria-label="商务技巧 AI 教练对话"
            onScroll={() => {
                const log = logRef.current;
                if (!log) {
                    return;
                }
                const target = latestTurnRef.current;
                if (!target) {
                    shouldFollowLatestRef.current =
                        log.scrollHeight - log.scrollTop - log.clientHeight <= 120;
                    return;
                }
                const targetTop = latestTurnTop(log, target);
                shouldFollowLatestRef.current =
                    Math.abs(log.scrollTop - targetTop) <= 160
                    || log.scrollTop > targetTop;
            }}
            className={className ?? "min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-4 py-5 md:px-8"}
        >
            {messages.map((message, index) => (
                <ChatMessage
                    key={message.message_id}
                    anchorRef={index === messages.length - 1 && !trailingNode ? latestTurnRef : undefined}
                    message={message}
                    events={eventsByMessage.get(message.message_id) ?? []}
                    activeEventId={activeEventId}
                    hiddenEventIds={hiddenEventIds ?? EMPTY_EVENT_ID_SET}
                    drafts={drafts}
                    submittingEventIds={submittingEventIds}
                    onFollowupPrompt={onFollowupPrompt}
                    onDraftChange={onDraftChange}
                    onSubmitEvent={onSubmitEvent}
                />
            ))}
            {trailingNode ? (
                <article
                    ref={latestTurnRef}
                    data-latest-turn-anchor="true"
                    className="flex gap-3"
                >
                    <Avatar role="assistant" />
                    <div className="max-w-[84%] flex-1">{trailingNode}</div>
                </article>
            ) : null}
            {(isStarting || isSending || isAdvancing) && !trailingNode ? (
                <AssistantLoading
                    label={activityLabel ?? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.defaultThinkingLabel}
                />
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
    anchorRef,
    message,
    events,
    activeEventId,
    hiddenEventIds,
    drafts,
    submittingEventIds,
    onFollowupPrompt,
    onDraftChange,
    onSubmitEvent,
}: {
    readonly anchorRef?: Ref<HTMLElement>;
    readonly message: AiCoachChatMessagePublicV1 | PendingMessage;
    readonly events: readonly AiCoachUiEventPublicV1[];
    readonly activeEventId: string | null;
    readonly hiddenEventIds: ReadonlySet<string>;
    readonly drafts: DraftByEventId;
    readonly submittingEventIds: ReadonlySet<string>;
    readonly onFollowupPrompt: (prompt: string) => void;
    readonly onDraftChange: (eventId: string, payload: AiCoachAnswerPayloadV1) => void;
    readonly onSubmitEvent: (event: AiCoachUiEventPublicV1) => void;
}) {
    const isUser = message.role === "user";
    return (
        <article
            ref={anchorRef}
            data-latest-turn-anchor={anchorRef ? "true" : undefined}
            className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
        >
            {!isUser ? <Avatar role="assistant" /> : null}
            <div className={`max-w-[84%] space-y-3 ${isUser ? "items-end" : ""}`}>
                <div
                    className={
                        isUser
                            ? "rounded-2xl bg-slate-950 px-4 py-3 text-sm leading-relaxed text-white"
                            : "rounded-2xl bg-white px-4 py-3 text-sm leading-relaxed text-slate-800 shadow-sm"
                    }
                >
                    {isUser ? message.content : <CoachMarkdown content={message.content} />}
                </div>
                {!isUser ? (
                    <div className="space-y-3">
                        {events.map((event) =>
                            shouldRenderEvent(event, activeEventId, hiddenEventIds) ? (
                                <GenerativeCard
                                    key={event.event_id}
                                    event={event}
                                    draft={drafts[event.event_id] ?? null}
                                    isActive={event.event_id === activeEventId}
                                    isSubmitting={submittingEventIds.has(event.event_id)}
                                    presentation="compact"
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
    hiddenEventIds: ReadonlySet<string>,
): boolean {
    if (hiddenEventIds.has(event.event_id)) {
        return false;
    }
    if (event.type !== "quiz_card") {
        return true;
    }
    if (event.status !== "pending") {
        return true;
    }
    return activeEventId !== null && event.event_id === activeEventId;
}

const EMPTY_EVENT_ID_SET = new Set<string>();

export function CoachMarkdown({ content }: { readonly content: string }) {
    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={chatMarkdownComponents}
        >
            {content}
        </ReactMarkdown>
    );
}

const chatMarkdownComponents = {
    h1: ({ children }: { readonly children?: ReactNode }) => (
        <h1 className="mb-3 mt-4 text-lg font-bold leading-snug text-slate-950 first:mt-0">{children}</h1>
    ),
    h2: ({ children }: { readonly children?: ReactNode }) => (
        <h2 className="mb-2.5 mt-4 text-base font-bold leading-snug text-slate-950 first:mt-0">{children}</h2>
    ),
    h3: ({ children }: { readonly children?: ReactNode }) => (
        <h3 className="mb-2 mt-3 text-sm font-bold leading-snug text-slate-900 first:mt-0">{children}</h3>
    ),
    p: ({ children }: { readonly children?: ReactNode }) => (
        <p className="mb-3 text-sm leading-7 text-slate-800 last:mb-0">{children}</p>
    ),
    ul: ({ children }: { readonly children?: ReactNode }) => (
        <ul className="mb-3 list-disc space-y-1.5 pl-5 text-sm leading-7 text-slate-800 last:mb-0">{children}</ul>
    ),
    ol: ({ children }: { readonly children?: ReactNode }) => (
        <ol className="mb-3 list-decimal space-y-1.5 pl-5 text-sm leading-7 text-slate-800 last:mb-0">{children}</ol>
    ),
    li: ({ children }: { readonly children?: ReactNode }) => (
        <li className="leading-relaxed">{children}</li>
    ),
    strong: ({ children }: { readonly children?: ReactNode }) => (
        <strong className="font-semibold text-slate-950">{children}</strong>
    ),
    blockquote: ({ children }: { readonly children?: ReactNode }) => (
        <blockquote className="mb-3 rounded-r-xl border-l-4 border-slate-300 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-700 last:mb-0">
            {children}
        </blockquote>
    ),
    code: ({ children }: { readonly children?: ReactNode }) => (
        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800">{children}</code>
    ),
    pre: ({ children }: { readonly children?: ReactNode }) => (
        <pre className="mb-3 overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">{children}</pre>
    ),
    a: ({ href, children }: { readonly href?: string; readonly children?: ReactNode }) => (
        <a href={href} className="font-medium text-blue-600 underline underline-offset-2 hover:text-blue-800">
            {children}
        </a>
    ),
    table: ({ children }: { readonly children?: ReactNode }) => (
        <div className="my-3 overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs text-slate-700">
                {children}
            </table>
        </div>
    ),
    th: ({ children }: { readonly children?: ReactNode }) => (
        <th className="bg-slate-50 px-3 py-2 font-bold text-slate-900">{children}</th>
    ),
    td: ({ children }: { readonly children?: ReactNode }) => (
        <td className="border-t border-slate-100 px-3 py-2 align-top leading-5">{children}</td>
    ),
};

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
            <div className="rounded-2xl bg-white px-4 py-3 text-sm font-medium text-slate-500 shadow-sm">
                {label}
            </div>
        </article>
    );
}
