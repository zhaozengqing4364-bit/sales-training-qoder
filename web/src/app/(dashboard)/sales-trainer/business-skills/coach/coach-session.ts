import type {
    AiCoachAnswerPayloadV1,
    AiCoachChatMessagePublicV1,
    AiCoachChatSessionPublicV1,
    AiCoachChatStreamEvent,
    AiCoachInteractionPublicV1,
    AiCoachUiEventPublicV1,
    BusinessEtiquetteAiCoachProgress,
    BusinessEtiquetteLearningUnit,
} from "@/lib/api/types";

export const MODULE_KEY = "business_skills";
export type CoachCommand = "continue" | "explain" | "switch_scenario" | "summarize" | "end" | "retry";

export type DraftByEventId = Readonly<Record<string, AiCoachAnswerPayloadV1 | null>>;

export type QuizCardEvent = Extract<AiCoachUiEventPublicV1, { type: "quiz_card" }>;
export type SummaryCardEvent = Extract<AiCoachUiEventPublicV1, { type: "summary_card" }>;
export type StreamingAssistantText = Extract<
    AiCoachChatStreamEvent,
    { type: "assistant_text_delta" }
>;

export type CoachTimelineMessage = {
    readonly message_id: string;
    readonly role: "assistant" | "user";
    readonly content: string;
    readonly order_index: number;
    readonly created_at: string;
    readonly events: readonly AiCoachUiEventPublicV1[];
    readonly state: "persisted" | "pending" | "streaming";
};

export interface CoachConversationViewModel {
    readonly timeline: readonly CoachTimelineMessage[];
    readonly activeEventId: string | null;
    readonly activeQuiz: QuizCardEvent | null;
    readonly latestScoredQuiz: QuizCardEvent | null;
    readonly latestSummary: SummaryCardEvent | null;
    readonly referenceQuiz: QuizCardEvent | null;
    readonly currentUnit: BusinessEtiquetteLearningUnit | null;
    readonly latestAssistantMessageId: string | null;
    readonly sessionEventCount: number;
    readonly quizCardCount: number;
    readonly scoredQuizCardCount: number;
}

export function buildCoachConversationViewModel({
    session,
    learningUnits,
    coachProgress,
    pendingUserMessage,
    streamingAssistantText,
}: {
    readonly session: AiCoachChatSessionPublicV1 | null;
    readonly learningUnits: readonly BusinessEtiquetteLearningUnit[];
    readonly coachProgress: BusinessEtiquetteAiCoachProgress | null;
    readonly pendingUserMessage: string | null;
    readonly streamingAssistantText: StreamingAssistantText | null;
}): CoachConversationViewModel {
    const activeEventId = activeEventIdForSession(session);
    const activeQuiz = activeQuizEventForSession(session);
    const latestScoredQuiz = latestScoredQuizEventForSession(session);
    const latestSummary = latestSummaryEventForSession(session);
    const referenceQuiz = trainingReferenceEventForSession(session);
    const progressUnit = coachProgress
        ? learningUnits.find((unit) => unit.unit_key === coachProgress.learning_unit_key)
        : null;
    const currentUnit = progressUnit ?? resolveCurrentLearningUnit(learningUnits, referenceQuiz);
    const eventsByMessage = groupEventsByMessage(session?.ui_events ?? []);
    const timeline = [
        ...buildPersistedTimeline(session?.messages ?? [], eventsByMessage),
        ...buildPendingTimelineMessage(session, pendingUserMessage),
        ...buildStreamingTimelineMessage(session, streamingAssistantText),
    ];
    const latestAssistantMessageId =
        [...timeline].reverse().find((item) => item.role === "assistant")?.message_id ?? null;
    const quizCards = quizEventsForSession(session);

    return {
        timeline,
        activeEventId,
        activeQuiz,
        latestScoredQuiz,
        latestSummary,
        referenceQuiz,
        currentUnit,
        latestAssistantMessageId,
        sessionEventCount: session?.ui_events.length ?? 0,
        quizCardCount: quizCards.length,
        scoredQuizCardCount: quizCards.filter((event) => event.status === "scored").length,
    };
}

