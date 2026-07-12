import type {
    PracticeSessionReport,
    PresentationReview,
    ReplayAnchor,
} from "@/lib/api/types/session-report";
import { debug } from "@/lib/debug";

export const HIGHLIGHT_REVIEW_LIMIT = 3;
const HIGHLIGHT_REVIEW_STORAGE_PREFIX = "qoder.highlightReviewList.v1";
const HIGHLIGHT_REVIEW_SCHEMA_VERSION = "highlight_review_v1";

export type HighlightReviewItem = {
    id: string;
    source_session_id: string;
    turn_number: number;
    content: string;
    reason: string | null;
    stage_name: string | null;
    issue_label: string | null;
    suggested_response: string | null;
};

type HighlightReviewStoragePayload = {
    schema_version: typeof HIGHLIGHT_REVIEW_SCHEMA_VERSION;
    updated_at: string;
    items: HighlightReviewItem[];
};

export type ReplayDeepLinkFocus = "main_issue" | "next_goal" | "learning_evidence";

export function buildSessionReportPath(sessionId: string): string {
    return `/practice/${encodeURIComponent(sessionId)}/report`;
}

export function buildPresentationPageReplayPath(
    sessionId: string,
    pageNumber: number,
): string {
    const params = new URLSearchParams({
        focus: "presentation_page",
        page: String(pageNumber),
        page_anchor_status: "resolved",
    });
    return `/practice/${encodeURIComponent(sessionId)}/replay?${params.toString()}`;
}

export function buildPresentationPagePracticePath({
    sessionId,
    presentationId,
    pageNumber,
    sourceSessionId,
}: {
    sessionId: string;
    presentationId: string;
    pageNumber: number;
    sourceSessionId: string;
}): string {
    const params = new URLSearchParams({
        scenario_type: "presentation",
        presentation_id: presentationId,
        focus: "presentation_page",
        page: String(pageNumber),
        source_session_id: sourceSessionId,
    });
    return `/practice/${encodeURIComponent(sessionId)}?${params.toString()}`;
}

export function buildPresentationPageFocusIntent({
    sourceSessionId,
    pageSummary,
}: {
    sourceSessionId: string;
    pageSummary: PresentationReview["page_summaries"][number];
}) {
    return {
        version: "presentation_page_retry_v1",
        source_session_id: sourceSessionId,
        presentation_page: {
            page_number: pageSummary.page_number,
            reason: pageSummary.missing_required_points.length > 0
                ? "missing_required_points"
                : "page_review",
            summary: pageSummary.summary,
            missing_required_points: pageSummary.missing_required_points,
        },
    };
}

export function buildReplayDeepLink(
    sessionId: string,
    options: {
        focus: ReplayDeepLinkFocus;
        anchor?: ReplayAnchor | null;
        turnNumber?: number | null;
    },
): string {
    const params = new URLSearchParams({ focus: options.focus });
    const anchor = options.anchor;
    if (anchor) {
        if (typeof anchor.message_id === "string" && anchor.message_id.trim()) {
            params.set("message_id", anchor.message_id);
        }
        if (typeof anchor.turn_number === "number") {
            params.set("turn", String(anchor.turn_number));
        }
        params.set("anchor_status", anchor.status);
        if (anchor.degraded_reason) {
            params.set("anchor_reason", anchor.degraded_reason);
        }
        if (anchor.marker?.type) {
            params.set("marker_type", anchor.marker.type);
        }
        if (typeof anchor.marker?.timestamp_ms === "number") {
            params.set("marker_timestamp_ms", String(anchor.marker.timestamp_ms));
        }
    } else if (typeof options.turnNumber === "number") {
        params.set("turn", String(options.turnNumber));
    }
    return `/practice/${encodeURIComponent(sessionId)}/replay?${params.toString()}`;
}

export function getRetryFallbackPath(
    retry?: PracticeSessionReport["retry_entry"] | null,
): string {
    return retry?.scenario_type === "presentation"
        ? "/training/presentation"
        : "/training/sales";
}

export function buildRetrySessionPath(
    sessionId: string,
    retry: NonNullable<PracticeSessionReport["retry_entry"]>,
    extra?: Record<string, string>,
): string {
    const params = new URLSearchParams({ scenario_type: retry.scenario_type });
    for (const [key, value] of Object.entries(extra ?? {})) {
        params.set(key, value);
    }
    if (retry.agent_id) params.set("agent_id", retry.agent_id);
    if (retry.persona_id) params.set("persona_id", retry.persona_id);
    if (retry.presentation_id) params.set("presentation_id", retry.presentation_id);
    return `/practice/${encodeURIComponent(sessionId)}?${params.toString()}`;
}

function getHighlightReviewStorageKey(sessionId: string): string {
    return `${HIGHLIGHT_REVIEW_STORAGE_PREFIX}:${sessionId}`;
}

export function isHighlightReviewItem(item: unknown): item is HighlightReviewItem {
    const record = item && typeof item === "object"
        ? item as Record<string, unknown>
        : null;
    return Boolean(
        record
        && typeof record.id === "string"
        && typeof record.content === "string"
        && typeof record.turn_number === "number"
        && typeof record.source_session_id === "string",
    );
}

export function readHighlightReviewItems(sessionId: string): HighlightReviewItem[] {
    if (typeof window === "undefined") return [];
    const storageKey = getHighlightReviewStorageKey(sessionId);
    try {
        const raw = window.localStorage.getItem(storageKey);
        if (!raw) return [];
        const parsed: unknown = JSON.parse(raw);
        const payload = parsed && typeof parsed === "object"
            ? parsed as Partial<HighlightReviewStoragePayload>
            : null;
        if (
            !payload
            || payload.schema_version !== HIGHLIGHT_REVIEW_SCHEMA_VERSION
            || !Array.isArray(payload.items)
        ) {
            window.localStorage.removeItem(storageKey);
            return [];
        }
        return payload.items.filter(isHighlightReviewItem).slice(0, HIGHLIGHT_REVIEW_LIMIT);
    } catch (error) {
        debug.warn("[Report] Failed to read highlight review list", { sessionId, error });
        window.localStorage.removeItem(storageKey);
        return [];
    }
}

export function persistHighlightReviewItems(
    sessionId: string,
    items: HighlightReviewItem[],
): void {
    if (typeof window === "undefined") return;
    try {
        window.localStorage.setItem(
            getHighlightReviewStorageKey(sessionId),
            JSON.stringify({
                schema_version: HIGHLIGHT_REVIEW_SCHEMA_VERSION,
                updated_at: new Date().toISOString(),
                items: items.slice(0, HIGHLIGHT_REVIEW_LIMIT),
            } satisfies HighlightReviewStoragePayload),
        );
    } catch (error) {
        debug.warn("[Report] Failed to persist highlight review list", { sessionId, error });
    }
}
