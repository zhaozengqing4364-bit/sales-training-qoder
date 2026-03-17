"use client";

import { QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { authHandler } from "@/lib/auth-handler";
import { currentUserQueryKey } from "@/lib/query/auth";
import { createAppQueryClient } from "@/lib/query/client";

function AuthQueryBridge() {
    const queryClient = useQueryClient();

    useEffect(() => {
        return authHandler.subscribe(() => {
            void queryClient.invalidateQueries({ queryKey: currentUserQueryKey });
        });
    }, [queryClient]);

    return null;
}

export function AppProviders({ children }: { children: React.ReactNode }) {
    const [queryClient] = useState(() => createAppQueryClient());

    return (
        <QueryClientProvider client={queryClient}>
            <AuthQueryBridge />
            {children}
        </QueryClientProvider>
    );
}
