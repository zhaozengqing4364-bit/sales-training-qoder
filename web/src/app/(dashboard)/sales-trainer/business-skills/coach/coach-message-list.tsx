"use client";

import { useCallback, useEffect, useMemo, useRef, type ReactNode, type Ref } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type {
    AiCoachAnswerPayloadV1,
    AiCoachUiEventPublicV1,
} from "@/lib/api/types";

import {
    type CoachConversationViewModel,
    type CoachTimelineMessage,
    type DraftByEventId,
} from "./coach-session";
import { GenerativeCard } from "./coach-cards";
import { BUSINESS_SKILLS_COACH_WORKBENCH_COPY } from "./coach-workbench-config";

export function CoachMessageList({
    viewModel,
    drafts,
    submittingEventIds,
    isStarting,
    isSending,
    isAdvancing,
    activityLabel,
    hiddenEventIds,
    error,
    autoScrollKey,
    trailingNode,
    streamingMetaNode,
    streamingAttachmentNode,
    commandBar,
    className,
    onFollowupPrompt,
    onDraftChange,
    onSubmitEvent,
}: {
    readonly viewModel: CoachConversationViewModel;
    readonly drafts: DraftByEventId;
    readonly submittingEventIds: ReadonlySet<string>;
    readonly isStarting: boolean;
    readonly isSending: boolean;
    readonly isAdvancing: boolean;
    readonly activityLabel: string | null;
    readonly hiddenEventIds?: ReadonlySet<string>;
    readonly error: string | null;
    readonly autoScrollKey?: string | number;
    readonly trailingNode?: ReactNode;
    readonly streamingMetaNode?: ReactNode;
    readonly streamingAttachmentNode?: ReactNode;
    readonly commandBar?: ReactNode;
    readonly className?: string;
    readonly onFollowupPrompt: (prompt: string) => void;
    readonly onDraftChange: (eventId: string, payload: AiCoachAnswerPayloadV1) => void;
    readonly onSubmitEvent: (event: AiCoachUiEventPublicV1) => void;
}) {
    const messages = viewModel.timeline;
    const logRef = useRef<HTMLDivElement | null>(null);
    const latestTurnRef = useRef<HTMLElement | null>(null);
    const shouldFollowLatestRef = useRef(true);
    const lastPendingMessageRef = useRef<string | null>(null);
    const pendingUserMessage = messages.find((message) => message.state === "pending")?.content ?? null;
    const hasStreamingMessage = messages.some((message) => message.state === "streaming");
    const eventScrollKey = useMemo(
        () =>
            messages
                .flatMap((message) => message.events)
                .map((event) => `${event.event_id}:${event.status}:${event.score_result?.mastered ?? ""}`)
                .join("|"),
        [messages],
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
        viewModel.activeEventId,
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
            className={className ?? "min-h-0 flex-1 space-y-6 overflow-y-auto overscroll-contain px-4 py-5 md:px-8"}
        >
            {messages.map((message, index) => (
                <ChatMessage
                    key={message.message_id}
                    anchorRef={index === messages.length - 1 && !trailingNode ? latestTurnRef : undefined}
                    message={message}
                    activeEventId={viewModel.activeEventId}
                    hiddenEventIds={hiddenEventIds ?? EMPTY_EVENT_ID_SET}
                    drafts={drafts}
                    submittingEventIds={submittingEventIds}
                    isLatestAssistant={message.message_id === viewModel.latestAssistantMessageId}
                    streamingMetaNode={message.state === "streaming" ? streamingMetaNode : null}
                    streamingAttachmentNode={message.state === "streaming" ? streamingAttachmentNode : null}
                    commandBar={commandBar}
                    onFollowupPrompt={onFollowupPrompt}
                    onDraftChange={onDraftChange}
                    onSubmitEvent={onSubmitEvent}
                />
            ))}
            {trailingNode ? (
                <article
                    ref={latestTurnRef}
                    data-latest-turn-anchor="true"
                    className="flex items-start gap-3"
                >
                    <MessageAvatar role="assistant" />
                    <div className="min-w-0 flex-1">{trailingNode}</div>
                </article>
            ) : null}
            {(isStarting || isSending || isAdvancing) && !trailingNode && !hasStreamingMessage ? (
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

function ChatMessage({
    anchorRef,
    message,
    activeEventId,
    hiddenEventIds,
    drafts,
    submittingEventIds,
    isLatestAssistant,
    streamingMetaNode,
    streamingAttachmentNode,
    commandBar,
    onFollowupPrompt,
    onDraftChange,
    onSubmitEvent,
}: {
    readonly anchorRef?: Ref<HTMLElement>;
    readonly message: CoachTimelineMessage;
    readonly activeEventId: string | null;
    readonly hiddenEventIds: ReadonlySet<string>;
    readonly drafts: DraftByEventId;
    readonly submittingEventIds: ReadonlySet<string>;
    readonly isLatestAssistant: boolean;
    readonly streamingMetaNode?: ReactNode;
    readonly streamingAttachmentNode?: ReactNode;
    readonly commandBar?: ReactNode;
    readonly onFollowupPrompt: (prompt: string) => void;
    readonly onDraftChange: (eventId: string, payload: AiCoachAnswerPayloadV1) => void;
    readonly onSubmitEvent: (event: AiCoachUiEventPublicV1) => void;
}) {
    const isUser = message.role === "user";
    return (
        <article
            ref={anchorRef}
            data-latest-turn-anchor={anchorRef ? "true" : undefined}
            className={isUser ? "flex items-start justify-end gap-3" : "flex items-start gap-3"}
        >
            {isUser ? (
                <>
                    <p className="max-w-[80%] rounded-2xl rounded-br-md bg-slate-900 px-4 py-2.5 text-sm leading-relaxed text-white">
                        {message.content}
                    </p>
                    <MessageAvatar role="user" />
                </>
            ) : (
                <>
                    <MessageAvatar role="assistant" />
                    <div className="min-w-0 flex-1 space-y-3">
                        <div className="max-w-[72ch] rounded-2xl rounded-tl-md border border-slate-200 bg-white px-4 py-3 text-sm leading-7 text-slate-800 shadow-sm">
                            <CoachMarkdown content={message.content} />
                            {streamingMetaNode}
                        </div>
                        {streamingAttachmentNode}
                        <div className="space-y-3">
                            {message.events.map((event) =>
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
                        {isLatestAssistant && commandBar ? (
                            <div className="max-w-[72ch] rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                                {commandBar}
                            </div>
                        ) : null}
                    </div>
                </>
            )}
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
        <blockquote className="mb-3 rounded-xl bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-700 last:mb-0">
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

function MessageAvatar({ role }: { readonly role: "assistant" | "user" }) {
    const label = role === "assistant" ? "AI" : "我";
    const className = role === "assistant"
        ? "bg-violet-50 text-violet-700 ring-violet-100"
        : "bg-slate-900 text-white ring-slate-900";
    return (
        <span
            aria-label={role === "assistant" ? "教练" : "你"}
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-black ring-1 ${className}`}
        >
            {label}
        </span>
    );
}

function AssistantLoading({ label }: { readonly label: string }) {
    return (
        <article className="flex items-start gap-3">
            <MessageAvatar role="assistant" />
            <div className="flex items-center gap-2 rounded-2xl rounded-tl-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
                <span className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:0ms]" />
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:150ms]" />
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:300ms]" />
                </span>
                <span>{label}</span>
            </div>
        </article>
    );
}
