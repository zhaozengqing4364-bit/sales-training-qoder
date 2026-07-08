"use client";

import Link from "next/link";
import { useEffect, useRef, type FormEvent, type ReactNode } from "react";
import {
    ArrowLeft,
    BookOpenCheck,
    Bot,
    CheckCircle2,
    ClipboardList,
    Lightbulb,
    ListChecks,
    MessageSquareText,
    RefreshCw,
    RotateCcw,
    Send,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import type {
    AiCoachAnswerPayloadV1,
    AiCoachChatSessionPublicV1,
    AiCoachChatStreamEvent,
    AiCoachChatStreamPhase,
    AiCoachScoreResultV1,
    AiCoachUiEventPublicV1,
    BusinessEtiquetteAiCoachProgress,
    BusinessEtiquetteLearningUnit,
} from "@/lib/api/types";

import { CoachMessageList } from "./coach-message-list";
import {
    buildCoachConversationViewModel,
    type CoachCommand,
    type DraftByEventId,
    type QuizCardEvent,
    type StreamingAssistantText,
    type SummaryCardEvent,
} from "./coach-session";
import {
    BUSINESS_SKILLS_COACH_CARD_TYPE_LABELS,
    BUSINESS_SKILLS_COACH_COMMAND_LABELS,
    BUSINESS_SKILLS_COACH_DIFFICULTY_LABELS,
    BUSINESS_SKILLS_COACH_NEXT_ACTION_LABELS,
    BUSINESS_SKILLS_COACH_PHASE_LABELS,
    BUSINESS_SKILLS_COACH_PROGRESS_LABELS,
    BUSINESS_SKILLS_COACH_WORKBENCH_COPY,
    BUSINESS_SKILLS_COACH_WORKBENCH_RULES,
} from "./coach-workbench-config";

interface AiCoachChatSurfaceProps {
    readonly session: AiCoachChatSessionPublicV1 | null;
    readonly learningUnits: readonly BusinessEtiquetteLearningUnit[];
    readonly learningUnitsError: string | null;
    readonly coachProgress: BusinessEtiquetteAiCoachProgress | null;
    readonly coachProgressError: string | null;
    readonly input: string;
    readonly drafts: DraftByEventId;
    readonly pendingUserMessage: string | null;
    readonly isStarting: boolean;
    readonly isSending: boolean;
    readonly pendingCommand: CoachCommand | null;
    readonly submittingEventIds: ReadonlySet<string>;
    readonly streamActivityLabel: string | null;
    readonly streamPhase: AiCoachChatStreamPhase | null;
    readonly streamingAssistantText: StreamingAssistantText | null;
    readonly streamingCardDelta: Extract<AiCoachChatStreamEvent, { type: "ui_event_delta" }> | null;
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
    learningUnits,
    learningUnitsError,
    coachProgress,
    coachProgressError,
    input,
    drafts,
    pendingUserMessage,
    isStarting,
    isSending,
    pendingCommand,
    submittingEventIds,
    streamActivityLabel,
    streamPhase,
    streamingAssistantText,
    streamingCardDelta,
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
    const viewModel = buildCoachConversationViewModel({
        session,
        learningUnits,
        coachProgress,
        pendingUserMessage,
        streamingAssistantText,
    });
    const activityLabel = streamActivityLabel
        ?? activityLabelFor(pendingCommand, isSending, isAdvancing, isStarting);
    const hasStreamingAssistantText = Boolean(streamingAssistantText?.text.trim());
    const showStreamingResponse = shouldShowStreamingCoachResponse({
        isStarting,
        isSending,
        isAdvancing,
        streamPhase,
        streamingAssistantText,
        streamingCardDelta,
        activeQuiz: viewModel.activeQuiz,
    });
    const streamingCardAttachment = streamingCardDelta ? (
        <StreamingTrainingCard
            activityLabel={activityLabel}
            currentUnit={viewModel.currentUnit}
            delta={streamingCardDelta}
        />
    ) : null;
    const streamingPreview = showStreamingResponse && !hasStreamingAssistantText ? (
        <StreamingCoachResponse
            activityLabel={activityLabel}
            currentUnit={viewModel.currentUnit}
            cardDelta={streamingCardDelta}
        />
    ) : null;
    const streamingInteraction = streamingCardDelta?.payload.interaction ?? null;
    const streamingScrollKey = [
        streamPhase ?? "",
        streamingAssistantText?.text.length ?? 0,
        streamingCardDelta?.delta_id ?? "",
        streamingInteraction?.stem?.length ?? 0,
        streamingInteraction?.options?.length ?? 0,
        activityLabel ?? "",
    ].join(":");

    return (
        <section className="mx-auto flex h-[calc(100dvh-4rem)] min-h-0 w-full max-w-7xl flex-col overflow-hidden rounded-2xl border border-slate-200/80 bg-stone-50/80 shadow-[0_24px_70px_-36px_rgba(15,23,42,0.24)]">
            <WorkbenchHeader
                session={session}
                isBusy={isBusy}
                isStarting={isStarting}
                onResume={onResume}
                onNewSession={onNewSession}
            />
            <main className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-3 lg:grid lg:grid-cols-[minmax(0,1fr)_21rem] lg:p-4">
                <section className="order-1 flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white/90 shadow-sm lg:order-none">
                    <ConversationHeader
                        currentUnit={viewModel.currentUnit}
                        activityLabel={activityLabel}
                        isBusy={isBusy}
                    />
                    <CoachErrorBanner message={error} />
                    <CoachMessageList
                        viewModel={viewModel}
                        drafts={drafts}
                        submittingEventIds={submittingEventIds}
                        isStarting={isStarting}
                        isSending={isSending}
                        isAdvancing={isAdvancing}
                        activityLabel={activityLabel}
                        error={null}
                        autoScrollKey={streamingScrollKey}
                        trailingNode={streamingPreview}
                        streamingMetaNode={<StreamingStatusLine activityLabel={activityLabel} />}
                        streamingAttachmentNode={hasStreamingAssistantText ? streamingCardAttachment : null}
                        commandBar={
                            <CoachInlineCommandBar
                                disabled={!session || isBusy}
                                hasActiveQuiz={viewModel.activeQuiz !== null}
                                pendingCommand={pendingCommand}
                                onCommand={onCoachCommand}
                            />
                        }
                        className="min-h-0 flex-1 space-y-6 overflow-y-auto overscroll-contain px-4 py-4 md:px-6"
                        onFollowupPrompt={onFollowupPrompt}
                        onDraftChange={onDraftChange}
                        onSubmitEvent={onSubmitEvent}
                    />
                    {BUSINESS_SKILLS_COACH_WORKBENCH_RULES.showFreeFollowup ? (
                        <Composer
                            value={input}
                            disabled={!session || isBusy}
                            hasActiveQuiz={viewModel.activeQuiz !== null}
                            onChange={onInputChange}
                            onSubmit={onSend}
                        />
                    ) : null}
                </section>
                <TrainingStatusSidebar
                    session={session}
                    viewModel={viewModel}
                    learningUnitsError={learningUnitsError}
                    coachProgress={coachProgress}
                    coachProgressError={coachProgressError}
                />
            </main>
        </section>
    );
}

function WorkbenchHeader({
    session,
    isBusy,
    isStarting,
    onResume,
    onNewSession,
}: {
    readonly session: AiCoachChatSessionPublicV1 | null;
    readonly isBusy: boolean;
    readonly isStarting: boolean;
    readonly onResume: () => void;
    readonly onNewSession: () => void;
}) {
    return (
        <header className="shrink-0 border-b border-slate-200 bg-white/95 px-4 py-2.5 backdrop-blur">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex min-w-0 items-center gap-3">
                    <Link
                        href="/sales-trainer"
                        className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs font-semibold text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
                    >
                        <ArrowLeft className="h-3.5 w-3.5" />
                        返回
                    </Link>
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-50 text-violet-600">
                        <Bot className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                        <h1 className="truncate text-base font-black text-slate-950">
                            {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.pageTitle}
                        </h1>
                        <p className="truncate text-xs text-slate-500">
                            {session
                                ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.activeSessionSubtitle
                                : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.startingSessionSubtitle}
                        </p>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Button
                        variant="primary"
                        size="sm"
                        className="rounded-full"
                        disabled={isBusy}
                        onClick={onResume}
                    >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        {isStarting
                            ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.busyButton
                            : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.resumeButton}
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        className="rounded-full"
                        disabled={isBusy}
                        onClick={onNewSession}
                    >
                        <RotateCcw className="mr-2 h-4 w-4" />
                        {isStarting
                            ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.newSessionBusyButton
                            : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.newSessionButton}
                    </Button>
                </div>
            </div>
        </header>
    );
}

function ConversationHeader({
    currentUnit,
    activityLabel,
    isBusy,
}: {
    readonly currentUnit: BusinessEtiquetteLearningUnit | null;
    readonly activityLabel: string | null;
    readonly isBusy: boolean;
}) {
    return (
        <div className="shrink-0 border-b border-slate-200 bg-white/80 px-4 py-3 md:px-5">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-500">对话陪练</p>
                    <h2 className="mt-1 truncate text-sm font-black text-slate-950">
                        {currentUnit?.title ?? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.fallbackUnitTitle}
                    </h2>
                </div>
                {isBusy && activityLabel ? (
                    <span
                        aria-live="polite"
                        className="inline-flex shrink-0 items-center gap-2 rounded-full bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700"
                    >
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
                        {activityLabel}
                    </span>
                ) : null}
            </div>
        </div>
    );
}

function CoachErrorBanner({
    message,
}: {
    readonly message: string | null;
}) {
    if (!message) {
        return null;
    }
    return (
        <section className="mx-4 mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-800 md:mx-5">
            <p className="font-semibold text-amber-900">
                {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamErrorTitle}
            </p>
            <p className="mt-1">{message}</p>
        </section>
    );
}

function StreamingCoachResponse({
    activityLabel,
    currentUnit,
    cardDelta,
}: {
    readonly activityLabel: string | null;
    readonly currentUnit: BusinessEtiquetteLearningUnit | null;
    readonly cardDelta: Extract<AiCoachChatStreamEvent, { type: "ui_event_delta" }> | null;
}) {
    return (
        <div aria-live="polite" className="max-w-[72ch] space-y-3">
            <div className="rounded-2xl rounded-tl-md border border-slate-200 bg-white px-4 py-3 text-sm leading-7 text-slate-800 shadow-sm">
                <p className="text-sm leading-7 text-slate-500">
                    {activityLabel ?? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.defaultThinkingLabel}
                </p>
            </div>
            {cardDelta ? (
                <StreamingTrainingCard
                    activityLabel={activityLabel}
                    currentUnit={currentUnit}
                    delta={cardDelta}
                />
            ) : null}
        </div>
    );
}

function StreamingStatusLine({
    activityLabel,
}: {
    readonly activityLabel: string | null;
}) {
    if (!activityLabel) {
        return null;
    }
    return (
        <p className="mt-2 text-xs font-medium leading-5 text-slate-500">
            {activityLabel}
        </p>
    );
}

function StreamingTrainingCard({
    activityLabel,
    currentUnit,
    delta,
}: {
    readonly activityLabel: string | null;
    readonly currentUnit: BusinessEtiquetteLearningUnit | null;
    readonly delta: Extract<AiCoachChatStreamEvent, { type: "ui_event_delta" }>;
}) {
    const interaction = delta.payload.interaction;
    const options = interaction.options ?? [];
    const interactionType = interaction.interaction_type ?? null;
    const trainingCardType = interaction.training_card_type ?? null;
    const chapters = interaction.source_chapter_orders ?? currentUnit?.source_chapter_orders ?? [];
    const capabilityKeys = interaction.capability_keys ?? currentUnit?.capability_keys ?? [];
    return (
        <section
            aria-live="polite"
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
        >
            <div className="flex items-start justify-between gap-4">
                <div className="flex flex-wrap gap-2">
                    <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamingCardTitle}
                    </span>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
                        {trainingCardType
                            ? BUSINESS_SKILLS_COACH_CARD_TYPE_LABELS[trainingCardType]
                            : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamingCardPreviewBadge}
                    </span>
                    {interactionType ? (
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
                            {interactionType === "single_choice"
                                ? "单选"
                                : interactionType === "multiple_choice"
                                    ? "多选"
                                    : "简答"}
                        </span>
                    ) : null}
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500">
                    {activityLabel ?? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamingCardActivityFallback}
                </span>
            </div>
            <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-xs font-semibold text-slate-500">
                    {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamingCardUnitLabel}
                </p>
                <p className="mt-1 text-sm font-semibold text-slate-950">
                    {currentUnit?.title ?? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.fallbackUnitTitle}
                </p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                    {capabilityKeys.length > 0 ? (
                        <span className="rounded-full bg-white px-2.5 py-1 font-medium">
                            {capabilityKeys.join("、")}
                        </span>
                    ) : null}
                    {chapters.length > 0 ? (
                        <span className="rounded-full bg-white px-2.5 py-1 font-medium">
                            关联第 {chapters.join("、")} 章
                        </span>
                    ) : null}
                </div>
            </div>
            <h3 className="mt-5 text-lg font-semibold leading-snug text-slate-950">
                {interaction.stem?.trim()
                    || BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamingCardStemPlaceholder}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
                {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamingCardDescription}
            </p>
            <div className="mt-4 space-y-2">
                {interactionType === "short_answer" ? (
                    <textarea
                        disabled
                        rows={4}
                        className="w-full resize-none rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-400"
                        placeholder="题目生成完成后可输入回答"
                    />
                ) : options.length > 0 ? (
                    options.map((option) => (
                        <button
                            key={option.option_id}
                            type="button"
                            disabled
                            className="flex w-full cursor-not-allowed items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm text-slate-500"
                        >
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border bg-white text-xs font-bold">
                                {option.option_id}
                            </span>
                            <span className="flex-1">{option.text}</span>
                        </button>
                    ))
                ) : (
                    <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-sm font-medium text-slate-400">
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamingCardOptionPlaceholder}
                    </div>
                )}
            </div>
            <div className="mt-4 flex justify-end">
                <Button className="rounded-full" disabled>
                    {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.streamingCardSubmitPlaceholder}
                </Button>
            </div>
        </section>
    );
}

