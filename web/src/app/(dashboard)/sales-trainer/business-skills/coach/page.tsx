"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, PlusCircle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    AiCoachAnswerPayloadV1,
    AiCoachChatSessionPublicV1,
    AiCoachChatStreamEvent,
    AiCoachChatStreamPhase,
    AiCoachUiEventPublicV1,
    BusinessEtiquetteAiCoachProgress,
    BusinessEtiquetteLearningUnit,
} from "@/lib/api/types";

import { businessSkillsArticleErrorMessage } from "../config";
import { AiCoachChatSurface } from "./coach-conversation";
import {
    activeEventIdForSession,
    type CoachCommand,
    type DraftByEventId,
    MODULE_KEY,
} from "./coach-session";
import { BUSINESS_SKILLS_COACH_WORKBENCH_COPY } from "./coach-workbench-config";

type ResumeStrategy = "latest_in_progress" | "new";
type StreamApplyResult = "status" | "delta" | "snapshot" | "error";
type AiCoachUiEventDelta = Extract<AiCoachChatStreamEvent, { type: "ui_event_delta" }>;
type AiCoachReasoningTextDelta = Extract<AiCoachChatStreamEvent, { type: "reasoning_text_delta" }>;

type CoachPreparationPanelProps = {
    readonly learningUnits: readonly BusinessEtiquetteLearningUnit[];
    readonly learningUnitsError: string | null;
    readonly activityLabel: string | null;
    readonly isBusy: boolean;
    readonly onResume: () => void;
    readonly onNewSession: () => void;
};

function businessEtiquetteCoachProgressErrorMessage(error: unknown): string {
    const apiError = error && typeof error === "object"
        ? error as { readonly status?: unknown; readonly errorCode?: unknown; readonly rawMessage?: unknown }
        : null;
    const errorCode = typeof apiError?.errorCode === "string" ? apiError.errorCode : "";
    const rawMessage = typeof apiError?.rawMessage === "string" ? apiError.rawMessage : "";
    if (
        errorCode.includes("BUSINESS_ETIQUETTE_AI_COACH_UNIT_NOT_FOUND")
        || errorCode.includes("BUSINESS_ETIQUETTE_AI_COACH_PROGRESS_SNAPSHOT_MISSING")
        || rawMessage.includes("缺少训练小单元快照")
    ) {
        return BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachSessionMissingUnitSnapshot;
    }
    if (
        apiError
        && (apiError.status === 409 || rawMessage.includes("小单元快照"))
    ) {
        return BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachProgressPendingDescription;
    }
    return getApiErrorMessage(error);
}

function isBusinessEtiquetteCoachUnitSnapshotError(error: unknown): boolean {
    const apiError = error && typeof error === "object"
        ? error as { readonly errorCode?: unknown; readonly rawMessage?: unknown }
        : null;
    const errorCode = typeof apiError?.errorCode === "string" ? apiError.errorCode : "";
    const rawMessage = typeof apiError?.rawMessage === "string" ? apiError.rawMessage : "";
    return (
        errorCode.includes("BUSINESS_ETIQUETTE_AI_COACH_UNIT_NOT_FOUND")
        || errorCode.includes("BUSINESS_ETIQUETTE_AI_COACH_PROGRESS_SNAPSHOT_MISSING")
        || rawMessage.includes("缺少训练小单元快照")
    );
}

function aiCoachStreamErrorMessage(
    event: Extract<AiCoachChatStreamEvent, { type: "error" }>,
): string {
    if (
        event.error_code.includes("BUSINESS_ETIQUETTE_AI_COACH_UNIT_NOT_FOUND")
        || event.message.includes("缺少训练小单元快照")
    ) {
        return BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachSessionMissingUnitSnapshot;
    }
    return event.message;
}

