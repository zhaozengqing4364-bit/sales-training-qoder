import type { UseQueryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { CurrentUser } from "@/lib/auth/current-user";

export const currentUserQueryKey = ["auth", "current-user"] as const;

export function getCurrentUserQueryOptions(
    initialData?: CurrentUser,
): UseQueryOptions<CurrentUser, Error, CurrentUser, typeof currentUserQueryKey> {
    return {
        queryKey: currentUserQueryKey,
        queryFn: () => api.user.getMe(),
        initialData,
    };
}
