import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
    ADMIN_CONSOLE_ROLE_VALUES,
    canUseAdminConsoleRole,
    hasRequiredRole,
    isPlatformAdminRole,
    normalizeCurrentUser,
    shouldStayInSalesTrainerAdmin,
    type CurrentUser,
} from "@/lib/auth/current-user";
import { currentUserQueryKey } from "@/lib/query/auth";
import { createAppQueryClient } from "@/lib/query/client";

import { useCurrentUser } from "./use-current-user";

const currentUser = {
    id: "user-1",
    user_id: "user-1",
    name: "王小明",
    display_name: "王小明",
    email: "learner@example.com",
    role: "user",
    is_active: true,
    created_at: "2026-04-01T00:00:00Z",
} as const satisfies CurrentUser;

const nextSessionUser = {
    id: "user-2",
    user_id: "user-2",
    name: "李小红",
    display_name: "李小红",
    email: "next@example.com",
    role: "admin",
    is_active: true,
    created_at: "2026-04-02T00:00:00Z",
} as const satisfies CurrentUser;

function createWrapper(queryClient: QueryClient) {
    return function Wrapper({ children }: { children: React.ReactNode }) {
        return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    };
}

describe("useCurrentUser", () => {
    it("seeds the shared current-user query cache from server-provided user data", async () => {
        const queryClient = createAppQueryClient();

        const { result } = renderHook(() => useCurrentUser(currentUser), {
            wrapper: createWrapper(queryClient),
        });

        await waitFor(() => {
            expect(result.current.data?.display_name).toBe("王小明");
        });

        expect(queryClient.getQueryData(currentUserQueryKey)).toMatchObject({
            id: "user-1",
            display_name: "王小明",
        });
    });

    it("replaces stale cached current-user data with the server-provided session user", async () => {
        const queryClient = createAppQueryClient();
        queryClient.setQueryData(currentUserQueryKey, currentUser);

        const { result } = renderHook(() => useCurrentUser(nextSessionUser), {
            wrapper: createWrapper(queryClient),
        });

        expect(result.current.data?.id).toBe("user-2");
        expect(result.current.data?.role).toBe("admin");

        await waitFor(() => {
            expect(queryClient.getQueryData(currentUserQueryKey)).toMatchObject({
                id: "user-2",
                role: "admin",
            });
        });
    });

    it("preserves project-specific admin roles instead of coercing them to user", () => {
        const user = normalizeCurrentUser({
            id: "content-1",
            display_name: "内容管理员",
            role: "content_admin",
        });

        expect(user.role).toBe("content_admin");
    });

    it("uses one admin-console role vocabulary for platform, content, ops and auditors", () => {
        expect(ADMIN_CONSOLE_ROLE_VALUES).toEqual(expect.arrayContaining([
            "admin",
            "super_admin",
            "content_admin",
            "newcomer_content_admin",
            "ops",
            "operator",
            "operations",
            "sre",
            "readonly_auditor",
        ]));
        expect(isPlatformAdminRole(" Super_Admin ")).toBe(true);
        expect(canUseAdminConsoleRole(" SRE ")).toBe(true);
        expect(canUseAdminConsoleRole("readonly_auditor")).toBe(true);
        expect(shouldStayInSalesTrainerAdmin("ops")).toBe(true);
        expect(shouldStayInSalesTrainerAdmin("readonly_auditor")).toBe(false);
    });

    it("matches canonical required roles against compatible aliases", () => {
        expect(hasRequiredRole({ role: "super_admin" }, ["admin"])).toBe(true);
        expect(hasRequiredRole({ role: "newcomer_content_admin" }, ["content_admin"])).toBe(true);
        expect(hasRequiredRole({ role: "sre" }, ["operations"])).toBe(true);
        expect(hasRequiredRole({ role: "readonly_auditor" }, ["admin"])).toBe(false);
    });
});