function CoachPreparationPanel({
    learningUnits,
    learningUnitsError,
    activityLabel,
    isBusy,
    onResume,
    onNewSession,
}: CoachPreparationPanelProps) {
    const currentUnit =
        learningUnits.find((unit) => unit.enabled) ?? learningUnits[0] ?? null;
    const capabilityNames = currentUnit?.capabilities
        .map((capability) => capability.display_name)
        .filter((displayName) => displayName.trim().length > 0) ?? [];
    return (
        <div className="space-y-6 pb-20">
            <Link
                href="/sales-trainer"
                className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
            >
                <ArrowLeft className="h-4 w-4" />
                {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.backLabel}
            </Link>
            <GlassCard className="space-y-5 p-5 sm:p-6">
                <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-violet-700">
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.pageTitle}
                    </p>
                    <h1 className="text-2xl font-semibold text-slate-950">
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.preparationTitle}
                    </h1>
                    <p className="max-w-2xl text-sm leading-relaxed text-slate-600">
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.preparationDescription}
                    </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-xl border border-slate-200 bg-white/75 p-4">
                        <p className="text-xs font-medium text-slate-500">
                            {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.currentUnitLabel}
                        </p>
                        <h2 className="mt-2 text-base font-semibold text-slate-950">
                            {currentUnit?.title
                                ?? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.fallbackUnitTitle}
                        </h2>
                        <p className="mt-2 text-sm leading-relaxed text-slate-600">
                            {currentUnit?.description
                                ?? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.preparationNoUnit}
                        </p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white/75 p-4">
                        <p className="text-xs font-medium text-slate-500">
                            {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.currentCapabilitiesLabel}
                        </p>
                        <p className="mt-2 text-base font-semibold text-slate-950">
                            {capabilityNames.length > 0
                                ? capabilityNames.join("、")
                                : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.fallbackUnitDescription}
                        </p>
                        <p className="mt-2 text-sm leading-relaxed text-slate-600">
                            {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.preparationUnitSummary}
                        </p>
                    </div>
                </div>

                {learningUnitsError ? (
                    <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                        {learningUnitsError}
                    </p>
                ) : null}
                {activityLabel ? (
                    <p className="rounded-xl border border-violet-100 bg-violet-50 px-4 py-3 text-sm text-violet-800">
                        {activityLabel}
                    </p>
                ) : null}

                <div className="flex flex-col gap-3 sm:flex-row">
                    <Button
                        className="rounded-full"
                        disabled={isBusy}
                        onClick={onResume}
                    >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        {isBusy
                            ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.busyButton
                            : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.resumeButton}
                    </Button>
                    <Button
                        variant="outline"
                        className="rounded-full"
                        disabled={isBusy}
                        onClick={onNewSession}
                    >
                        <PlusCircle className="mr-2 h-4 w-4" />
                        {isBusy
                            ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.newSessionBusyButton
                            : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.newSessionButton}
                    </Button>
                </div>
            </GlassCard>
        </div>
    );
}