function buildPersistedTimeline(
    messages: readonly AiCoachChatMessagePublicV1[],
    eventsByMessage: ReadonlyMap<string, readonly AiCoachUiEventPublicV1[]>,
): readonly CoachTimelineMessage[] {
    return messages.map((message) => ({
        message_id: message.message_id,
        role: message.role,
        content: message.content,
        order_index: message.order_index,
        created_at: message.created_at,
        events: eventsByMessage.get(message.message_id) ?? [],
        state: "persisted",
    }));
}

function buildPendingTimelineMessage(
    session: AiCoachChatSessionPublicV1 | null,
    pendingUserMessage: string | null,
): readonly CoachTimelineMessage[] {
    if (!pendingUserMessage) {
        return [];
    }
    return [
        {
            message_id: "pending-user",
            role: "user",
            content: pendingUserMessage,
            order_index: (session?.messages.length ?? 0) + 1,
            created_at: new Date().toISOString(),
            events: [],
            state: "pending",
        },
    ];
}

function buildStreamingTimelineMessage(
    session: AiCoachChatSessionPublicV1 | null,
    streamingAssistantText: StreamingAssistantText | null,
): readonly CoachTimelineMessage[] {
    const content = streamingAssistantText?.text.trim() ?? "";
    if (!content) {
        return [];
    }
    return [
        {
            message_id: "streaming-assistant",
            role: "assistant",
            content,
            order_index: (session?.messages.length ?? 0) + 2,
            created_at: new Date().toISOString(),
            events: [],
            state: "streaming",
        },
    ];
}

function groupEventsByMessage(events: readonly AiCoachUiEventPublicV1[]) {
    const grouped = new Map<string, readonly AiCoachUiEventPublicV1[]>();
    for (const event of events) {
        grouped.set(event.message_id, [...(grouped.get(event.message_id) ?? []), event]);
    }
    return grouped;
}

export function activeEventIdForSession(
    session: AiCoachChatSessionPublicV1 | null,
): string | null {
    const state = session?.coach_state;
    if (state && Object.prototype.hasOwnProperty.call(state, "active_event_id")) {
        return state.active_event_id;
    }
    return firstPendingQuizEvent(session)?.event_id ?? null;
}

export function firstPendingQuizEvent(
    session: AiCoachChatSessionPublicV1 | null,
): QuizCardEvent | null {
    return (
        session?.ui_events.find(
            (event): event is Extract<AiCoachUiEventPublicV1, { type: "quiz_card" }> =>
                event.type === "quiz_card"
                && event.status === "pending"
                && event.answer_payload === null
                && event.score_result === null,
        ) ?? null
    );
}

export function activeQuizEventForSession(
    session: AiCoachChatSessionPublicV1 | null,
): QuizCardEvent | null {
    const activeEventId = activeEventIdForSession(session);
    if (!activeEventId) {
        return null;
    }
    return (
        session?.ui_events.find(
            (event): event is Extract<AiCoachUiEventPublicV1, { type: "quiz_card" }> =>
                event.type === "quiz_card"
                && event.event_id === activeEventId
                && event.status === "pending"
                && event.answer_payload === null
                && event.score_result === null,
        ) ?? null
    );
}

export function quizEventsForSession(
    session: AiCoachChatSessionPublicV1 | null,
): readonly QuizCardEvent[] {
    return (session?.ui_events ?? []).filter(
        (event): event is QuizCardEvent => event.type === "quiz_card",
    );
}

export function latestScoredQuizEventForSession(
    session: AiCoachChatSessionPublicV1 | null,
): QuizCardEvent | null {
    return (
        [...quizEventsForSession(session)]
            .reverse()
            .find((event) => event.status === "scored" && event.score_result !== null) ?? null
    );
}

export function latestSummaryEventForSession(
    session: AiCoachChatSessionPublicV1 | null,
): SummaryCardEvent | null {
    return (
        [...(session?.ui_events ?? [])]
            .reverse()
            .find((event): event is SummaryCardEvent => event.type === "summary_card") ?? null
    );
}

