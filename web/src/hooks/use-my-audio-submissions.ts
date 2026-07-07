"use client";

import { useQuery } from "@tanstack/react-query";

import { myAudioSubmissionsQueryOptions } from "@/lib/query/my-audio-submissions";

export interface UseMyAudioSubmissionsParams {
    limit?: number;
    offset?: number;
    enabled?: boolean;
}

export function useMyAudioSubmissions(params: UseMyAudioSubmissionsParams = {}) {
    const limit = params.limit ?? 20;
    const offset = params.offset ?? 0;
    const enabled = params.enabled ?? true;
    const query = useQuery({
        ...myAudioSubmissionsQueryOptions(limit, offset),
        enabled,
    });

    const isLoading = query.isPending;
    const isError = query.isError;
    const error = query.error ?? null;

    return {
        submissions: query.data?.items ?? [],
        total: query.data?.total ?? 0,
        isLoading,
        isError,
        error,
        refetch: async () => {
            await query.refetch();
        },
    };
}
