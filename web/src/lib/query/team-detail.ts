import { queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

const TEAM_DETAIL_STALE_TIME_MS = 5 * 60_000;
const TEAM_DETAIL_GC_TIME_MS = 10 * 60_000;
const teamDetailQueryDefaults = {
    staleTime: TEAM_DETAIL_STALE_TIME_MS,
    gcTime: TEAM_DETAIL_GC_TIME_MS,
    retry: false,
} as const;

export const teamDetailQueryKeys = {
    all: ["team", "detail"] as const,
    detail: (learnerId: string) =>
        [...teamDetailQueryKeys.all, learnerId] as const,
};

export function teamDetailQueryOptions(learnerId: string) {
    return queryOptions({
        queryKey: teamDetailQueryKeys.detail(learnerId),
        queryFn: () => api.admin.newcomerTraining.getLearner(learnerId),
        ...teamDetailQueryDefaults,
    });
}
