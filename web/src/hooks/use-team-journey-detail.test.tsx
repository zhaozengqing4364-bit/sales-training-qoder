import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createAppQueryClient } from "@/lib/query/client";

import { useTeamJourneyDetail } from "./use-team-journey-detail";

const {
    getAdminJourneyMock,
} = vi.hoisted(() => ({
    getAdminJourneyMock: vi.fn(),
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
                    getAdminJourney: getAdminJourneyMock,
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

function buildJourneyPayload(overrides?: { learner_id?: string; learner_name?: string }) {
    return {
        journey_id: "journey-1",
        learner_id: overrides?.learner_id ?? "learner-1",
        learner_name: overrides?.learner_name ?? "张三",
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
        modules: [
            {
                module_key: "business_skills",
                title: "商务技巧",
                display_name: "商务技巧",
                module_type: "article_exam",
                kind: "quiz_attempt" as const,
                order_index: 1,
                enabled: true,
                status: "passed" as const,
                stage: "passed" as const,
                passed: true,
                score: 90,
                max_score: 100,
                completion_rule: "passed",
                unmet_reasons: [],
                outcome_history: [],
            },
        ],
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
    };
}

describe("useTeamJourneyDetail", () => {
    beforeEach(() => {
        getAdminJourneyMock.mockReset();
    });

    it("loads journey detail and exposes loading state", async () => {
        getAdminJourneyMock.mockResolvedValue(buildJourneyPayload());

        const queryClient = createAppQueryClient();
        const { result } = renderHook(() => useTeamJourneyDetail({ learnerId: "learner-1" }), {
            wrapper: createWrapper(queryClient),
        });

        expect(result.current.isLoading).toBe(true);

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        });

        expect(result.current.isError).toBe(false);
        expect(result.current.journey?.learner_id).toBe("learner-1");
        expect(result.current.journey?.learner_name).toBe("张三");
        expect(getAdminJourneyMock).toHaveBeenCalledWith("learner-1");
    });

    it("exposes error state when query fails", async () => {
        getAdminJourneyMock.mockRejectedValue(new Error("[TRAINING_RECORD_NOT_FOUND]"));

        const queryClient = createAppQueryClient();
        const { result } = renderHook(() => useTeamJourneyDetail({ learnerId: "learner-x" }), {
            wrapper: createWrapper(queryClient),
        });

        await waitFor(() => {
            expect(result.current.isError).toBe(true);
        });

        expect(result.current.error).toBeInstanceOf(Error);
        expect(result.current.error?.message).toBe("[TRAINING_RECORD_NOT_FOUND]");
        expect(result.current.journey).toBeUndefined();
    });

    it("refetches journey detail when refetch is called", async () => {
        getAdminJourneyMock.mockResolvedValue(buildJourneyPayload());

        const queryClient = createAppQueryClient();
        const { result } = renderHook(() => useTeamJourneyDetail({ learnerId: "learner-1" }), {
            wrapper: createWrapper(queryClient),
        });

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        });

        getAdminJourneyMock.mockClear();
        getAdminJourneyMock.mockResolvedValue(buildJourneyPayload({ learner_name: "张三更新" }));

        await result.current.refetch();

        await waitFor(() => {
            expect(getAdminJourneyMock).toHaveBeenCalled();
        });
    });
});
