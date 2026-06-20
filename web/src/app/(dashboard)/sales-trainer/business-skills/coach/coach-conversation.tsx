"use client";

import type { FormEvent, ReactNode } from "react";
import {
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
    activeEventIdForSession,
    activeQuizEventForSession,
    latestScoredQuizEventForSession,
    latestSummaryEventForSession,
    resolveCurrentLearningUnit,
    trainingReferenceEventForSession,
    type CoachCommand,
    type DraftByEventId,
    type QuizCardEvent,
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
    readonly streamingReasoningText: Extract<AiCoachChatStreamEvent, { type: "reasoning_text_delta" }> | null;
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
    streamingReasoningText,
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
    const activeEventId = activeEventIdForSession(session);
    const activeQuiz = activeQuizEventForSession(session);
    const latestScoredQuiz = latestScoredQuizEventForSession(session);
    const referenceQuiz = trainingReferenceEventForSession(session);
    const summaryEvent = latestSummaryEventForSession(session);
    const progressUnit = coachProgress
        ? learningUnits.find((unit) => unit.unit_key === coachProgress.learning_unit_key)
        : null;
    const currentUnit = progressUnit ?? resolveCurrentLearningUnit(learningUnits, referenceQuiz);
    const activityLabel = streamActivityLabel
        ?? activityLabelFor(pendingCommand, isSending, isAdvancing, isStarting);
    const shouldShowStreamingResponse = shouldShowStreamingCoachResponse({
        isStarting,
        isSending,
        isAdvancing,
        streamPhase,
        streamingReasoningText,
        streamingCardDelta,
        activeQuiz,
    });
    const streamingPreview = shouldShowStreamingResponse ? (
        <StreamingCoachResponse
            activityLabel={activityLabel}
            currentUnit={currentUnit}
            reasoningText={streamingReasoningText?.text ?? ""}
            cardDelta={streamingCardDelta}
        />
    ) : null;
    const streamingInteraction = streamingCardDelta?.payload.interaction ?? null;
    const streamingScrollKey = [
        streamPhase ?? "",
        streamingReasoningText?.text.length ?? 0,
        streamingCardDelta?.delta_id ?? "",
        streamingInteraction?.stem?.length ?? 0,
        streamingInteraction?.options?.length ?? 0,
        activityLabel ?? "",
    ].join(":");
    return (
        <section className="mx-auto flex h-[calc(100dvh-6rem)] min-h-0 w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200/80 bg-slate-50/80 shadow-[0_24px_70px_-36px_rgba(15,23,42,0.24)]">
            <WorkbenchHeader
                session={session}
                isBusy={isBusy}
                isStarting={isStarting}
                onResume={onResume}
                onNewSession={onNewSession}
                onEnd={() => onCoachCommand("end")}
            />
            <main className="flex min-h-0 flex-1 flex-col px-3 py-3 md:px-4 lg:px-5">
                <TrainingContextPanel
                    session={session}
                    currentUnit={currentUnit}
                    referenceQuiz={referenceQuiz}
                    coachProgress={coachProgress}
                    coachProgressError={coachProgressError}
                    learningUnitsError={learningUnitsError}
                />
                <CoachErrorBanner message={error} />
                <div className="mt-3 min-h-0 flex-1 overflow-hidden rounded-xl border border-slate-200 bg-slate-100/60">
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
                        autoScrollKey={streamingScrollKey}
                        trailingNode={streamingPreview}
                        className="h-full min-h-0 space-y-3 overflow-y-auto overscroll-contain px-3 py-3 md:px-4"
                        onFollowupPrompt={onFollowupPrompt}
                        onDraftChange={onDraftChange}
                        onSubmitEvent={onSubmitEvent}
                    />
                </div>
                {summaryEvent ? (
                    <CoachGuidancePanel
                        latestScoredQuiz={latestScoredQuiz}
                        summaryEvent={summaryEvent}
                        coachProgress={coachProgress}
                        coachProgressError={coachProgressError}
                    />
                ) : null}
            </main>
            <CoachCommandBar
                disabled={!session || isBusy}
                hasActiveQuiz={activeQuiz !== null}
                pendingCommand={pendingCommand}
                onCommand={onCoachCommand}
            />
            {BUSINESS_SKILLS_COACH_WORKBENCH_RULES.showFreeFollowup ? (
                <Composer
                    value={input}
                    disabled={!session || isBusy}
                    hasActiveQuiz={activeQuiz !== null}
                    onChange={onInputChange}
                    onSubmit={onSend}
                />
            ) : null}
        </section>
    );
}

