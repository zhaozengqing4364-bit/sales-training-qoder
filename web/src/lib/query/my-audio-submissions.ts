import { queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

const MY_AUDIO_SUBMISSIONS_STALE_TIME_MS = 60 * 1000;
const MY_AUDIO_SUBMISSIONS_GC_TIME_MS = 5 * 60_000;
const myAudioSubmissionsQueryDefaults = {
    staleTime: MY_AUDIO_SUBMISSIONS_STALE_TIME_MS,
    gcTime: MY_AUDIO_SUBMISSIONS_GC_TIME_MS,
    retry: false,
} as const;

const MY_AUDIO_SUBMISSIONS_DEFAULT_LIMIT = 20;

export const myAudioSubmissionsQueryKeys = {
    all: ["sales-trainer", "my-audio-submissions"] as const,
    list: (limit: number, offset: number) =>
        [...myAudioSubmissionsQueryKeys.all, limit, offset] as const,
};

export function myAudioSubmissionsQueryOptions(
    limit: number = MY_AUDIO_SUBMISSIONS_DEFAULT_LIMIT,
    offset: number = 0,
) {
    return queryOptions({
        queryKey: myAudioSubmissionsQueryKeys.list(limit, offset),
        queryFn: () => api.salesTrainer.listMyAudioSubmissions({ limit, offset }),
        ...myAudioSubmissionsQueryDefaults,
    });
}
