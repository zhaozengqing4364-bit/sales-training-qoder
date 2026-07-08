import type { UseQueryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { CurrentUser } from "@/lib/auth/current-user";

export const currentUserQueryKey = ["auth", "current-user"] as const;

const CURRENT_USER_STALE_TIME_MS = 5 * 60_000;
const CURRENT_USER_GC_TIME_MS = 10 * 60_000;

export function getCurrentUserQueryOptions(
    initialData?: CurrentUser,
): UseQueryOptions<CurrentUser, Error, CurrentUser, typeof currentUserQueryKey> {
    return {
        queryKey: currentUserQueryKey,
        queryFn: () => api.user.getMe(),
        initialData,
        staleTime: CURRENT_USER_STALE_TIME_MS,
        gcTime: CURRENT_USER_GC_TIME_MS,
    };
}