function TrainingStatusSidebar({
    session,
    viewModel,
    learningUnitsError,
    coachProgress,
    coachProgressError,
}: {
    readonly session: AiCoachChatSessionPublicV1 | null;
    readonly viewModel: ReturnType<typeof buildCoachConversationViewModel>;
    readonly learningUnitsError: string | null;
    readonly coachProgress: BusinessEtiquetteAiCoachProgress | null;
    readonly coachProgressError: string | null;
}) {
    const sidebarDetailsRef = useRef<HTMLDetailsElement | null>(null);
    const state = session?.coach_state;
    const phaseLabel = state
        ? BUSINESS_SKILLS_COACH_PHASE_LABELS[state.session_phase]
        : "准备中";
    const difficultyLabel = state
        ? BUSINESS_SKILLS_COACH_DIFFICULTY_LABELS[state.difficulty]
        : "热身";
    const nextActionLabel = state?.last_action
        ? BUSINESS_SKILLS_COACH_NEXT_ACTION_LABELS[state.last_action]
        : "准备第一题";
    const masteryLabel = coachProgress
        ? BUSINESS_SKILLS_COACH_PROGRESS_LABELS[coachProgress.status]
        : masteryLabelFor(viewModel.referenceQuiz);
    const unitWarning = learningUnitsError
        ?? (viewModel.currentUnit ? null : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.learningUnitsUnavailable);

    useEffect(() => {
        if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
            return;
        }
        const query = window.matchMedia("(min-width: 1024px)");
        const applyDefaultOpen = () => {
            if (sidebarDetailsRef.current) {
                sidebarDetailsRef.current.open = query.matches;
            }
        };
        applyDefaultOpen();
        query.addEventListener("change", applyDefaultOpen);
        return () => {
            query.removeEventListener("change", applyDefaultOpen);
        };
    }, []);

    return (
        <aside className="order-2 max-h-[42dvh] shrink-0 overflow-y-auto overscroll-contain lg:order-none lg:max-h-none lg:min-h-0">
            <details
                ref={sidebarDetailsRef}
                className="rounded-2xl border border-slate-200 bg-white/85 shadow-sm"
            >
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 marker:hidden">
                    <span className="flex min-w-0 items-center gap-2">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                            <ListChecks className="h-4 w-4" />
                        </span>
                        <span className="min-w-0">
                            <span className="block text-sm font-black text-slate-950">
                                当前训练状态
                            </span>
                            <span className="block truncate text-xs text-slate-500">
                                {phaseLabel} · {nextActionLabel}
                            </span>
                        </span>
                    </span>
                    <span className="text-xs font-semibold text-slate-400">展开/收起</span>
                </summary>
                <div className="space-y-4 border-t border-slate-200 px-4 py-4">
                    <SidebarBlock
                        icon={<BookOpenCheck className="h-4 w-4" />}
                        title={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.roundGoalLabel}
                    >
                        <p className="text-sm font-semibold leading-relaxed text-slate-950">
                            {viewModel.currentUnit?.title ?? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.fallbackUnitTitle}
                        </p>
                        <p className="mt-1 text-xs leading-5 text-slate-500">
                            {viewModel.currentUnit?.description
                                ?? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.fallbackUnitDescription}
                        </p>
                    </SidebarBlock>

                    <div className="flex flex-wrap gap-2">
                        <StatusPill label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.activityLabel} value={phaseLabel} />
                        <StatusPill label="难度" value={difficultyLabel} />
                        <StatusPill label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachProgressLabel} value={masteryLabel} />
                    </div>

                    {unitWarning ? (
                        <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-700">
                            {unitWarning}
                        </p>
                    ) : null}

                    <SidebarBlock
                        icon={<MessageSquareText className="h-4 w-4" />}
                        title={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.currentCapabilitiesLabel}
                    >
                        <CapabilityList
                            currentUnit={viewModel.currentUnit}
                            referenceQuiz={viewModel.referenceQuiz}
                        />
                    </SidebarBlock>

                    <SidebarBlock
                        icon={<CheckCircle2 className="h-4 w-4" />}
                        title={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachProgressLabel}
                    >
                        <ProgressPanel
                            coachProgress={coachProgress}
                            coachProgressError={coachProgressError}
                        />
                    </SidebarBlock>

                    <SidebarBlock
                        icon={<ClipboardList className="h-4 w-4" />}
                        title={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.conversationEvidenceTitle}
                    >
                        <EvidenceSummary
                            viewModel={viewModel}
                            latestScoredQuiz={viewModel.latestScoredQuiz}
                            summaryEvent={viewModel.latestSummary}
                        />
                    </SidebarBlock>
                </div>
            </details>
        </aside>
    );
}

