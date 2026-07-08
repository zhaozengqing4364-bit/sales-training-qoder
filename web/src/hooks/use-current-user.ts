"use client";

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { CurrentUser } from "@/lib/auth/current-user";
import { currentUserQueryKey, getCurrentUserQueryOptions } from "@/lib/query/auth";

function getCurrentUserIdentity(user: CurrentUser): string {
    return user.user_id || user.id;
}

function hasDifferentSessionUser(left: CurrentUser | undefined, right: CurrentUser): boolean {
    if (!left) {
        return true;
    }

    return getCurrentUserIdentity(left) !== getCurrentUserIdentity(right)
        || left.role !== right.role;
}

export function useCurrentUser(initialData?: CurrentUser) {
    const queryClient = useQueryClient();
    const query = useQuery(getCurrentUserQueryOptions(initialData));
    const shouldUseServerUser = initialData
        ? hasDifferentSessionUser(query.data, initialData)
        : false;

    useEffect(() => {
        if (!initialData) {
            return;
        }

        queryClient.setQueryData<CurrentUser>(currentUserQueryKey, (cachedUser) => (
            hasDifferentSessionUser(cachedUser, initialData) ? initialData : cachedUser
        ));
    }, [initialData, queryClient]);

    return shouldUseServerUser ? { ...query, data: initialData } : query;
}
