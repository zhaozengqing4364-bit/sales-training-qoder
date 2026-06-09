"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import type { CurrentUser } from "@/lib/auth/current-user";
import { createAppQueryClient } from "@/lib/query/client";
import { getCurrentUserQueryOptions } from "@/lib/query/auth";

export function useCurrentUser(initialData?: CurrentUser) {
    const [serverQueryClient] = useState(() => createAppQueryClient());
    const queryClient = initialData ? serverQueryClient : undefined;

    return useQuery(getCurrentUserQueryOptions(initialData), queryClient);
}
