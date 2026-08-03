import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createAppQueryClient } from "@/lib/query/client";
import { useTeamJourneys } from "./use-team-journeys";

const listLearnersMock = vi.hoisted(() => vi.fn());

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
                    listLearners: listLearnersMock,
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
        learner: { learner_id: "learner-1", name: "张三" },
        cohort: { cohort_id: "cohort-1", name: "销售新人班" },
        enrollment: { enrollment_id: "enrollment-1", status: "active", revision_id: "revision-1", version: 1 },
        path: { path_id: "path-1", title: "新人训练", revision_label: "首发版" },
        status: "active",
        status_label: "训练进行中",
        progress: { completed_required: 0, total_required: 1, percentage: 0 },
        current_activity: null,
        primary_action: null,
        updated_at: "2026-07-18T00:00:00Z",
    }],
    total: 1,
    limit: 50,
    offset: 0,
    applied_filters: { search: null },
    generated_at: "2026-07-18T00:00:00Z",
};

describe("useTeamJourneys", () => {
    beforeEach(() => listLearnersMock.mockReset());

    it("loads canonical journey projections", async () => {
        listLearnersMock.mockResolvedValue(response);
        const { result } = renderHook(() => useTeamJourneys({ limit: 50, offset: 0 }), {
            wrapper: wrapper(createAppQueryClient()),
        });
        await waitFor(() => expect(result.current.isLoading).toBe(false));
        expect(result.current.isError).toBe(false);
        expect(result.current.journeys.data?.items[0]?.learner.name).toBe("张三");
        expect(listLearnersMock).toHaveBeenCalledWith({ limit: 50, offset: 0 });
    });

    it("exposes errors and supports refetch", async () => {
        listLearnersMock.mockRejectedValueOnce(new Error("journeys unavailable"));
        const { result } = renderHook(() => useTeamJourneys(), {
            wrapper: wrapper(createAppQueryClient()),
        });
        await waitFor(() => expect(result.current.isError).toBe(true));
        listLearnersMock.mockResolvedValue(response);
        await act(async () => { await result.current.refetch(); });
        await waitFor(() => expect(result.current.isError).toBe(false));
    });
});
