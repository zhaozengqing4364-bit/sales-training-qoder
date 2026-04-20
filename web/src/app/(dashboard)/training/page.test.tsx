import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TrainingCategoriesPage from "./page";

const { getCategoriesMock, getMyHistoryMock } = vi.hoisted(() => ({
    getCategoriesMock: vi.fn(),
    getMyHistoryMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/training",
    useParams: () => ({}),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => <div className={className}>{children}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            training: {
                ...actual.api.training,
                getCategories: getCategoriesMock,
            },
            user: {
                ...actual.api.user,
                getMyHistory: getMyHistoryMock,
            },
        },
    };
});

describe("TrainingCategoriesPage", () => {
    beforeEach(() => {
        getCategoriesMock.mockReset();
        getMyHistoryMock.mockReset();
        getMyHistoryMock.mockResolvedValue({ sessions: [], total: 0, page: 1, page_size: 50, total_pages: 0 });
    });

    it("distinguishes backend failure from a genuinely empty category response", async () => {
        getCategoriesMock
            .mockRejectedValueOnce(new Error("training unavailable"))
            .mockResolvedValueOnce([
                {
                    id: "sales",
                    title: "后端恢复的销售训练",
                    description: "恢复后从后端返回的训练入口。",
                    icon_key: "Mic",
                    color_theme: "bg-blue-50 text-blue-600",
                    agent_count: 1,
                    tags: ["恢复"],
                    status: "active",
                },
            ]);

        render(<TrainingCategoriesPage />);

        expect(await screen.findByText("训练分类暂不可用，当前展示的是本地兜底入口，不代表后端没有训练模式。")).toBeTruthy();
        expect(screen.getByText("销售能力训练")).toBeTruthy();
        expect(screen.getByRole("button", { name: "重试训练分类" })).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "重试训练分类" }));

        expect(await screen.findByText("后端恢复的销售训练")).toBeTruthy();
        expect(screen.queryByText(/训练分类暂不可用/)).toBeNull();
    });

    it("uses fallback categories for empty success without showing degraded copy", async () => {
        getCategoriesMock.mockResolvedValueOnce([]);

        render(<TrainingCategoriesPage />);

        expect(await screen.findByText("销售能力训练")).toBeTruthy();
        const mobileQuickActions = screen.getByRole("navigation", { name: "移动快捷入口" });
        expect(mobileQuickActions).toBeTruthy();
        expect(within(mobileQuickActions).getByRole("link", { name: /训练大厅/ }).getAttribute("href")).toBe("/training");
        expect(within(mobileQuickActions).getByRole("link", { name: /历史/ }).getAttribute("href")).toBe("/history");
        expect(screen.queryByText(/训练分类暂不可用/)).toBeNull();
    });

    it("builds category ability maps only from completed evaluable history", async () => {
        getCategoriesMock.mockResolvedValueOnce([
            {
                id: "sales",
                title: "销售能力训练",
                description: "销售训练入口。",
                icon_key: "Mic",
                color_theme: "bg-blue-50 text-blue-600",
                agent_count: 2,
                tags: ["销售"],
                status: "active",
            },
            {
                id: "presentation",
                title: "演讲与表达训练",
                description: "演讲训练入口。",
                icon_key: "Presentation",
                color_theme: "bg-purple-50 text-purple-600",
                agent_count: 1,
                tags: ["演讲"],
                status: "active",
            },
        ]);
        getMyHistoryMock.mockResolvedValueOnce({
            sessions: [
                {
                    session_id: "sales-evaluable",
                    scenario_name: "销售对练",
                    scenario_type: "sales",
                    persona_name: null,
                    agent_name: "销售教练",
                    start_time: "2026-04-19T09:00:00.000Z",
                    duration_seconds: 480,
                    overall_score: 76,
                    report_status: "completed",
                    report_generated_at: "2026-04-19T09:12:00.000Z",
                    status: "completed",
                    evaluable: true,
                    not_evaluable_reason: null,
                    main_issue: {
                        issue_type: "异议处理",
                        issue_text: "面对强势质疑时没有先复述问题。",
                        recovery_rule: "先复述，再给证据。",
                    },
                    next_goal: {
                        goal_type: "推进下一步行动",
                        goal_text: "下一轮要明确约定客户下一步行动。",
                        rule: "retry",
                    },
                    stage_summary: [],
                },
                {
                    session_id: "sales-not-evaluable",
                    scenario_name: "销售对练",
                    scenario_type: "sales",
                    persona_name: null,
                    agent_name: "销售教练",
                    start_time: "2026-04-20T09:00:00.000Z",
                    duration_seconds: 120,
                    overall_score: 99,
                    report_status: "completed",
                    report_generated_at: "2026-04-20T09:12:00.000Z",
                    status: "completed",
                    evaluable: false,
                    not_evaluable_reason: "INSUFFICIENT_TURN_DATA",
                    stage_summary: [],
                },
                {
                    session_id: "presentation-evaluable",
                    scenario_name: "演讲训练",
                    scenario_type: "presentation",
                    persona_name: null,
                    agent_name: "演讲教练",
                    start_time: "2026-04-18T09:00:00.000Z",
                    duration_seconds: 600,
                    overall_score: 91,
                    report_status: "completed",
                    report_generated_at: "2026-04-18T09:12:00.000Z",
                    status: "completed",
                    evaluable: true,
                    not_evaluable_reason: null,
                    main_issue: {
                        issue_type: "结构铺垫",
                        issue_text: "第二页价值承接不足。",
                        recovery_rule: "先讲结论再补证据。",
                    },
                    stage_summary: [],
                },
            ],
            total: 3,
            page: 1,
            page_size: 50,
            total_pages: 1,
        });

        render(<TrainingCategoriesPage />);

        expect((await screen.findAllByText("训练能力地图")).length).toBeGreaterThan(0);
        expect(screen.getByText("76.0 分")).toBeTruthy();
        expect(screen.getByText("91.0 分")).toBeTruthy();
        expect(screen.getByText("待复练：推进下一步行动")).toBeTruthy();
        expect(screen.getByText("下一轮要明确约定客户下一步行动。")).toBeTruthy();
        expect(screen.getByText("最弱能力：结构铺垫")).toBeTruthy();
        expect(screen.getByText("第二页价值承接不足。")).toBeTruthy();
        expect(screen.getAllByText("只统计 completed/evaluable 训练。").length).toBeGreaterThan(0);
        expect(screen.queryByText("99.0 分")).toBeNull();
    });

});
