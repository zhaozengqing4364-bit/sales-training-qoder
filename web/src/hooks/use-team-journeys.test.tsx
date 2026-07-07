import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createAppQueryClient } from "@/lib/query/client";

import { useTeamJourneys } from "./use-team-journeys";

const {
    listAdminJourneysMock,
    getJourneyAnalyticsMock,
} = vi.hoisted(() => ({
    listAdminJourneysMock: vi.fn(),
    getJourneyAnalyticsMock: vi.fn(),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    listAdminJourneys: listAdminJourneysMock,
                    getJourneyAnalytics: getJourneyAnalyticsMock,
                },
            },
        },
    };
});

function createWrapper(queryClient: QueryClient) {
    return function Wrapper({ children }: { children: React.ReactNode }) {
        return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    };
}

function buildAnalyticsPayload(overrides?: {
    learner_count?: number;
    passed_learner_count?: number;
    risk_learner_count?: number;
    in_progress_count?: number;
}) {
    return {
        generated_at: "2026-07-07T00:00:00Z",
        summary: {
            learner_count: overrides?.learner_count ?? 3,
            loaded_learner_count: overrides?.learner_count ?? 3,
            passed_learner_count: overrides?.passed_learner_count ?? 1,
            risk_learner_count: overrides?.risk_learner_count ?? 1,
            pass_rate: 0.33,
        },
        funnel: [
            {
                stage: "not_started" as const,
                learner_count: 1,
                rate: 0.33,
            },
            {
                stage: "in_progress" as const,
                learner_count: overrides?.in_progress_count ?? 1,
                rate: 0.33,
            },
            {
                stage: "passed" as const,
                learner_count: overrides?.passed_learner_count ?? 1,
                rate: 0.33,
            },
        ],
        module_summaries: [],
        weakness_heatmap: [],
        trend_data: [],
        learner_level_summaries: [],
        role_level_summaries: [],
        risk_learners: [
            {
                learner_id: "learner-2",
                learner_name: "卡关学员",
                department: "销售部",
                training_stage: "needs_remediation" as const,
                risk_reasons: ["business_skills:not_passed", "elevator_pitch:status:failed"],
                risk_module_count: 2,
                risk_module_keys: ["business_skills", "elevator_pitch"],
            },
        ],
        filters: {
            limit: 500,
        },
    };
}

function buildJourneysPayload() {
    return {
        items: [
            {
                journey_id: "journey-1",
                learner_id: "learner-1",
                learner_name: "张三",
                department: "销售部",
                path_key: "newcomer_training_path_v1" as const,
                path_revision_id: "rev-1",
                path_revision_no: 1,
                source: "active_revision" as const,
                legacy_snapshot_only: false as const,
                role_capabilities: [],
                learner_level: {
                    level_key: "level-1",
                    label: "初级",
                    source: "user_profile" as const,
                    rank: 1,
                },
                role_level: {
                    level_key: "role-1",
                    label: "销售",
                    source: "user_profile" as const,
                    rank: 1,
                },
                training_stage: "in_progress" as const,
                modules: [],
                overall_progress: {
                    total_modules: 5,
                    completed_modules: 2,
                    passed_modules: 1,
                    failed_modules: 1,
                    needs_remediation_modules: 0,
                },
                retraining_requests: [],
                diagnostics: [],
                generated_at: "2026-07-07T00:00:00Z",
            },
        ],
        total: 1,
        limit: 50,
        offset: 0,
    };
}

describe("useTeamJourneys", () => {
    beforeEach(() => {
        listAdminJourneysMock.mockReset();
        getJourneyAnalyticsMock.mockReset();
    });

    it("loads both journeys and analytics and exposes loading state", async () => {
        listAdminJourneysMock.mockResolvedValue(buildJourneysPayload());
        getJourneyAnalyticsMock.mockResolvedValue(buildAnalyticsPayload());

        const queryClient = createAppQueryClient();
        const { result } = renderHook(() => useTeamJourneys({ limit: 50, offset: 0 }), {
            wrapper: createWrapper(queryClient),
        });

        expect(result.current.isLoading).toBe(true);

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        });

        expect(result.current.isError).toBe(false);
        expect(result.current.journeys.data?.items).toHaveLength(1);
        expect(result.current.analytics.data?.summary.learner_count).toBe(3);
        expect(listAdminJourneysMock).toHaveBeenCalledWith({ limit: 50, offset: 0 });
        expect(getJourneyAnalyticsMock).toHaveBeenCalled();
    });

    it("exposes error state when journeys query fails", async () => {
        listAdminJourneysMock.mockRejectedValue(new Error("journeys unavailable"));
        getJourneyAnalyticsMock.mockResolvedValue(buildAnalyticsPayload());

        const queryClient = createAppQueryClient();
        const { result } = renderHook(() => useTeamJourneys(), {
            wrapper: createWrapper(queryClient),
        });

        await waitFor(() => {
            expect(result.current.isError).toBe(true);
        });

        expect(result.current.error).toBeInstanceOf(Error);
        expect(result.current.error?.message).toBe("journeys unavailable");
    });

    it("exposes error state when analytics query fails", async () => {
        listAdminJourneysMock.mockResolvedValue(buildJourneysPayload());
        getJourneyAnalyticsMock.mockRejectedValue(new Error("analytics unavailable"));

        const queryClient = createAppQueryClient();
        const { result } = renderHook(() => useTeamJourneys(), {
            wrapper: createWrapper(queryClient),
        });

        await waitFor(() => {
            expect(result.current.isError).toBe(true);
        });

        expect(result.current.error).toBeInstanceOf(Error);
        expect(result.current.error?.message).toBe("analytics unavailable");
    });

    it("refetches both queries when refetch is called", async () => {
        listAdminJourneysMock.mockResolvedValue(buildJourneysPayload());
        getJourneyAnalyticsMock.mockResolvedValue(buildAnalyticsPayload());

        const queryClient = createAppQueryClient();
        const { result } = renderHook(() => useTeamJourneys(), {
            wrapper: createWrapper(queryClient),
        });

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        });

        listAdminJourneysMock.mockClear();
        getJourneyAnalyticsMock.mockClear();

        await result.current.refetch();

        await waitFor(() => {
            expect(listAdminJourneysMock).toHaveBeenCalled();
            expect(getJourneyAnalyticsMock).toHaveBeenCalled();
        });
    });
});
