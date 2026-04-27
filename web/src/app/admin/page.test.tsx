import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminDashboardPage from "./page";

const { healthMock, getDashboardMock } = vi.hoisted(() => ({
    healthMock: vi.fn(),
    getDashboardMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            internal: {
                ...actual.api.internal,
                health: healthMock,
            },
            analyticsOpen: {
                ...actual.api.analyticsOpen,
                getDashboard: getDashboardMock,
            },
        },
    };
});

describe("AdminDashboardPage", () => {
    beforeEach(() => {
        healthMock.mockReset();
        getDashboardMock.mockReset();

        healthMock.mockResolvedValue({ status: "ok" });
        getDashboardMock.mockResolvedValue({
            effectiveness: {
                pass_rate_3min_flow: 66.7,
                pass_rate_5turn_defense: 58.3,
                pass_rate_4step_structure: 75,
                next_day_retry_rate: 41.7,
            },
        });
    });

    it("keeps only the top effectiveness card as live data and marks the rest as pending connected data", async () => {
        render(<AdminDashboardPage />);

        await waitFor(() => {
            expect(healthMock).toHaveBeenCalledTimes(1);
            expect(getDashboardMock).toHaveBeenCalledWith({ days: 7 });
        });

        expect(await screen.findByText("管理首页接入状态说明")).toBeTruthy();
        expect(screen.queryByPlaceholderText("全局搜索...")).toBeNull();
        expect(screen.getByText("66.7%")).toBeTruthy();
        expect(screen.getByText("58.3%")).toBeTruthy();
        expect(screen.getAllByText("待接真实统计").length).toBeGreaterThanOrEqual(3);
        expect(screen.getByText(/以下卡片当前作为管理入口与待接权威数据提示/)).toBeTruthy();
        expect(screen.getByText("当前管理入口")).toBeTruthy();
        expect(screen.getByText("直接进入当前已接入数据源的管理面；首页不提供未接入的表单、日志控制台或自动告警入口。"))
            .toBeTruthy();
        expect(screen.getAllByRole("link", { name: "进入用户管理" }).some((link) => link.getAttribute("href") === "/admin/users"))
            .toBe(true);
        expect(screen.getAllByRole("link", { name: "进入数据分析" }).some((link) => link.getAttribute("href") === "/admin/analytics"))
            .toBe(true);
        expect(screen.getAllByRole("link", { name: "进入系统日志" }).some((link) => link.getAttribute("href") === "/admin/logs"))
            .toBe(true);
        expect(screen.queryByText("2,543")).toBeNull();
        expect(screen.queryByText("84")).toBeNull();
        expect(screen.queryByText("42%")).toBeNull();
        expect(screen.queryByText("68%")).toBeNull();
        expect(screen.queryByText("75%")).toBeNull();
        expect(screen.queryByText("450 GB")).toBeNull();
        expect(screen.queryByText("GPT-4-Turbo")).toBeNull();
        expect(screen.queryByText("API 速率限制临近")).toBeNull();
        expect(screen.queryByText("证书过期")).toBeNull();
        expect(screen.queryByText("系统备份完成")).toBeNull();
        expect(screen.queryByText("动态项 #1 描述...")).toBeNull();
    });
});