function SidebarBlock({
    icon,
    title,
    children,
}: {
    readonly icon: ReactNode;
    readonly title: string;
    readonly children: ReactNode;
}) {
    return (
        <section>
            <div className="flex items-center gap-2 text-slate-700">
                <span className="text-violet-600">{icon}</span>
                <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
            </div>
            <div className="mt-2">{children}</div>
        </section>
    );
}

function StatusPill({
    label,
    value,
}: {
    readonly label: string;
    readonly value: string;
}) {
    return (
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
            {label}：{value}
        </span>
    );
}

function CapabilityList({
    currentUnit,
    referenceQuiz,
}: {
    readonly currentUnit: BusinessEtiquetteLearningUnit | null;
    readonly referenceQuiz: QuizCardEvent | null;
}) {
    const labels = capabilityLabelsFor(currentUnit, referenceQuiz);
    if (labels.length === 0) {
        return (
            <p className="text-sm leading-relaxed text-slate-500">
                {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.fallbackUnitDescription}
            </p>
        );
    }
    return (
        <div className="flex flex-wrap gap-2">
            {labels.map((label) => (
                <span key={label} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                    {label}
                </span>
            ))}
        </div>
    );
}

function ProgressPanel({
    coachProgress,
    coachProgressError,
}: {
    readonly coachProgress: BusinessEtiquetteAiCoachProgress | null;
    readonly coachProgressError: string | null;
}) {
    if (!coachProgress) {
        return (
            <div className="rounded-xl bg-slate-50 px-3 py-3">
                <p className="font-semibold text-slate-900">
                    {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachProgressUnavailable}
                </p>
                {coachProgressError ? (
                    <p className="mt-1 text-sm leading-relaxed text-amber-700">
                        {coachProgressError}
                    </p>
                ) : null}
            </div>
        );
    }
    return (
        <div className="space-y-3">
            <div className="flex flex-wrap gap-2 text-xs">
                <span className={`rounded-full px-3 py-1 font-semibold ${
                    coachProgress.passed
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-700"
                }`}>
                    {BUSINESS_SKILLS_COACH_PROGRESS_LABELS[coachProgress.status]}
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 font-semibold text-slate-600">
                    {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachProgressCards}
                    ：{coachProgress.scored_card_count}
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 font-semibold text-slate-600">
                    {coachProgress.remediation_attempt_count}/{coachProgress.max_remediation_attempts} 次补救
                </span>
            </div>
            <p className="text-sm leading-relaxed text-slate-700">
                {coachProgress.next_step}
            </p>
            <CapabilityScoreList progress={coachProgress} />
            {coachProgress.weak_capability_keys.length > 0 ? (
                <FeedbackList
                    label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachWeakCapabilities}
                    items={capabilityDisplayNames(
                        coachProgress,
                        coachProgress.weak_capability_keys,
                    )}
                />
            ) : null}
            {coachProgress.recommended_chapter_orders.length > 0 ? (
                <FeedbackList
                    label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachRecommendedChapters}
                    items={coachProgress.recommended_chapter_orders.map((order) => (
                        `第 ${order} 章`
                    ))}
                />
            ) : null}
            {coachProgress.recommended_training_card_types.length > 0 ? (
                <FeedbackList
                    label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachRecommendedCards}
                    items={coachProgress.recommended_training_card_types.map((type) => (
                        BUSINESS_SKILLS_COACH_CARD_TYPE_LABELS[type]
                    ))}
                />
            ) : null}
        </div>
    );
}

