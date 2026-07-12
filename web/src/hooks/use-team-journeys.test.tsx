import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createAppQueryClient } from "@/lib/query/client";
import { useTeamJourneys } from "./use-team-journeys";

const listJourneysMock = vi.hoisted(() => vi.fn());

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
                    listJourneys: listJourneysMock,
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

const response = {
    items: [{
        learner_id: "learner-1",
        learner_name: "张三",
        department: "销售部",
        journey: {
            enrollment_id: "enrollment-1",
            path_revision_id: "revision-1",
            path_title: "新人训练",
            phases: [],
            progress: { completed_activities: 0, total_activities: 1, percentage: 0 },
            primary_next_action: null,
        },
    }],
    total: 1,
};

describe("useTeamJourneys", () => {
    beforeEach(() => listJourneysMock.mockReset());

    it("loads canonical journey projections", async () => {
        listJourneysMock.mockResolvedValue(response);
        const { result } = renderHook(() => useTeamJourneys({ limit: 50, offset: 0 }), {
            wrapper: wrapper(createAppQueryClient()),
        });
        await waitFor(() => expect(result.current.isLoading).toBe(false));
        expect(result.current.isError).toBe(false);
        expect(result.current.journeys.data?.items[0]?.learner_name).toBe("张三");
        expect(listJourneysMock).toHaveBeenCalledWith({ limit: 50, offset: 0 });
    });

    it("exposes errors and supports refetch", async () => {
        listJourneysMock.mockRejectedValueOnce(new Error("journeys unavailable"));
        const { result } = renderHook(() => useTeamJourneys(), {
            wrapper: wrapper(createAppQueryClient()),
        });
        await waitFor(() => expect(result.current.isError).toBe(true));
        listJourneysMock.mockResolvedValue(response);
        await act(async () => { await result.current.refetch(); });
        await waitFor(() => expect(result.current.isError).toBe(false));
    });
});
