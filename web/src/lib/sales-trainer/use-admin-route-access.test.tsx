import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSalesTrainerAdminRouteAccess } from "./use-admin-route-access";

const { getCapabilities } = vi.hoisted(() => ({ getCapabilities: vi.fn() }));

vi.mock("@/lib/api/client", () => ({
    api: { admin: { salesTrainer: { getCapabilities } } },
    getApiErrorMessage: (error: Error) => error.message,
}));

const FULL_ACCESS = {
    role: "admin",
    role_label: "管理员",
    capability_keys: ["admin_full_access"],
    capabilities: {
        admin_full_access: true,
        manage_content: true,
        manage_questions: true,
        manage_modules: true,
        manage_prompts: true,
        view_records: true,
        view_global_records: true,
        retry_jobs: true,
        regrade_history: true,
        view_logs: true,
        view_settings: true,
    },
};

describe("useSalesTrainerAdminRouteAccess", () => {
    beforeEach(() => getCapabilities.mockReset().mockResolvedValue(FULL_ACCESS));

    it("reuses the capability result across admin route mounts", async () => {
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        });
        const wrapper = ({ children }: { children: ReactNode }) => (
            <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        );

        const first = renderHook(
            () => useSalesTrainerAdminRouteAccess("/admin/newcomer-training/path"),
            { wrapper },
        );
        await waitFor(() => expect(first.result.current.canAccess).toBe(true));
        first.unmount();

        const second = renderHook(
            () => useSalesTrainerAdminRouteAccess("/admin/sales-trainer/readiness"),
            { wrapper },
        );
        await waitFor(() => expect(second.result.current.canAccess).toBe(true));

        expect(getCapabilities).toHaveBeenCalledTimes(1);
    });
});
