import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { SalesTrainerAdminModuleNav } from "./module-nav";
import type { SalesTrainerAdminCapabilities } from "@/lib/api/types";

const { getCapabilitiesMock } = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>{children}</a>
    ),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getCapabilities: getCapabilitiesMock,
                },
            },
        },
    };
});

function capabilities(
    overrides: Partial<SalesTrainerAdminCapabilities["capabilities"]>,
): SalesTrainerAdminCapabilities {
    const values = {
        admin_full_access: false,
        manage_content: false,
        manage_questions: false,
        manage_modules: false,
        manage_prompts: false,
        view_records: false,
        view_global_records: false,
        retry_jobs: false,
        regrade_history: false,
        view_logs: false,
        view_settings: false,
        ...overrides,
    };
    return {
        role: "support",
        role_label: "培训负责人",
        capabilities: values,
        capability_keys: Object.entries(values)
            .filter(([, enabled]) => enabled)
            .map(([key]) => key as SalesTrainerAdminCapabilities["capability_keys"][number]),
    };
}

describe("SalesTrainerAdminModuleNav", () => {
    it("renders all contextual entries for full access", () => {
        render(
            <SalesTrainerAdminModuleNav
                currentPath="/admin/sales-trainer/ai-coach"
                capabilities={capabilities({ admin_full_access: true })}
            />,
        );

        expect(screen.getByRole("link", { name: "路径配置" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/paths",
        );
        expect(screen.getByRole("link", { name: "AI 教练配置" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/ai-coach",
        );
    });

    it("does not leak contextual entries when only one item is capability-visible", () => {
        render(
            <SalesTrainerAdminModuleNav
                currentPath="/admin/sales-trainer/ai-coach"
                capabilities={capabilities({ manage_modules: true })}
            />,
        );

        expect(screen.queryByRole("link", { name: "AI 教练配置" })).toBeNull();
        expect(screen.queryByRole("navigation", { name: "路径配置模块内导航" })).toBeNull();
    });

    it("fails closed when capability loading fails", async () => {
        getCapabilitiesMock
            .mockRejectedValueOnce(new Error("forbidden"))
            .mockResolvedValueOnce(capabilities({ admin_full_access: true }));

        render(<SalesTrainerAdminModuleNav currentPath="/admin/sales-trainer/ai-coach" />);

        expect(await screen.findByText("销售训练导航权限加载失败")).toBeTruthy();
        expect(screen.getByText("forbidden")).toBeTruthy();
        expect(screen.queryByRole("link", { name: "AI 教练配置" })).toBeNull();
        expect(screen.queryByRole("link", { name: "路径配置" })).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "重新加载导航" }));

        expect(await screen.findByRole("link", { name: "AI 教练配置" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "路径配置" })).toBeTruthy();
        expect(screen.queryByText("销售训练导航权限加载失败")).toBeNull();
    });
});
