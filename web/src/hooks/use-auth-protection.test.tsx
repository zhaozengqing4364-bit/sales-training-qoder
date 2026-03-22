import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders } from "@/components/providers/app-providers";
import { useAuthProtection } from "./use-auth-protection";

const { replaceMock, getMeMock } = vi.hoisted(() => ({
    replaceMock: vi.fn(),
    getMeMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        replace: replaceMock,
    }),
    usePathname: () => "/support/runtime",
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            user: {
                ...actual.api.user,
                getMe: getMeMock,
            },
        },
    };
});

function createWrapper() {
    return function Wrapper({ children }: { children: React.ReactNode }) {
        return <AppProviders>{children}</AppProviders>;
    };
}

describe("useAuthProtection", () => {
    beforeEach(() => {
        replaceMock.mockReset();
        getMeMock.mockReset();
    });

    it("authorizes an allowed role using the shared current-user query", async () => {
        getMeMock.mockResolvedValue({
            user_id: "support-1",
            id: "support-1",
            name: "支持同学",
            display_name: "支持同学",
            email: "support@test.com",
            role: "support",
            is_active: true,
            created_at: "",
        });

        const { result } = renderHook(
            () => useAuthProtection({ requiredRoles: ["support", "admin"] }),
            { wrapper: createWrapper() },
        );

        await waitFor(() => {
            expect(result.current.isAuthorized).toBe(true);
        });

        expect(replaceMock).not.toHaveBeenCalled();
    });

    it("redirects to login when the current-user query fails", async () => {
        const unauthorizedError = Object.assign(new Error("unauthorized"), { status: 401 });
        getMeMock.mockRejectedValue(unauthorizedError);

        renderHook(() => useAuthProtection(), { wrapper: createWrapper() });

        await waitFor(() => {
            expect(replaceMock).toHaveBeenCalledWith("/login");
        });
    });

    it("does not redirect to login when the current-user query fails with a transient server error", async () => {
        const transientError = Object.assign(new Error("server unavailable"), { status: 503 });
        getMeMock.mockRejectedValue(transientError);

        const { result } = renderHook(() => useAuthProtection(), { wrapper: createWrapper() });

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        }, { timeout: 2500 });

        expect(result.current.isAuthorized).toBe(false);
        expect(replaceMock).not.toHaveBeenCalled();
    });
});
