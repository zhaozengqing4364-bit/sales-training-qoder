import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createAppQueryClient } from "@/lib/query/client";
import { useTeamJourneyDetail } from "./use-team-journey-detail";

const getLearnerMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                newcomerTraining: {
                    ...actual.api.admin.newcomerTraining,
                    getLearner: getLearnerMock,
                },
            },
        },
    };
});

function wrapper(queryClient: QueryClient) {
    return function QueryWrapper({ children }: { children: React.ReactNode }) {
        return (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        );
    };
}

const journey = {
    learner: { learner_id: "learner-1", name: "张三" },
    cohort: { cohort_id: "cohort-1", name: "新人班" },
    journey: {
        contract_version: "journey_projection_v1",
        generated_at: "2026-07-18T00:00:00Z",
        data_freshness: "fresh",
        capabilities: ["view_journey"],
        status: "active",
        status_label: "训练进行中",
        status_reason: null,
        enrollment: { enrollment_id: "enrollment-1", status: "active", revision_id: "revision-1", version: 1 },
        path: { path_id: "path-1", title: "新人训练", revision_label: "首发版" },
        stages: [],
        progress: { completed_required: 0, total_required: 1, percentage: 0 },
        current_activity: null,
        background_tasks: [],
        recent_outcomes: [],
        primary_action: null,
        projection_version: 1,
    },
};

describe("useTeamJourneyDetail", () => {
    beforeEach(() => getLearnerMock.mockReset());

    it("loads the learner's canonical journey", async () => {
        getLearnerMock.mockResolvedValue(journey);
        const { result } = renderHook(() => useTeamJourneyDetail({ learnerId: "learner-1" }), {
            wrapper: wrapper(createAppQueryClient()),
        });
        await waitFor(() => expect(result.current.isLoading).toBe(false));
        expect(result.current.journey?.enrollment?.enrollment_id).toBe("enrollment-1");
        expect(getLearnerMock).toHaveBeenCalledWith("learner-1");
    });

    it("exposes errors and supports refetch", async () => {
        getLearnerMock.mockRejectedValueOnce(new Error("not found"));
        const { result } = renderHook(() => useTeamJourneyDetail({ learnerId: "learner-x" }), {
            wrapper: wrapper(createAppQueryClient()),
        });
        await waitFor(() => expect(result.current.isError).toBe(true));
        getLearnerMock.mockResolvedValue(journey);
        await act(async () => { await result.current.refetch(); });
        await waitFor(() => expect(result.current.isError).toBe(false));
    });
});