function WorkbenchHeader({
    session,
    isBusy,
    isStarting,
    onResume,
    onNewSession,
    onEnd,
}: {
    readonly session: AiCoachChatSessionPublicV1 | null;
    readonly isBusy: boolean;
    readonly isStarting: boolean;
    readonly onResume: () => void;
    readonly onNewSession: () => void;
    readonly onEnd: () => void;
}) {
    return (
        <header className="shrink-0 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-950 text-white">
                        <Bot className="h-5 w-5" />
                    </div>
                    <div>
                        <h1 className="text-lg font-semibold text-slate-950">
                            {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.pageTitle}
                        </h1>
                        <p className="text-xs text-slate-500">
                            {session
                                ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.activeSessionSubtitle
                                : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.startingSessionSubtitle}
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
                        {isStarting
                            ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.busyButton
                            : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.resumeButton}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        className="rounded-xl"
                        disabled={isBusy}
                        onClick={onNewSession}
                    >
                        <RotateCcw className="mr-2 h-4 w-4" />
                        {isStarting
                            ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.newSessionBusyButton
                            : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.newSessionButton}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        className="rounded-xl border-amber-200 text-amber-700 hover:bg-amber-50"
                        disabled={!session || isBusy}
                        onClick={onEnd}
                    >
                        <ClipboardList className="mr-2 h-4 w-4" />
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.endButton}
                    </Button>
                </div>
            </div>
        </header>
    );
}

