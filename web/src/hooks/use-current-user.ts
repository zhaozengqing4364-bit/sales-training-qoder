"use client";

import { useQuery } from "@tanstack/react-query";

import type { CurrentUser } from "@/lib/auth/current-user";
import { getCurrentUserQueryOptions } from "@/lib/query/auth";

export function useCurrentUser(initialData?: CurrentUser) {
    return useQuery(getCurrentUserQueryOptions(initialData));
}
