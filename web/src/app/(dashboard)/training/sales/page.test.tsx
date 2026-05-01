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
} = vi.hoisted(() => ({
    backMock: vi.fn(),
    pushMock: vi.fn(),
    getSalesAgentsMock: vi.fn(),
    listScenariosMock: vi.fn(),
    getSalesPersonasMock: vi.fn(),
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
        },
    };
});

vi.mock("@/lib/debug", () => ({
    debug: {
        warn: vi.fn(),
        log: vi.fn(),
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

describe("SalesTrainingPage", () => {
    beforeEach(() => {
        backMock.mockReset();
        pushMock.mockReset();
        getSalesAgentsMock.mockReset();
        listScenariosMock.mockReset();
        getSalesPersonasMock.mockReset();

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
    });

    it("loads the sales entry stats and published agents without the 80/20 combination module", async () => {
        render(<SalesTrainingPage />);

        expect(await screen.findByText("销售能力训练")).toBeTruthy();
        expect(screen.getByText("可用销售场景")).toBeTruthy();
        expect(screen.getByText("可选客户画像")).toBeTruthy();
        expect(screen.getByText("发布中的智能体")).toBeTruthy();
        expect(screen.getByRole("button", { name: /销售陪练选择角色开始对练/ })).toBeTruthy();

        expect(screen.queryByText("核心 10 组合（80/20）")).toBeNull();
        expect(screen.queryByText(/后台配置/)).toBeNull();
        expect(screen.queryByText(/安全兜底/)).toBeNull();
        expect(screen.queryByText(/组合 1/)).toBeNull();
    });

    it("uses an explicit training lobby return route instead of browser history", async () => {
        render(<SalesTrainingPage />);

        fireEvent.click(await screen.findByRole("button", { name: /返回训练大厅/ }));

        expect(pushMock).toHaveBeenCalledWith("/training");
        expect(backMock).not.toHaveBeenCalled();
    });

    it("opens the selected agent role page from the agent card", async () => {
        render(<SalesTrainingPage />);

        fireEvent.click(await screen.findByRole("button", { name: /销售陪练选择角色开始对练/ }));

        expect(pushMock).toHaveBeenCalledWith("/agents/agent-sales");
    });

    it("separates partial API failure from real empty counts on the sales entry", async () => {
        getSalesAgentsMock.mockRejectedValueOnce(new Error("agents unavailable"));

        render(<SalesTrainingPage />);

        expect(await screen.findByText("部分数据加载失败（智能体），请重试。")).toBeTruthy();
        expect(screen.getByText("发布中的智能体")).toBeTruthy();
        expect(screen.getByText("加载失败")).toBeTruthy();
        expect(screen.getByText("可选客户画像")).toBeTruthy();
        expect(screen.queryByText("发布中的智能体 0")).toBeNull();
        expect(screen.queryByText("核心 10 组合（80/20）")).toBeNull();
    });
});