function TrainingContextPanel({
    session,
    currentUnit,
    referenceQuiz,
    coachProgress,
    coachProgressError,
    learningUnitsError,
}: {
    readonly session: AiCoachChatSessionPublicV1 | null;
    readonly currentUnit: BusinessEtiquetteLearningUnit | null;
    readonly referenceQuiz: QuizCardEvent | null;
    readonly coachProgress: BusinessEtiquetteAiCoachProgress | null;
    readonly coachProgressError: string | null;
    readonly learningUnitsError: string | null;
}) {
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
    const capabilityLabels = capabilityLabelsFor(currentUnit, referenceQuiz);
    const masteryLabel = coachProgress
        ? BUSINESS_SKILLS_COACH_PROGRESS_LABELS[coachProgress.status]
        : masteryLabelFor(referenceQuiz);
    const unitWarning = learningUnitsError
        ?? (currentUnit ? null : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.learningUnitsUnavailable);
    const chapters = referenceQuiz?.payload.interaction.source_chapter_orders
        ?? currentUnit?.source_chapter_orders
        ?? [];
    const contextMeta = [
        capabilityLabels.length
            ? capabilityLabels.join("、")
            : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.fallbackUnitDescription,
        chapters.length ? `关联第 ${chapters.join("、")} 章` : null,
        `${difficultyLabel} · ${nextActionLabel}`,
        state?.current_focus ?? null,
        coachProgressError
            ? coachProgressError
            : progressDetail(coachProgress) ?? `已完成 ${state?.answered_card_count ?? 0} 张卡`,
    ].filter((item): item is string => typeof item === "string" && item.length > 0);
    return (
        <section className="rounded-xl border border-slate-200 bg-white/90 px-4 py-2.5 shadow-sm">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-500">
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.currentUnitLabel}
                    </p>
                    <h2 className="mt-0.5 truncate text-base font-semibold tracking-tight text-slate-950">
                        {currentUnit?.title ?? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.fallbackUnitTitle}
                    </h2>
                    <p className="mt-0.5 line-clamp-1 text-xs leading-5 text-slate-500">
                        {contextMeta.join(" / ")}
                    </p>
                </div>
                <div className="grid gap-2 sm:grid-cols-2 lg:w-[21rem]">
                    <ContextChip
                        label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.activityLabel}
                        value={phaseLabel}
                    />
                    <ContextChip
                        label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachProgressLabel}
                        value={masteryLabel}
                    />
                </div>
            </div>
            {unitWarning ? (
                <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-700">
                    {unitWarning}
                </p>
            ) : null}
        </section>
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
        <section className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-800">
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
    reasoningText,
    cardDelta,
}: {
    readonly activityLabel: string | null;
    readonly currentUnit: BusinessEtiquetteLearningUnit | null;
    readonly reasoningText: string;
    readonly cardDelta: Extract<AiCoachChatStreamEvent, { type: "ui_event_delta" }> | null;
}) {
    return (
        <div
            aria-live="polite"
            className="space-y-2 rounded-xl border border-slate-200 bg-white p-3 shadow-sm"
        >
            <StreamingStatusLine activityLabel={activityLabel} />
            {reasoningText.trim() ? (
                <details
                    open
                    className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-slate-600"
                >
                    <summary className="cursor-pointer select-none text-xs font-semibold text-slate-700">
                        思考过程
                    </summary>
                    <p className="mt-2 max-h-36 overflow-y-auto whitespace-pre-wrap break-words text-xs leading-5">
                        {reasoningText.trim()}
                    </p>
                </details>
            ) : null}
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
        <p className="text-xs font-medium leading-5 text-slate-500">
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
    const interaction = delta?.payload.interaction ?? null;
    const options = interaction?.options ?? [];
    const interactionType = interaction?.interaction_type ?? null;
    const trainingCardType = interaction?.training_card_type ?? null;
    const chapters = interaction?.source_chapter_orders ?? currentUnit?.source_chapter_orders ?? [];
    const capabilityKeys = interaction?.capability_keys ?? currentUnit?.capability_keys ?? [];
    return (
        <section
            aria-live="polite"
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6"
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
                {interaction?.stem?.trim()
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

function CoachGuidancePanel({
    latestScoredQuiz,
    summaryEvent,
    coachProgress,
    coachProgressError,
}: {
    readonly latestScoredQuiz: QuizCardEvent | null;
    readonly summaryEvent: SummaryCardEvent | null;
    readonly coachProgress: BusinessEtiquetteAiCoachProgress | null;
    readonly coachProgressError: string | null;
}) {
    return (
        <aside className="rounded-2xl border border-slate-200 bg-white/90 p-4 shadow-sm xl:sticky xl:top-4">
            <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white">
                    <Lightbulb className="h-4 w-4" />
                </div>
                <div>
                    <h2 className="text-sm font-semibold text-slate-950">
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.coachGuidanceTitle}
                    </h2>
                    <p className="mt-1 text-xs leading-relaxed text-slate-500">
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.coachGuidanceDescription}
                    </p>
                </div>
            </div>
            <div className="mt-4 space-y-4">
                <GuidanceBlock
                    icon={<MessageSquareText className="h-4 w-4" />}
                    title={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.feedbackTitle}
                >
                    <FeedbackPanel latestScoredQuiz={latestScoredQuiz} />
                </GuidanceBlock>
                <GuidanceBlock
                    icon={<ListChecks className="h-4 w-4" />}
                    title={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachProgressLabel}
                >
                    <ProgressPanel
                        coachProgress={coachProgress}
                        coachProgressError={coachProgressError}
                    />
                </GuidanceBlock>
                <GuidanceBlock
                    icon={<BookOpenCheck className="h-4 w-4" />}
                    title={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.endPanelTitle}
                >
                    <EndPanel
                        summaryEvent={summaryEvent}
                        latestScoredQuiz={latestScoredQuiz}
                        coachProgress={coachProgress}
                    />
                </GuidanceBlock>
            </div>
        </aside>
    );
}

function GuidanceBlock({
    icon,
    title,
    children,
}: {
    readonly icon: ReactNode;
    readonly title: string;
    readonly children: ReactNode;
}) {
    return (
        <section className="rounded-xl bg-slate-50 px-3 py-3">
            <div className="flex items-center gap-2 text-slate-700">
                <span className="text-slate-500">{icon}</span>
                <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
            </div>
            <div className="mt-3">
                {children}
            </div>
        </section>
    );
}

function FeedbackPanel({
    latestScoredQuiz,
}: {
    readonly latestScoredQuiz: QuizCardEvent | null;
}) {
    const scoreResult = latestScoredQuiz?.score_result ?? null;
    return (
        <div>
            {scoreResult ? (
                <div className="space-y-3">
                    <ScoreSummary scoreResult={scoreResult} />
                    <p className="text-sm leading-relaxed text-slate-700">
                        {scoreResult.feedback}
                    </p>
                    <StructuredFeedback result={scoreResult.structured_feedback} />
                    {scoreResult.missed_points.length > 0 ? (
                        <FeedbackList
                            label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.missedPointsLabel}
                            items={scoreResult.missed_points}
                        />
                    ) : null}
                </div>
            ) : (
                <div className="rounded-xl bg-white px-3 py-3">
                    <p className="font-semibold text-slate-900">
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.feedbackEmptyTitle}
                    </p>
                    <p className="mt-1 text-sm leading-relaxed text-slate-500">
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.feedbackEmptyDescription}
                    </p>
                </div>
            )}
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
    return (
        <div>
            {coachProgress ? (
                <div className="space-y-3">
                    <div className="flex flex-wrap gap-2 text-xs">
                        <span className={`rounded-full px-3 py-1 font-semibold ${
                            coachProgress.passed
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-amber-100 text-amber-700"
                        }`}>
                            {BUSINESS_SKILLS_COACH_PROGRESS_LABELS[coachProgress.status]}
                        </span>
                        <span className="rounded-full bg-white px-3 py-1 font-semibold text-slate-600">
                            {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachProgressCards}
                            ：{coachProgress.scored_card_count}
                        </span>
                        <span className="rounded-full bg-white px-3 py-1 font-semibold text-slate-600">
                            {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachProgressRemediation}
                            ：{coachProgress.remediation_attempt_count}
                            /{coachProgress.max_remediation_attempts}
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
            ) : (
                <div className="rounded-xl bg-white px-3 py-3">
                    <p className="font-semibold text-slate-900">
                        {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.aiCoachProgressUnavailable}
                    </p>
                    {coachProgressError ? (
                        <p className="mt-1 text-sm leading-relaxed text-amber-700">
                            {coachProgressError}
                        </p>
                    ) : null}
                </div>
            )}
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
                <div key={score.capability_key} className="rounded-lg bg-white px-3 py-2">
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

function EndPanel({
    summaryEvent,
    latestScoredQuiz,
    coachProgress,
}: {
    readonly summaryEvent: SummaryCardEvent | null;
    readonly latestScoredQuiz: QuizCardEvent | null;
    readonly coachProgress: BusinessEtiquetteAiCoachProgress | null;
}) {
    const summary = summaryEvent?.payload ?? null;
    const mastered = coachProgress?.passed
        ?? summary?.mastered
        ?? latestScoredQuiz?.score_result?.mastered
        ?? null;
    const feedbackNextStep = latestScoredQuiz?.score_result?.structured_feedback?.next_step;
    const whyItems = summary?.weaknesses?.length
        ? summary.weaknesses
        : latestScoredQuiz?.score_result?.missed_points ?? [];
    const nextItems = summary?.next_steps?.length
        ? summary.next_steps
        : coachProgress?.next_step
            ? [coachProgress.next_step]
            : feedbackNextStep
            ? [feedbackNextStep]
            : [];
    return (
        <div>
            <div className="space-y-3">
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    mastered ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                }`}>
                    {mastered
                        ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.endPanelMastered
                        : BUSINESS_SKILLS_COACH_WORKBENCH_COPY.endPanelNotMastered}
                </span>
                {typeof summary?.score_percent === "number" ? (
                    <p className="mt-3 text-sm font-semibold text-slate-900">
                        {Math.round(summary.score_percent)}%
                    </p>
                ) : null}
                {summary?.items.length ? (
                    <ul className="mt-3 space-y-2 text-sm text-slate-700">
                        {summary.items.map((item) => (
                            <li key={item} className="rounded-lg bg-white px-3 py-2">
                                {item}
                            </li>
                        ))}
                    </ul>
                ) : null}
                {whyItems.length > 0 ? (
                    <FeedbackList
                        label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.endPanelWhy}
                        items={whyItems}
                    />
                ) : null}
                {nextItems.length > 0 ? (
                    <FeedbackList
                        label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.endPanelNext}
                        items={nextItems}
                    />
                ) : null}
            </div>
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

function StructuredFeedback({
    result,
}: {
    readonly result: AiCoachScoreResultV1["structured_feedback"];
}) {
    if (!result) {
        return null;
    }
    return (
        <div className="space-y-2">
            {result.did_well.length > 0 ? (
                <FeedbackBlock
                    label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.didWellLabel}
                    body={result.did_well.join("；")}
                />
            ) : null}
            <FeedbackBlock
                label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.mainIssueLabel}
                body={result.main_issue}
            />
            <FeedbackBlock
                label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.whyInappropriateLabel}
                body={result.why_inappropriate}
            />
            <FeedbackBlock
                label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.suggestedResponseLabel}
                body={result.suggested_response}
            />
            <FeedbackBlock
                label={BUSINESS_SKILLS_COACH_WORKBENCH_COPY.nextStepLabel}
                body={result.next_step}
            />
        </div>
    );
}

function FeedbackBlock({
    label,
    body,
}: {
    readonly label: string;
    readonly body: string;
}) {
    if (!body) {
        return null;
    }
    return (
        <div className="rounded-lg bg-white px-3 py-2 text-sm">
            <p className="text-[11px] font-semibold text-slate-400">{label}</p>
            <p className="mt-1 leading-relaxed text-slate-700">{body}</p>
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
                    <li key={item} className="rounded-lg bg-white px-3 py-2">
                        {item}
                    </li>
                ))}
            </ul>
        </div>
    );
}

function ContextChip({
    label,
    value,
}: {
    readonly label: string;
    readonly value: string;
}) {
    return (
        <div className="min-w-0 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
            <p className="text-[11px] font-semibold text-slate-400">{label}</p>
            <p className="mt-1 truncate text-sm font-semibold leading-relaxed text-slate-900">
                {value}
            </p>
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
        readonly disabled?: boolean;
    }[] = [
        {
            command: "continue",
            disabled: hasActiveQuiz && !BUSINESS_SKILLS_COACH_WORKBENCH_RULES.allowSkipActiveCard,
        },
        { command: "explain" },
        { command: "switch_scenario" },
        { command: "summarize" },
    ];
    return (
        <div className="shrink-0 border-t border-slate-200 bg-white/90 px-4 py-2 md:px-5">
            <div className="flex items-center gap-2 overflow-x-auto">
                <span className="mr-1 inline-flex shrink-0 items-center text-xs font-semibold text-slate-500">
                    <CheckCircle2 className="mr-1 h-4 w-4 text-emerald-600" />
                    {BUSINESS_SKILLS_COACH_WORKBENCH_COPY.commandBarLabel}
                </span>
                {commands.map((item) => (
                    <Button
                        key={item.command}
                        type="button"
                        variant={item.command === "continue" ? "primary" : "outline"}
                        size="sm"
                        className="shrink-0 rounded-xl"
                        disabled={disabled || item.disabled === true}
                        onClick={() => onCommand(item.command)}
                    >
                        {pendingCommand === item.command
                            ? BUSINESS_SKILLS_COACH_WORKBENCH_COPY.busyButton
                            : BUSINESS_SKILLS_COACH_COMMAND_LABELS[item.command]}
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
            className="shrink-0 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:px-5"
        >
            <div className="flex items-end gap-3 rounded-xl border border-slate-200 bg-white p-1.5 shadow-sm">
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
                    disabled={disabled || !value.trim()}
                    className="h-10 rounded-xl bg-slate-950 px-4 hover:bg-slate-800"
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

function progressDetail(
    progress: BusinessEtiquetteAiCoachProgress | null,
): string | null {
    if (!progress) {
        return null;
    }
    const blockLabel = progress.block_next ? "阻断后续" : "不阻断后续";
    return `${progress.scored_card_count} 张卡 · ${progress.remediation_attempt_count}/${progress.max_remediation_attempts} 次补救 · ${blockLabel}`;
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
    streamingReasoningText,
    streamingCardDelta,
    activeQuiz,
}: {
    readonly isStarting: boolean;
    readonly isSending: boolean;
    readonly isAdvancing: boolean;
    readonly streamPhase: AiCoachChatStreamPhase | null;
    readonly streamingReasoningText: Extract<AiCoachChatStreamEvent, { type: "reasoning_text_delta" }> | null;
    readonly streamingCardDelta: Extract<AiCoachChatStreamEvent, { type: "ui_event_delta" }> | null;
    readonly activeQuiz: QuizCardEvent | null;
}): boolean {
    if (
        streamingReasoningText?.text.trim()
        || streamingCardDelta !== null
    ) {
        return true;
    }
    if (!isStarting && !isSending && !isAdvancing) {
        return false;
    }
    return isStreamingTrainingCardPhase(streamPhase) && activeQuiz === null;
}