export function trainingReferenceEventForSession(
    session: AiCoachChatSessionPublicV1 | null,
): QuizCardEvent | null {
    return (
        activeQuizEventForSession(session)
        ?? latestScoredQuizEventForSession(session)
        ?? [...quizEventsForSession(session)].reverse()[0]
        ?? null
    );
}

export function resolveCurrentLearningUnit(
    units: readonly BusinessEtiquetteLearningUnit[],
    event: QuizCardEvent | null,
): BusinessEtiquetteLearningUnit | null {
    if (!event) {
        return units.find((unit) => unit.enabled) ?? units[0] ?? null;
    }
    const eventCapabilityKeys = new Set(event.payload.interaction.capability_keys ?? []);
    const eventChapterOrders = new Set(event.payload.interaction.source_chapter_orders ?? []);
    let bestUnit: BusinessEtiquetteLearningUnit | null = null;
    let bestScore = 0;
    for (const unit of units) {
        const chapterMatches = unit.source_chapter_orders.filter((order) =>
            eventChapterOrders.has(order),
        ).length;
        const capabilityMatches = unit.capability_keys.filter((key) =>
            eventCapabilityKeys.has(key),
        ).length;
        const score = chapterMatches * 3 + capabilityMatches * 2 + (unit.enabled ? 1 : 0);
        if (score > bestScore) {
            bestScore = score;
            bestUnit = unit;
        }
    }
    return bestUnit;
}

function readConstraint(
    interaction: AiCoachInteractionPublicV1,
    key: "min_selected" | "max_selected" | "min_length" | "max_length",
): number | null {
    const value = interaction.answer_constraints[key];
    return typeof value === "number" ? value : null;
}

export function isAnswerPayloadSubmittable(
    interaction: AiCoachInteractionPublicV1,
    payload: AiCoachAnswerPayloadV1 | null,
): boolean {
    switch (interaction.interaction_type) {
        case "single_choice":
            return payload?.variant === "choice" && payload.option_ids.length === 1;
        case "multiple_choice": {
            if (payload?.variant !== "choice") {
                return false;
            }
            const selectedCount = payload.option_ids.length;
            const minSelected = readConstraint(interaction, "min_selected") ?? 1;
            const maxSelected = readConstraint(interaction, "max_selected");
            return (
                selectedCount >= minSelected
                && (maxSelected === null || selectedCount <= maxSelected)
            );
        }
        case "short_answer": {
            if (payload?.variant !== "text") {
                return false;
            }
            const length = payload.text.trim().length;
            const minLength = readConstraint(interaction, "min_length") ?? 1;
            const maxLength = readConstraint(interaction, "max_length");
            return length >= minLength && (maxLength === null || length <= maxLength);
        }
        default: {
            const exhaustive: never = interaction.interaction_type;
            return exhaustive;
        }
    }
}

export function draftForChoice(
    current: AiCoachAnswerPayloadV1 | null,
    optionId: string,
    multiple: boolean,
): AiCoachAnswerPayloadV1 {
    if (!multiple) {
        return { variant: "choice", option_ids: [optionId] };
    }
    const previous = current?.variant === "choice" ? current.option_ids : [];
    const exists = previous.includes(optionId);
    return {
        variant: "choice",
        option_ids: exists
            ? previous.filter((value) => value !== optionId)
            : [...previous, optionId],
    };
}

export function draftForText(text: string): AiCoachAnswerPayloadV1 {
    return { variant: "text", text };
}

export function selectedOptionIds(payload: AiCoachAnswerPayloadV1 | null): readonly string[] {
    return payload?.variant === "choice" ? payload.option_ids : [];
}

export function textAnswer(payload: AiCoachAnswerPayloadV1 | null): string {
    return payload?.variant === "text" ? payload.text : "";
}

export function eventScoreState(event: AiCoachUiEventPublicV1): "correct" | "wrong" | "pending" {
    if (event.type !== "quiz_card" || !event.score_result) {
        return "pending";
    }
    if (typeof event.score_result.mastered === "boolean") {
        return event.score_result.mastered ? "correct" : "wrong";
    }
    return event.score_result.score >= event.score_result.max_score ? "correct" : "wrong";
}