function CapabilityScoreList({
    progress,
}: {
    readonly progress: BusinessEtiquetteAiCoachProgress;
}) {
    if (progress.capability_scores.length === 0) {
        return null;
    }
    return (
        <div className="space-y-2">
            {progress.capability_scores.map((score) => (
                <div key={score.capability_key} className="rounded-lg bg-slate-50 px-3 py-2">
                    <div className="flex items-center justify-between gap-2 text-xs">
                        <span className="font-semibold text-slate-700">
                            {score.display_name}
                        </span>
                        <span className="font-semibold text-slate-500">
                            {typeof score.normalized_score === "number"
                                ? `${Math.round(score.normalized_score)}%`
                                : "--"}
                        </span>
                    </div>
                    <p className="mt-1 text-[11px] text-slate-500">
                        {score.mastery_level_name ?? "暂无等级"} · 达标线 {Math.round(score.threshold)}%
                    </p>
                </div>
            ))}
        </div>
    );
}

function EvidenceSummary({
    viewModel,
    latestScoredQuiz,
    summaryEvent,
}: {
    readonly viewModel: ReturnType<typeof buildCoachConversationViewModel>;
    readonly latestScoredQuiz: QuizCardEvent | null;
    readonly summaryEvent: SummaryCardEvent | null;
}) {
    const latestScore = latestScoredQuiz?.score_result ?? null;
    return (
        <div className="space-y-3">
            <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <EvidenceMetric label="消息" value={viewModel.timeline.length} />
                <EvidenceMetric label="训练卡" value={viewModel.quizCardCount} />
                <EvidenceMetric label="已评分" value={viewModel.scoredQuizCardCount} />
            </div>
            {latestScore ? <ScoreSummary scoreResult={latestScore} /> : null}
            {summaryEvent ? <EndPanel summaryEvent={summaryEvent} latestScoredQuiz={latestScoredQuiz} /> : null}
        </div>
    );
}

