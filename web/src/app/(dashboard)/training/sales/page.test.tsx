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
});
