import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainingPage from "./page";

const {
    backMock,
    pushMock,
    getSalesAgentsMock,
    listScenariosMock,
    getSalesPersonasMock,
    getRecommendationMock,
    getMyHistoryMock,
} = vi.hoisted(() => ({
    backMock: vi.fn(),
    pushMock: vi.fn(),
    getSalesAgentsMock: vi.fn(),
    listScenariosMock: vi.fn(),
    getSalesPersonasMock: vi.fn(),
    getRecommendationMock: vi.fn(),
    getMyHistoryMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        back: backMock,
        push: pushMock,
    }),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button {...props}>{children}</button>
    ),
}));

vi.mock("@/components/ui/agent-card", () => ({
    AgentCard: ({ name, actionText, onClick }: { name: string; actionText: string; onClick: () => void }) => (
        <button type="button" onClick={onClick}>
            {name}
            {actionText}
        </button>
    ),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            training: {
                ...actual.api.training,
                getSalesAgents: getSalesAgentsMock,
            },
            scenarios: {
                ...actual.api.scenarios,
                list: listScenariosMock,
                getSalesPersonas: getSalesPersonasMock,
            },
            dashboard: {
                ...actual.api.dashboard,
                getRecommendation: getRecommendationMock,
            },
            user: {
                ...actual.api.user,
                getMyHistory: getMyHistoryMock,
            },
        },
    };
});

vi.mock("@/lib/debug", () => ({
    debug: {
        error: vi.fn(),
    },
}));

vi.mock("lucide-react", async () => {
    const actual = await vi.importActual<typeof import("lucide-react")>("lucide-react");
    const Icon = ({ children }: { children?: ReactNode }) => <span>{children}</span>;
    return {
        ...actual,
        ArrowLeft: Icon,
        Users2: Icon,
        Target: Icon,
    };
});

