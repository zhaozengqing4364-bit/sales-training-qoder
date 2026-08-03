import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    FoundationAdminCapabilityBoundary,
    FoundationAdminWorkspaceNav,
} from "./workspace-nav";

const getCapabilities = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/newcomer-training/paths",
}));
vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => <a href={href} {...props}>{children}</a>,
}));
vi.mock("@/lib/api/client", () => ({
    api: { admin: { newcomerTraining: { getCapabilities } } },
    getApiErrorMessage: (error: unknown) => error instanceof Error ? error.message : "加载失败",
}));

function renderWithQuery(children: ReactNode) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>);
}

describe("FoundationAdminWorkspaceNav", () => {
    beforeEach(() => {
        getCapabilities.mockReset();
        getCapabilities.mockResolvedValue({
            capabilities: ["edit_paths", "manage_cohorts"],
            access: { edit_paths: true, manage_cohorts: true },
            permission_help: "请联系组织管理员申请权限。",
        });
    });

    it("uses the backend capability projection as the navigation authority", async () => {
        renderWithQuery(<FoundationAdminWorkspaceNav />);

        expect((await screen.findByRole("link", { name: /路径与版本/ })).getAttribute("href"))
            .toBe("/admin/newcomer-training/paths");
        expect(screen.getByRole("link", { name: /学员与班级/ })).toBeTruthy();
        expect(screen.queryByRole("link", { name: /治理设置/ })).toBeNull();
        expect(screen.queryByRole("link", { name: /发布记录/ })).toBeNull();
    });

    it("renders an explicit permission state instead of leaking a hidden action", async () => {
        renderWithQuery(
            <FoundationAdminCapabilityBoundary capability="publish_releases">
                <button type="button">发布版本</button>
            </FoundationAdminCapabilityBoundary>,
        );

        expect(await screen.findByRole("heading", { name: "当前账号不能访问此工作区" })).toBeTruthy();
        expect(screen.queryByRole("button", { name: "发布版本" })).toBeNull();
        expect(screen.getByText("请联系组织管理员申请权限。")).toBeTruthy();
    });
});
