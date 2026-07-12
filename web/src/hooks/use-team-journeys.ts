"use client";

import { useQuery } from "@tanstack/react-query";

import {
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
    const isLoading = journeys.isPending;
    const isError = journeys.isError;
    const error = journeys.error ?? null;

    return {
        journeys,
        isLoading,
        isError,
        error,
        refetch: async () => {
            await journeys.refetch();
        },
    };
}
