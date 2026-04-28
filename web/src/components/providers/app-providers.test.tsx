import { act, render, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders } from "./app-providers";
import { authHandler } from "@/lib/auth-handler";
import { currentUserQueryKey } from "@/lib/query/auth";

const { pushMock, replaceMock } = vi.hoisted(() => ({
    pushMock: vi.fn(),
    replaceMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
        replace: replaceMock,
    }),
}));

let observedQueryClient: QueryClient | null = null;

function SeedCurrentUserCache() {
    const queryClient = useQueryClient();

    useEffect(() => {
        observedQueryClient = queryClient;
        queryClient.setQueryData(currentUserQueryKey, {
            id: "user-1",
            user_id: "user-1",
            name: "Cached User",
            display_name: "Cached User",
            email: "cached@example.com",
            role: "user",
            is_active: true,
            created_at: "2026-04-28T00:00:00Z",
        });
    }, [queryClient]);

    return null;
}

describe("AppProviders auth query bridge", () => {
    beforeEach(() => {
        observedQueryClient = null;
        pushMock.mockReset();
        replaceMock.mockReset();
    });

    afterEach(() => {
        observedQueryClient = null;
    });

    it("clears cached current-user data immediately when auth state changes", async () => {
        render(
            <AppProviders>
                <SeedCurrentUserCache />
            </AppProviders>,
        );

        await waitFor(() => {
            expect(observedQueryClient?.getQueryData(currentUserQueryKey)).toMatchObject({
                id: "user-1",
            });
        });

        act(() => {
            authHandler.logout("auth-cache-clear-test");
        });

        expect(observedQueryClient?.getQueryData(currentUserQueryKey)).toBeNull();
        expect(pushMock).not.toHaveBeenCalled();
        expect(replaceMock).not.toHaveBeenCalled();
    });
});
