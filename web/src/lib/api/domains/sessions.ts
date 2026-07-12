/** Session report, replay, history, highlight, and media transport. */

import type {
    HighlightReviewItemPayload,
    HighlightReviewResponse,
    HighlightReviewShareCreateResponse,
    HighlightReviewShareSummary,
    HighlightsResponse,
    KnowledgeCheckDiagnostics,
    PracticeSessionReport,
    Recommendation,
    ReplayData,
    ReplayMessagesResponse,
    ReportTrendsResponse,
    SessionItem,
    SessionStats,
} from "../types";
import type { ApiRequest } from "./shared";

type SessionsDomainDependencies = {
    request: ApiRequest;
    resolveApiBaseUrl: () => string;
    createHeaders: (existingHeaders?: HeadersInit, includeContentType?: boolean) => Headers;
    fetchWithLoopbackRetry: (url: string, options: RequestInit) => Promise<Response>;
    createApiError: (status: number, payload: unknown) => Error;
    createNetworkError: (error: unknown) => Error;
};

export function createSessionsDomain({
    request,
    resolveApiBaseUrl,
    createHeaders,
    fetchWithLoopbackRetry,
    createApiError,
    createNetworkError,
}: SessionsDomainDependencies) {
    return {
        list: async (params?: { limit?: number; page?: number; page_size?: number; sort?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.limit) searchParams.set("limit", String(params.limit));
            if (params?.page) searchParams.set("page", String(params.page));
            if (params?.page_size) searchParams.set("page_size", String(params.page_size));
            if (params?.sort) searchParams.set("sort", params.sort);
            return request<{ total: number; items: SessionItem[]; page: number; page_size: number; has_more: boolean }>(`/sessions?${searchParams}`);
        },

        getStats: async () => request<SessionStats>("/sessions/stats"),
        getReport: async (sessionId: string) => request<PracticeSessionReport>(`/practice/sessions/${sessionId}/report`),
        getReportTrends: async (sessionId: string, limit = 5) => request<ReportTrendsResponse>(`/practice/sessions/${sessionId}/report-trends?limit=${limit}`),
        getNextRecommendation: async (sessionId: string) => request<Recommendation>(`/practice/sessions/${sessionId}/next-recommendation`),
        getKnowledgeCheck: async (sessionId: string) => request<KnowledgeCheckDiagnostics>(`/practice/sessions/${sessionId}/knowledge-check`),
        getEnhancedReport: async (sessionId: string) => request<Record<string, unknown>>(`/sessions/${sessionId}/enhanced-report`),
        getReplay: async (sessionId: string) => request<ReplayData>(`/sessions/${sessionId}/replay`),
        getMessages: async (sessionId: string, page = 1, pageSize = 50) => {
            return request<ReplayMessagesResponse>(`/sessions/${sessionId}/messages?page=${page}&page_size=${pageSize}`);
        },
        getMessageDetail: async (sessionId: string, messageId: string) => {
            return request<Record<string, unknown>>(`/sessions/${sessionId}/messages/${messageId}`);
        },
        getHighlights: async (sessionId: string) => request<HighlightsResponse>(`/sessions/${sessionId}/highlights`),
        getHighlightReview: async (sessionId: string) => request<HighlightReviewResponse | null>(`/sessions/${sessionId}/highlight-review`),
        saveHighlightReview: async (
            sessionId: string,
            payload: { items: Array<Partial<HighlightReviewItemPayload> & { id?: string }>; title?: string | null },
        ) => request<HighlightReviewResponse>(`/sessions/${sessionId}/highlight-review`, {
            method: "PUT",
            body: JSON.stringify({
                schema_version: "highlight_review_v1",
                title: payload.title ?? null,
                items: payload.items.map((item) => ({
                    id: item.id ?? item.message_id,
                    message_id: item.message_id ?? item.id,
                    reason: item.reason ?? null,
                    stage_name: item.stage_name ?? null,
                    issue_label: item.issue_label ?? null,
                    suggested_response: item.suggested_response ?? null,
                })),
            }),
        }),
        createHighlightReviewShare: async (
            sessionId: string,
            payload: { consent_granted: boolean; consent_text?: string | null; ttl_days?: number | null; channel?: "wecom" },
        ) => request<HighlightReviewShareCreateResponse>(`/sessions/${sessionId}/highlight-review/shares`, {
            method: "POST",
            body: JSON.stringify({
                channel: payload.channel ?? "wecom",
                consent_granted: payload.consent_granted,
                consent_text: payload.consent_text ?? null,
                ttl_days: payload.ttl_days ?? null,
            }),
        }),
        revokeHighlightReviewShare: async (
            sessionId: string,
            shareId: string,
            reason?: string | null,
        ) => request<HighlightReviewShareSummary>(`/sessions/${sessionId}/highlight-review/shares/${shareId}/revoke`, {
            method: "POST",
            body: JSON.stringify({ reason: reason ?? null }),
        }),

        getAudioBlobUrl: async (sessionId: string, messageId: string) => {
            const response = await fetch(`${resolveApiBaseUrl()}/sessions/${sessionId}/audio/${messageId}`, {
                credentials: "include",
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const blob = await response.blob();
            return URL.createObjectURL(blob);
        },

        getSegmentAudioBlobUrl: async (sessionId: string, segmentSequence: number) => {
            try {
                const response = await fetchWithLoopbackRetry(
                    `${resolveApiBaseUrl()}/sessions/${sessionId}/audio-segments/${segmentSequence}`,
                    {
                        credentials: "include",
                        headers: createHeaders(undefined, false),
                    },
                );

                if (!response.ok) {
                    const payload = await response.json().catch(() => ({}));
                    throw createApiError(response.status, payload);
                }

                const blob = await response.blob();
                return URL.createObjectURL(blob);
            } catch (error) {
                if (error instanceof Error && error.name === "AbortError") {
                    throw error;
                }
                if (error instanceof Error && error.name === "ApiRequestError") {
                    throw error;
                }
                throw createNetworkError(error);
            }
        },
    };
}
