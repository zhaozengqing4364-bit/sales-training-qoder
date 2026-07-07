"use client";

import { useQuery } from "@tanstack/react-query";

import {
    teamAnalyticsQueryOptions,
    teamJourneysQueryOptions,
} from "@/lib/query/team";

export interface UseTeamJourneysParams {
    limit?: number;
    offset?: number;
}

export function useTeamJourneys(params: UseTeamJourneysParams = {}) {
    const limit = params.limit ?? 50;
    const offset = params.offset ?? 0;
    const journeys = useQuery(teamJourneysQueryOptions(limit, offset));
    const analytics = useQuery(teamAnalyticsQueryOptions());

    const isLoading = journeys.isPending || analytics.isPending;
    const isError = journeys.isError || analytics.isError;
    const error = journeys.error ?? analytics.error ?? null;

    return {
        journeys,
        analytics,
        isLoading,
        isError,
        error,
        refetch: async () => {
            await Promise.allSettled([
                journeys.refetch(),
                analytics.refetch(),
            ]);
        },
    };
}