describe("SalesTrainingPage core combinations", () => {
    beforeEach(() => {
        backMock.mockReset();
        pushMock.mockReset();
        getSalesAgentsMock.mockReset();
        listScenariosMock.mockReset();
        getSalesPersonasMock.mockReset();
        getRecommendationMock.mockReset();
        getMyHistoryMock.mockReset();

        getSalesAgentsMock.mockResolvedValue([
            {
                id: "agent-sales",
                name: "销售陪练",
                description: "覆盖破冰、需求挖掘、价值表达、异议处理和推进下一步。",
                category: "sales",
                status: "published",
                role: "销售全流程教练",
                difficulty: "medium",
                ui_metadata: { tags: ["异议处理", "需求挖掘"] },
            },
        ]);
        listScenariosMock.mockResolvedValue([
            {
                scenario_id: "sales-1",
                scenario_type: "sales",
                name: "销售对练",
                is_active: true,
            },
        ]);
        getSalesPersonasMock.mockResolvedValue([
            {
                id: "persona-cold",
                name: "冷淡型",
                description: "回应少，需要先破冰。",
                characteristics: ["冷淡型客户"],
                difficulty: "medium",
            },
            {
                id: "persona-price",
                name: "价格敏感型",
                description: "重点关注价格和 ROI。",
                characteristics: ["价格敏感型客户"],
                difficulty: "hard",
            },
        ]);
        getRecommendationMock.mockResolvedValue({
            title: "继续训练",
            reason: "完成一次新的可评估销售训练。",
            action_label: "开始训练",
            target_path: "/training/sales",
            recommendation_kind: "onboarding",
            scenario_type: "sales",
        });
        getMyHistoryMock.mockResolvedValue({
            sessions: [],
            total: 0,
            page: 1,
            page_size: 5,
            total_pages: 0,
        });
    });

    it("turns matched 80/20 combinations into focused start routes", async () => {
        render(<SalesTrainingPage />);

        expect((await screen.findAllByText("去开练：销售陪练 · 价格敏感型")).length).toBeGreaterThan(0);

        fireEvent.click(screen.getByRole("button", { name: /组合 3\s+需求挖掘\s+客户角色：价格敏感型客户/ }));

        expect(pushMock).toHaveBeenCalledTimes(1);
        const pushedUrl = pushMock.mock.calls[0][0] as string;
        expect(pushedUrl).toContain("/agents/agent-sales?persona_id=persona-price");

        const params = new URLSearchParams(pushedUrl.split("?")[1]);
        const focusIntent = JSON.parse(params.get("focus_intent") || "{}") as {
            version?: string;
            main_issue?: { issue_text?: string };
            next_goal?: { goal_text?: string };
        };
        expect(focusIntent.version).toBe("sales_core_combination_v1");
        expect(focusIntent.main_issue?.issue_text).toContain("需求挖掘");
        expect(focusIntent.main_issue?.issue_text).toContain("价格敏感型客户");
        expect(focusIntent.next_goal?.goal_text).toContain("需求挖掘 × 价格敏感型客户");
        expect(getRecommendationMock).toHaveBeenCalledTimes(1);
        expect(getMyHistoryMock).toHaveBeenCalledWith({ page: 1, page_size: 5, scenario_type: "sales" });
    });

    it("prioritizes a core combination from the latest retry recommendation", async () => {
        const focusIntent = {
            version: "sales_retry_v1",
            source_session_id: "session-previous",
            main_issue: {
                issue_type: "需求挖掘",
                issue_text: "上次在价格敏感型客户场景中需求挖掘不足。",
                recovery_rule: "围绕价格敏感型客户先确认预算和 ROI。",
            },
            next_goal: {
                goal_type: "需求挖掘",
                goal_text: "下一轮练习需求挖掘 × 价格敏感型客户。",
                rule: "retry",
            },
        };
        getRecommendationMock.mockResolvedValueOnce({
            title: "复练需求挖掘",
            reason: "基于上次可评估销售报告。",
            action_label: "按目标再练",
            target_path: `/agents/agent-sales?persona_id=persona-price&focus_intent=${encodeURIComponent(JSON.stringify(focusIntent))}`,
            recommendation_kind: "sales_retry",
            scenario_type: "sales",
            source_session_id: "session-previous",
        });

        render(<SalesTrainingPage />);

        expect(await screen.findByRole("button", {
            name: /组合 1\s+基于上次报告推荐\s+需求挖掘\s+客户角色：价格敏感型客户/,
        })).toBeTruthy();
    });

    it("falls back to recent sales history when the recommendation has no matching focus", async () => {
        getRecommendationMock.mockResolvedValueOnce({
            title: "普通训练",
            reason: "先完成一次可评估训练。",
            action_label: "开始训练",
            target_path: "/training/sales",
            recommendation_kind: "onboarding",
            scenario_type: "sales",
        });
        getMyHistoryMock.mockResolvedValueOnce({
            sessions: [
                {
                    session_id: "history-1",
                    scenario_name: "销售对练",
                    scenario_type: "sales",
                    persona_name: "强势质疑型客户",
                    agent_name: "销售陪练",
                    start_time: "2026-04-19T10:00:00.000Z",
                    duration_seconds: 600,
                    overall_score: 72,
                    report_status: "completed",
                    report_generated_at: "2026-04-19T10:12:00.000Z",
                    status: "completed",
                    feedback_summary: "对强势质疑型客户需要更稳地回应。",
                    main_issue: {
                        issue_type: "异议处理",
                        issue_text: "面对强势质疑型客户时异议处理容易绕开关键问题。",
                        recovery_rule: "先复述质疑，再给证据。",
                    },
                    next_goal: {
                        goal_type: "异议处理",
                        goal_text: "下一轮练习异议处理 × 强势质疑型客户。",
                        rule: "retry",
                    },
                },
            ],
            total: 1,
            page: 1,
            page_size: 5,
            total_pages: 1,
        });

        render(<SalesTrainingPage />);

        expect(await screen.findByRole("button", {
            name: /组合 1\s+基于上次报告推荐\s+异议处理\s+客户角色：强势质疑型客户/,
        })).toBeTruthy();
    });

    it("uses an explicit training lobby return route instead of browser history", async () => {
        render(<SalesTrainingPage />);

        fireEvent.click(await screen.findByRole("button", { name: /返回训练大厅/ }));

        expect(pushMock).toHaveBeenCalledWith("/training");
        expect(backMock).not.toHaveBeenCalled();
    });

    it("makes missing persona combinations visibly unavailable instead of leaving inert cards", async () => {
        getSalesPersonasMock.mockResolvedValueOnce([
            {
                id: "persona-price",
                name: "价格敏感型",
                description: "重点关注价格和 ROI。",
                characteristics: ["价格敏感型客户"],
                difficulty: "hard",
            },
        ]);

        render(<SalesTrainingPage />);

        expect((await screen.findAllByText("管理员尚未配置「冷淡型客户」角色")).length).toBeGreaterThan(0);

        fireEvent.click(screen.getByRole("button", { name: /组合 1\s+破冰建立信任\s+客户角色：冷淡型客户/ }));

        expect(pushMock).not.toHaveBeenCalled();
    });

    it("separates partial API failure from real empty counts on the sales entry", async () => {
        getSalesAgentsMock.mockRejectedValueOnce(new Error("agents unavailable"));

        render(<SalesTrainingPage />);

        expect(await screen.findByText("部分数据加载失败（智能体），请重试。")).toBeTruthy();
        expect(screen.getByText("发布中的智能体")).toBeTruthy();
        expect(screen.getByText("加载失败")).toBeTruthy();
        expect(screen.getByText("可选客户画像")).toBeTruthy();
        expect(screen.queryByText("发布中的智能体 0")).toBeNull();
    });
});
