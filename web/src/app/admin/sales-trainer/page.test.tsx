import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerWorkbenchPage from "./page";
import type { SalesTrainerAdminCapabilities } from "@/lib/api/types";

const { getCapabilitiesMock, getManagerDashboardMock } = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
    getManagerDashboardMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer",
}));

vi.mock("@/components/admin/admin-layout-shells", () => ({
    AdminIndexShell: ({ children, header }: { children: ReactNode; header: ReactNode }) => (
        <div>
            {header}
            {children}
        </div>
    ),
    AdminPageHeader: ({ title, description, secondaryActions }: {
        title: string;
        description: string;
        secondaryActions?: ReactNode;
    }) => (
        <header>
            <h1>{title}</h1>
            <p>{description}</p>
            {secondaryActions}
        </header>
    ),
}));

vi.mock("@/components/admin/sales-trainer/module-nav", () => ({
    SALES_TRAINER_ADMIN_WORKBENCH_LINKS: [
        { href: "/admin/sales-trainer/units", label: "模块单元", icon: () => <span aria-hidden /> },
        { href: "/admin/sales-trainer/ai-coach", label: "AI 教练配置", icon: () => <span aria-hidden /> },
        { href: "/admin/sales-trainer/training-records", label: "训练记录", icon: () => <span aria-hidden /> },
    ],
    filterSalesTrainerAdminRouteItemsForCapabilities: (
        items: Array<{ href: string }>,
        capabilities: SalesTrainerAdminCapabilities | null,
    ) => {
        if (!capabilities) {
            return [];
        }
        if (capabilities.capabilities.admin_full_access) {
            return items;
        }
        return items.filter((item) => (
            item.href === "/admin/sales-trainer/units"
                ? capabilities.capabilities.manage_modules
                : item.href === "/admin/sales-trainer/ai-coach"
                    ? capabilities.capabilities.manage_prompts
                    : item.href === "/admin/sales-trainer/training-records"
                        ? capabilities.capabilities.view_records
                        : false
        ));
    },
    SalesTrainerAdminModuleNav: () => <nav aria-label="新人训练路径导航" />,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children }: { children: ReactNode }) => <div>{children}</div>,
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
                    getManagerDashboard: getManagerDashboardMock,
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

describe("SalesTrainerWorkbenchPage", () => {
    beforeEach(() => {
        getCapabilitiesMock.mockReset();
        getCapabilitiesMock.mockResolvedValue(capabilities({ admin_full_access: true }));
        getManagerDashboardMock.mockReset();
        getManagerDashboardMock.mockResolvedValue({
            generated_at: "2026-06-12T00:00:00Z",
            policy: {
                low_score_threshold: 70,
                repeat_practice_threshold: 2,
            },
            summary: {
                record_count: 12,
                completion_rate: 75,
                pass_rate: 66.67,
            },
            module_summaries: [],
            weak_dimensions: [
                {
                    dimension_key: "value_expression",
                    dimension_label: "价值表达",
                    record_count: 3,
                    learner_count: 2,
                },
            ],
            risk_learners: [
                {
                    user_id: "user-1",
                    user_name: "张三",
                    risk_reasons: ["low_score"],
                    lowest_score: 56,
                    record_count: 2,
                    suggested_action: "指定弱项复习",
                },
            ],
            intervention_suggestions: [
                {
                    user_id: "user-1",
                    user_name: "张三",
                    priority: "medium",
                    action: "指定弱项复习",
                },
            ],
        });
    });

    it("shows the manager dashboard summary and AI coach config workbench entry", async () => {
        render(<SalesTrainerWorkbenchPage />);

        await waitFor(() => {
            expect(getManagerDashboardMock).toHaveBeenCalled();
        });

        expect(screen.getByRole("heading", { name: "新人训练路径工作台" })).toBeTruthy();
        expect(screen.getByText("12")).toBeTruthy();
        expect(screen.getByText("75.0%")).toBeTruthy();
        expect(screen.getAllByText("价值表达").length).toBeGreaterThan(0);
        expect(screen.getAllByText("张三").length).toBeGreaterThan(0);
        expect(screen.getAllByText("指定弱项复习").length).toBeGreaterThan(0);
        expect(screen.getByRole("link", { name: /AI 教练配置/ }).getAttribute("href")).toBe(
            "/admin/sales-trainer/ai-coach",
        );
        expect(screen.getByRole("link", { name: /训练记录/ }).getAttribute("href")).toBe(
            "/admin/sales-trainer/training-records",
        );
    });

    it("filters workbench entries by admin capabilities", async () => {
        getCapabilitiesMock.mockResolvedValueOnce(capabilities({
            manage_content: true,
            view_records: true,
        }));

        render(<SalesTrainerWorkbenchPage />);

        await waitFor(() => {
            expect(getCapabilitiesMock).toHaveBeenCalled();
        });

        expect(screen.getByRole("link", { name: /训练记录/ }).getAttribute("href")).toBe(
            "/admin/sales-trainer/training-records",
        );
        expect(screen.queryByRole("link", { name: /AI 教练配置/ })).toBeNull();
        expect(screen.queryByRole("link", { name: /模块单元/ })).toBeNull();
    });

    it("fails closed for direct workbench access before loading dashboard data", async () => {
        getCapabilitiesMock.mockResolvedValueOnce(capabilities({ view_records: true }));

        render(<SalesTrainerWorkbenchPage />);

        expect(await screen.findByText("新人训练工作台不可访问")).toBeTruthy();
        expect(screen.getByText(/系统不会加载管理看板数据/)).toBeTruthy();
        expect(getManagerDashboardMock).not.toHaveBeenCalled();
        expect(screen.queryByText("训练记录")).toBeNull();
        expect(screen.queryByText("风险学员")).toBeNull();
        expect(screen.queryByRole("link", { name: /训练记录/ })).toBeNull();
    });

    it("does not show all workbench entries when capability loading fails", async () => {
        getCapabilitiesMock.mockRejectedValueOnce(new Error("forbidden"));

        render(<SalesTrainerWorkbenchPage />);

        expect(await screen.findByText("新人训练工作台不可访问")).toBeTruthy();
        expect(screen.getByText("forbidden")).toBeTruthy();

        expect(screen.queryByRole("link", { name: /AI 教练配置/ })).toBeNull();
        expect(screen.queryByRole("link", { name: /训练记录/ })).toBeNull();
        expect(getManagerDashboardMock).not.toHaveBeenCalled();
    });

    it("shows a retryable dashboard error instead of empty metrics", async () => {
        getManagerDashboardMock.mockRejectedValueOnce(new Error("dashboard down"));

        render(<SalesTrainerWorkbenchPage />);

        expect(await screen.findByText("新人训练看板加载失败")).toBeTruthy();
        expect(screen.getByText(/已停止渲染指标和风险学员空态/)).toBeTruthy();
        expect(screen.queryByText("完成率")).toBeNull();
        expect(screen.queryByText("暂无风险学员")).toBeNull();
    });

    it("treats malformed successful dashboard responses as load errors", async () => {
        getManagerDashboardMock.mockResolvedValueOnce({
            generated_at: "2026-06-12T00:00:00Z",
            policy: {},
            summary: {
                record_count: 12,
            },
            module_summaries: [],
            weak_dimensions: [],
            risk_learners: [],
            intervention_suggestions: [],
        });

        render(<SalesTrainerWorkbenchPage />);

        expect(await screen.findByText("新人训练看板加载失败")).toBeTruthy();
        expect(screen.getByText(/summary\.completion_rate/)).toBeTruthy();
        expect(screen.queryByText("完成率")).toBeNull();
        expect(screen.queryByText("暂无风险学员")).toBeNull();
    });
});
