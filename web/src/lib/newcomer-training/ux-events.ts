import { trackCustomMetric } from "@/lib/performance";

export type FoundationUxEvent =
    | "journey_entered"
    | "activity_entered"
    | "activity_started"
    | "activity_completed"
    | "progress_saved"
    | "draft_restored"
    | "upload_interrupted"
    | "task_waiting"
    | "remediation_started"
    | "review_requested"
    | "review_completed";

export type FoundationUxDimension =
    | "lesson"
    | "quiz"
    | "audio_assessment"
    | "ai_coach"
    | "assignment"
    | "background_task"
    | "review";

/**
 * Emits a privacy-safe, non-blocking UX counter.
 *
 * The fixed event/dimension vocabulary intentionally prevents answers, recording
 * text, prompts, learner identifiers, or arbitrary error payloads from entering
 * frontend analytics.
 */
export function trackFoundationUxEvent(
    event: FoundationUxEvent,
    dimension?: FoundationUxDimension,
): void {
    if (typeof window === "undefined") return;
    const suffix = dimension ? `.${dimension}` : "";
    trackCustomMetric(`newcomer_foundation.${event}${suffix}`, 1);
}
