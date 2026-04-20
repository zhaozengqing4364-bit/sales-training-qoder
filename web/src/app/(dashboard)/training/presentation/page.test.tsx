import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PresentationTrainingPage from "./page";

const {
    pushMock,
    backMock,
    getPresentationAgentsMock,
    listPresentationsMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    backMock: vi.fn(),
    getPresentationAgentsMock: vi.fn(),
    listPresentationsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
        back: backMock,
    }),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button {...props}>{children}</button>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
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
            agents: {
                ...actual.api.agents,
                getList: getPresentationAgentsMock,
            },
            presentations: {
                ...actual.api.presentations,
                list: listPresentationsMock,
            },
        },
    };
});

vi.mock("@/lib/debug", () => ({
    debug: {
        error: vi.fn(),
    },
}));

describe("PresentationTrainingPage entry states", () => {
    beforeEach(() => {
        pushMock.mockReset();
        backMock.mockReset();
        getPresentationAgentsMock.mockReset();
        listPresentationsMock.mockReset();

        getPresentationAgentsMock.mockResolvedValue([
            {
                id: "presentation-agent-1",
                name: "演讲教练",
                description: "演讲训练",
                category: "presentation",
                status: "published",
                role: "演讲教练",
                difficulty: "medium",
            },
        ]);
        listPresentationsMock.mockResolvedValue([]);
    });

    it("uses an explicit training lobby return route instead of browser history", async () => {
        render(<PresentationTrainingPage />);

        fireEvent.click(await screen.findByRole("button", { name: /返回训练大厅/ }));

        expect(pushMock).toHaveBeenCalledWith("/training");
        expect(backMock).not.toHaveBeenCalled();
    });

    it("separates partial presentation data failure from a genuinely empty training entry", async () => {
        getPresentationAgentsMock.mockRejectedValueOnce(new Error("agents unavailable"));
        listPresentationsMock.mockResolvedValueOnce([
            {
                id: "deck-1",
                title: "客户方案汇报",
                status: "ready",
            },
        ]);

        render(<PresentationTrainingPage />);

        expect(await screen.findByText("部分演讲训练数据加载失败（演讲智能体），请重试。")).toBeTruthy();
        expect(screen.getByText("可用 PPT：1 份")).toBeTruthy();
        expect(screen.getByText("当前没有发布中的演讲智能体。为保证角色稳定与策略生效，请先配置“智能体 + 角色”后再开始演练。")).toBeTruthy();
        expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
    });
});