export default function AiCoachPage() {
    const [session, setSession] = useState<AiCoachChatSessionPublicV1 | null>(null);
    const [learningUnits, setLearningUnits] = useState<BusinessEtiquetteLearningUnit[]>([]);
    const [learningUnitsError, setLearningUnitsError] = useState<string | null>(null);
    const [coachProgress, setCoachProgress] = useState<BusinessEtiquetteAiCoachProgress | null>(null);
    const [coachProgressError, setCoachProgressError] = useState<string | null>(null);
    const [input, setInput] = useState("");
    const [drafts, setDrafts] = useState<DraftByEventId>({});
    const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
    const [pendingCommand, setPendingCommand] = useState<CoachCommand | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isStarting, setIsStarting] = useState(false);
    const [isSending, setIsSending] = useState(false);
    const [submittingEventIds, setSubmittingEventIds] = useState<ReadonlySet<string>>(
        () => new Set(),
    );
    const [streamActivityLabel, setStreamActivityLabel] = useState<string | null>(null);
    const [streamPhase, setStreamPhase] = useState<AiCoachChatStreamPhase | null>(null);
    const [streamingReasoningText, setStreamingReasoningText] =
        useState<AiCoachReasoningTextDelta | null>(null);
    const [streamingCardDelta, setStreamingCardDelta] =
        useState<AiCoachUiEventDelta | null>(null);
    const [error, setError] = useState<string | null>(null);
    const streamOperationRef = useRef(0);
    const streamAbortRef = useRef<AbortController | null>(null);

    const applyStreamEvent = useCallback((event: AiCoachChatStreamEvent): StreamApplyResult => {
        if (event.type === "status") {
            setStreamActivityLabel(event.message);
            setStreamPhase(event.phase);
            return "status";
        }
        if (event.type === "ui_event_delta") {
            setStreamingCardDelta(event);
            setStreamPhase(event.phase);
            return "delta";
        }
        if (event.type === "assistant_text_delta") {
            setStreamPhase(event.phase);
            return "delta";
        }
        if (event.type === "reasoning_text_delta") {
            setStreamingReasoningText((current) => ({
                ...event,
                text: `${current?.text ?? ""}${event.text}`,
            }));
            setStreamPhase(event.phase);
            return "delta";
        }
        if (event.type === "session_snapshot") {
            setSession(event.session);
            setStreamingReasoningText(null);
            setStreamingCardDelta(null);
            setStreamPhase(event.phase);
            if (event.session.coach_state?.business_etiquette_progress) {
                setCoachProgress(event.session.coach_state.business_etiquette_progress);
                setCoachProgressError(null);
            }
            setIsLoading(false);
            setError(null);
            return "snapshot";
        }
        setStreamActivityLabel(null);
        setStreamingReasoningText(null);
        setStreamingCardDelta(null);
        setStreamPhase(event.phase);
        setError(aiCoachStreamErrorMessage(event));
        return "error";
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
        resumeStrategy: ResumeStrategy,
        options: {
            readonly initialLoad?: boolean;
            readonly clearOnError?: boolean;
        } = {},
    ) => {
        const { controller, operationId } = beginStreamOperation();
        setError(null);
        setStreamPhase(null);
        setStreamingReasoningText(null);
        setStreamingCardDelta(null);
        setIsStarting(true);
        setStreamActivityLabel(
            resumeStrategy === "new"
                ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.loadingNew
                : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.loadingResume,
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
            let streamEventCount = 0;
            let streamFailed = false;
            for await (const event of events) {
                if (!isCurrentStreamOperation(operationId)) {
                    return;
                }
                streamEventCount += 1;
                streamFailed = applyStreamEvent(event) === "error" || streamFailed;
            }
            if (isCurrentStreamOperation(operationId) && streamEventCount === 0) {
                setError(BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamEmptyError);
            }
            if (isCurrentStreamOperation(operationId) && !streamFailed) {
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
                setStreamPhase(null);
            }
        }
    }, [applyStreamEvent, beginStreamOperation, isCurrentStreamOperation]);

    useEffect(() => {
        return () => {
            streamAbortRef.current?.abort();
        };
    }, []);

    useEffect(() => {
        let cancelled = false;
        async function loadLearningUnits() {
            try {
                const response = await api.newcomerTraining.getBusinessEtiquetteLearningUnits();
                if (cancelled) {
                    return;
                }
                setLearningUnits([...response.units].sort((left, right) => (
                    left.order_index - right.order_index
                )));
                setLearningUnitsError(null);
            } catch (loadError) {
                if (cancelled) {
                    return;
                }
                setLearningUnits([]);
                setLearningUnitsError(businessSkillsArticleErrorMessage(loadError));
            }
        }
        void loadLearningUnits();
        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        if (!session) {
            const timer = window.setTimeout(() => {
                setCoachProgress(null);
                setCoachProgressError(null);
            }, 0);
            return () => {
                window.clearTimeout(timer);
            };
        }
        const currentSession = session;
        let cancelled = false;
        async function loadCoachProgress() {
            try {
                const progress =
                    await api.newcomerTraining.getBusinessEtiquetteAiCoachProgress(
                        currentSession.session_id,
                    );
                if (cancelled) {
                    return;
                }
                setCoachProgress(progress);
                setCoachProgressError(null);
            } catch (loadError) {
                if (cancelled) {
                    return;
                }
                setCoachProgress(
                    currentSession.coach_state?.business_etiquette_progress ?? null,
                );
                const message = businessEtiquetteCoachProgressErrorMessage(loadError);
                setCoachProgressError(message);
                if (isBusinessEtiquetteCoachUnitSnapshotError(loadError)) {
                    setError(message);
                }
            }
        }
        void loadCoachProgress();
        return () => {
            cancelled = true;
        };
    }, [session]);

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
        setStreamPhase(null);
        setStreamingReasoningText(null);
        setStreamingCardDelta(null);
        setIsSending(true);
        setPendingUserMessage(message);
        setStreamActivityLabel(BUSINESS_SKILLS_COACH_WORKBENCH_COPY.sendingText);
        try {
            const events = api.newcomerTraining.sendAiCoachChatMessageStream(
                session.session_id,
                { content: message },
                controller.signal,
            );
            let streamEventCount = 0;
            let streamFailed = false;
            for await (const event of events) {
                if (!isCurrentStreamOperation(operationId)) {
                    return;
                }
                streamEventCount += 1;
                streamFailed = applyStreamEvent(event) === "error" || streamFailed;
            }
            if (isCurrentStreamOperation(operationId) && streamEventCount === 0) {
                setError(BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamEmptyError);
            }
            if (isCurrentStreamOperation(operationId) && !streamFailed) {
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
                setStreamPhase(null);
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
        setStreamPhase(null);
        setStreamingReasoningText(null);
        setStreamingCardDelta(null);
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
            let streamEventCount = 0;
            let streamFailed = false;
            for await (const event of events) {
                if (!isCurrentStreamOperation(operationId)) {
                    return;
                }
                streamEventCount += 1;
                streamFailed = applyStreamEvent(event) === "error" || streamFailed;
            }
            if (isCurrentStreamOperation(operationId) && streamEventCount === 0) {
                setError(BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamEmptyError);
            }
            if (isCurrentStreamOperation(operationId) && !streamFailed) {
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
                setStreamPhase(null);
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
            setStreamPhase(null);
            setStreamingReasoningText(null);
            setStreamingCardDelta(null);
            setStreamActivityLabel(BUSINESS_SKILLS_COACH_WORKBENCH_COPY.scoringAnswer);
            setSubmittingEventIds((current) => new Set(current).add(event.event_id));
            try {
                const events = api.newcomerTraining.submitAiCoachChatEventAnswerStream(
                    session.session_id,
                    event.event_id,
                    { answer_payload: answerPayload },
                    controller.signal,
                );
                let streamEventCount = 0;
                let streamFailed = false;
                for await (const streamEvent of events) {
                    if (!isCurrentStreamOperation(operationId)) {
                        return;
                    }
                    streamEventCount += 1;
                    streamFailed = applyStreamEvent(streamEvent) === "error" || streamFailed;
                }
                if (isCurrentStreamOperation(operationId) && streamEventCount === 0) {
                    setError(BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamEmptyError);
                }
                if (isCurrentStreamOperation(operationId) && !streamFailed) {
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
                    setStreamPhase(null);
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

    if (!session && error) {
        return (
            <div className="space-y-6 pb-20">
                <Link
                    href="/sales-trainer"
                    className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
                >
                    <ArrowLeft className="h-4 w-4" />
                    {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.backLabel}
                </Link>
                <GlassCard className="space-y-4 p-6">
                    <h1 className="text-xl font-semibold text-slate-950">
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.unavailableTitle}
                    </h1>
                    <p className="text-sm leading-relaxed text-red-700">
                        {error || BUSINESS_SKILLS_COACH_WORKBENCH_COPY.unavailableDescription}
                    </p>
                    <Button
                        variant="outline"
                        className="rounded-full"
                        onClick={() => void startSession("latest_in_progress")}
                    >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.retryButton}
                    </Button>
                </GlassCard>
            </div>
        );
    }

    if (!session) {
        return (
            <CoachPreparationPanel
                learningUnits={learningUnits}
                learningUnitsError={learningUnitsError}
                activityLabel={streamActivityLabel}
                isBusy={isStarting}
                onResume={() => void startSession("latest_in_progress")}
                onNewSession={() => void startSession("new")}
            />
        );
    }

    return (
        <div className="space-y-4 pb-4">
            <Link
                href="/sales-trainer"
                className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
            >
                <ArrowLeft className="h-4 w-4" />
                {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.backLabel}
            </Link>
            <AiCoachChatSurface
                session={session}
                learningUnits={learningUnits}
                learningUnitsError={learningUnitsError}
                coachProgress={coachProgress}
                coachProgressError={coachProgressError}
                input={input}
                drafts={drafts}
                pendingUserMessage={pendingUserMessage}
                isStarting={isStarting}
                isSending={isSending}
                pendingCommand={pendingCommand}
                submittingEventIds={submittingEventIds}
                streamActivityLabel={streamActivityLabel}
                streamPhase={streamPhase}
                streamingReasoningText={streamingReasoningText}
                streamingCardDelta={streamingCardDelta}
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
