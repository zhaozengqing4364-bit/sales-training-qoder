import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createAppQueryClient } from "@/lib/query/client";
import { useTeamJourneyDetail } from "./use-team-journey-detail";

const getLearnerJourneyMock = vi.hoisted(() => vi.fn());

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
                    getLearnerJourney: getLearnerJourneyMock,
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
    enrollment_id: "enrollment-1",
    path_revision_id: "revision-1",
    path_title: "新人训练",
    phases: [],
    progress: { completed_activities: 0, total_activities: 1, percentage: 0 },
    primary_next_action: null,
};

describe("useTeamJourneyDetail", () => {
    beforeEach(() => getLearnerJourneyMock.mockReset());

    it("loads the learner's canonical journey", async () => {
        getLearnerJourneyMock.mockResolvedValue(journey);
        const { result } = renderHook(() => useTeamJourneyDetail({ learnerId: "learner-1" }), {
            wrapper: wrapper(createAppQueryClient()),
        });
        await waitFor(() => expect(result.current.isLoading).toBe(false));
        expect(result.current.journey?.enrollment_id).toBe("enrollment-1");
        expect(getLearnerJourneyMock).toHaveBeenCalledWith("learner-1");
    });

    it("exposes errors and supports refetch", async () => {
        getLearnerJourneyMock.mockRejectedValueOnce(new Error("not found"));
        const { result } = renderHook(() => useTeamJourneyDetail({ learnerId: "learner-x" }), {
            wrapper: wrapper(createAppQueryClient()),
        });
        await waitFor(() => expect(result.current.isError).toBe(true));
        getLearnerJourneyMock.mockResolvedValue(journey);
        await act(async () => { await result.current.refetch(); });
        await waitFor(() => expect(result.current.isError).toBe(false));
    });
});
