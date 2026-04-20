"use client";

import { QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

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

function AuthNavigationBridge() {
    const router = useRouter();

    useEffect(() => authHandler.setNavigator((to, options) => {
        if (options?.mode === "push") {
            router.push(to);
            return;
        }

        router.replace(to);
    }), [router]);

    return null;
}

export function AppProviders({ children }: { children: React.ReactNode }) {
    const [queryClient] = useState(() => createAppQueryClient());

    return (
        <QueryClientProvider client={queryClient}>
            <AuthQueryBridge />
            <AuthNavigationBridge />
            {children}
        </QueryClientProvider>
    );
}
