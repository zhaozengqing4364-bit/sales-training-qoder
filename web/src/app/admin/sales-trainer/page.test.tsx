import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerWorkbenchPage from "./page";

const { getManagerDashboardMock } = vi.hoisted(() => ({
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
                    getManagerDashboard: getManagerDashboardMock,
                },
            },
        },
    };
});

describe("SalesTrainerWorkbenchPage", () => {
    beforeEach(() => {
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
});
