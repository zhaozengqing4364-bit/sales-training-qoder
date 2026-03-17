import { QueryClient } from "@tanstack/react-query";

function shouldRetry(failureCount: number, error: unknown): boolean {
    const status = typeof error === "object" && error !== null && "status" in error
        ? Number((error as { status?: number }).status)
        : undefined;

    if (status === 401 || status === 403) {
        return false;
    }

    if (typeof status === "number" && status >= 400 && status < 500 && status !== 429) {
        return false;
    }

    return failureCount < 1;
}

export function createAppQueryClient(): QueryClient {
    return new QueryClient({
        defaultOptions: {
            queries: {
                staleTime: 60_000,
                gcTime: 5 * 60_000,
                refetchOnWindowFocus: false,
                retry: shouldRetry,
            },
            mutations: {
                retry: false,
            },
        },
    });
}