function EvidenceMetric({
    label,
    value,
}: {
    readonly label: string;
    readonly value: number;
}) {
    return (
        <div className="rounded-xl bg-slate-50 px-2 py-2">
            <p className="font-black text-slate-950">{value}</p>
            <p className="mt-0.5 text-slate-500">{label}</p>
        </div>
    );
}

function EndPanel({
    summaryEvent,
    latestScoredQuiz,
}: {
    readonly summaryEvent: SummaryCardEvent | null;
    readonly latestScoredQuiz: QuizCardEvent | null;
}) {
    const summary = summaryEvent?.payload ?? null;
    const mastered = summary?.mastered ?? latestScoredQuiz?.score_result?.mastered ?? null;
    if (!summary) {
        return null;
    }
    return (
        <div className="rounded-xl bg-slate-50 px-3 py-3">
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                mastered ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
            }`}>
                {mastered
                    ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.endPanelMastered
                    : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.endPanelNotMastered}
            </span>
            {summary.items.length > 0 ? (
                <ul className="mt-3 space-y-2 text-sm text-slate-700">
                    {summary.items.map((item) => (
                        <li key={item}>{item}</li>
                    ))}
                </ul>
            ) : null}
        </div>
    );
}

function ScoreSummary({
    scoreResult,
}: {
    readonly scoreResult: AiCoachScoreResultV1;
}) {
    const percent = scoreResult.max_score > 0
        ? Math.round((scoreResult.score / scoreResult.max_score) * 100)
        : null;
    return (
        <div className="flex flex-wrap gap-2 text-xs">
            <span className={`rounded-full px-3 py-1 font-semibold ${
                scoreResult.mastered ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
            }`}>
                {scoreResult.mastered ? "已达标" : "继续练习"}
            </span>
            {percent !== null ? (
                <span className="rounded-full bg-slate-100 px-3 py-1 font-semibold text-slate-600">
                    {percent}%
                </span>
            ) : null}
            {typeof scoreResult.mastery_threshold === "number" ? (
                <span className="rounded-full bg-slate-100 px-3 py-1 font-semibold text-slate-600">
                    通过线 {Math.round(scoreResult.mastery_threshold)}%
                </span>
            ) : null}
        </div>
    );
}

function FeedbackList({
    label,
    items,
}: {
    readonly label: string;
    readonly items: readonly string[];
}) {
    if (items.length === 0) {
        return null;
    }
    return (
        <div className="mt-3">
            <p className="text-xs font-semibold text-slate-500">{label}</p>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
                {items.map((item) => (
                    <li key={item} className="rounded-lg bg-slate-50 px-3 py-2">
                        {item}
                    </li>
                ))}
            </ul>
        </div>
    );
}

function CoachInlineCommandBar({
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
        readonly disabled?: boolean;
        readonly icon: ReactNode;
    }[] = [
        {
            command: "continue",
            disabled: hasActiveQuiz && !BUSINESS_SKILLS_COACH_WORKBENCH_RULES.allowSkipActiveCard,
            icon: <CheckCircle2 className="h-4 w-4" />,
        },
        { command: "explain", icon: <Lightbulb className="h-4 w-4" /> },
        { command: "switch_scenario", icon: <RotateCcw className="h-4 w-4" /> },
        { command: "summarize", icon: <ClipboardList className="h-4 w-4" /> },
    ];
    return (
        <div className="flex flex-wrap items-center gap-2">
            {commands.map((item) => (
                <Button
                    key={item.command}
                    type="button"
                    variant={item.command === "continue" ? "primary" : "ghost"}
                    size="sm"
                    className="rounded-full"
                    disabled={disabled || item.disabled === true}
                    onClick={() => onCommand(item.command)}
                >
                    {item.icon}
                    <span className="ml-1.5">
                        {pendingCommand === item.command
                            ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.busyButton
                            : BUSINESS_SKILLS_COACH_COMMAND_LABELS[item.command]}
                    </span>
                </Button>
            ))}
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
            className="shrink-0 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:px-5"
        >
            <div className="flex items-end gap-3 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-sm">
                <textarea
                    value={value}
                    disabled={disabled}
                    onChange={(event) => onChange(event.target.value)}
                    placeholder={
                        hasActiveQuiz
                            ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.followupPlaceholderWhenActive
                            : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.followupPlaceholderDefault
                    }
                    rows={1}
                    className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-3 py-2 text-sm leading-relaxed text-slate-900 outline-none placeholder:text-slate-400"
                />
                <Button
                    type="submit"
                    variant="primary"
                    disabled={disabled || !value.trim()}
                    className="h-10 rounded-xl px-4"
                    aria-label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.sendAriaLabel}
                >
                    <Send className="h-4 w-4" />
                </Button>
            </div>
        </form>
    );
}

function capabilityLabelsFor(
    currentUnit: BusinessEtiquetteLearningUnit | null,
    referenceQuiz: QuizCardEvent | null,
): string[] {
    const capabilityKeys = referenceQuiz?.payload.interaction.capability_keys ?? [];
    if (!currentUnit) {
        return [...capabilityKeys];
    }
    const displayByKey = new Map(
        currentUnit.capabilities.map((capability) => [
            capability.capability_key,
            capability.display_name,
        ]),
    );
    if (capabilityKeys.length > 0) {
        return capabilityKeys.map((key) => displayByKey.get(key) ?? key);
    }
    return currentUnit.capabilities.map((capability) => capability.display_name);
}

function capabilityDisplayNames(
    progress: BusinessEtiquetteAiCoachProgress,
    capabilityKeys: readonly string[],
): string[] {
    const displayByKey = new Map(
        progress.capability_scores.map((score) => [
            score.capability_key,
            score.display_name,
        ]),
    );
    return capabilityKeys.map((key) => displayByKey.get(key) ?? key);
}

function masteryLabelFor(referenceQuiz: QuizCardEvent | null): string {
    const result = referenceQuiz?.score_result;
    if (!result) {
        return "训练中";
    }
    if (result.mastered === true) {
        return "已达标";
    }
    if (result.mastered === false) {
        return "继续练习";
    }
    return result.score >= result.max_score ? "已达标" : "继续练习";
}

function activityLabelFor(
    pendingCommand: CoachCommand | null,
    isSending: boolean,
    isAdvancing: boolean,
    isStarting: boolean,
): string | null {
    if (isStarting) {
        return "教练正在组织下一步训练";
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
            return "教练正在组织下一步训练";
    }
}

function isStreamingTrainingCardPhase(
    phase: AiCoachChatStreamPhase | null,
): boolean {
    return phase === "generating_first_card"
        || phase === "generating_next_card"
        || phase === "deciding_next_action";
}

function shouldShowStreamingCoachResponse({
    isStarting,
    isSending,
    isAdvancing,
    streamPhase,
    streamingAssistantText,
    streamingCardDelta,
    activeQuiz,
}: {
    readonly isStarting: boolean;
    readonly isSending: boolean;
    readonly isAdvancing: boolean;
    readonly streamPhase: AiCoachChatStreamPhase | null;
    readonly streamingAssistantText: StreamingAssistantText | null;
    readonly streamingCardDelta: Extract<AiCoachChatStreamEvent, { type: "ui_event_delta" }> | null;
    readonly activeQuiz: QuizCardEvent | null;
}): boolean {
    if (streamingAssistantText?.text.trim() || streamingCardDelta !== null) {
        return true;
    }
    if (!isStarting && !isSending && !isAdvancing) {
        return false;
    }
    return isStreamingTrainingCardPhase(streamPhase) && activeQuiz === null;
}
