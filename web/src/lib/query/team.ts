import { queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

const TEAM_STALE_TIME_MS = 5 * 60_000;
const TEAM_GC_TIME_MS = 10 * 60_000;
const teamQueryDefaults = {
    staleTime: TEAM_STALE_TIME_MS,
    gcTime: TEAM_GC_TIME_MS,
    retry: false,
} as const;

const TEAM_DEFAULT_LIMIT = 50;

export const teamQueryKeys = {
    all: ["team"] as const,
    journeys: (limit: number, offset: number) =>
        [...teamQueryKeys.all, "journeys", limit, offset] as const,
    analytics: () => [...teamQueryKeys.all, "analytics"] as const,
};

export function teamJourneysQueryOptions(limit = TEAM_DEFAULT_LIMIT, offset = 0) {
    return queryOptions({
        queryKey: teamQueryKeys.journeys(limit, offset),
        queryFn: () => api.admin.salesTrainer.listAdminJourneys({ limit, offset }),
        ...teamQueryDefaults,
    });
}

export function teamAnalyticsQueryOptions() {
    return queryOptions({
        queryKey: teamQueryKeys.analytics(),
        queryFn: () => api.admin.salesTrainer.getJourneyAnalytics(),
        ...teamQueryDefaults,
    });
}
