import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgentPersonaSelectPage from "./page";

const {
    backMock,
    pushMock,
    getAgentWithPersonasMock,
    listPresentationsMock,
    createSessionMock,
} = vi.hoisted(() => ({
    backMock: vi.fn(),
    pushMock: vi.fn(),
    getAgentWithPersonasMock: vi.fn(),
    listPresentationsMock: vi.fn(),
    createSessionMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ agentId: "agent-1" }),
    useRouter: () => ({
        back: backMock,
        push: pushMock,
    }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            agents: {
                ...actual.api.agents,
                getAgentWithPersonas: getAgentWithPersonasMock,
            },
            presentations: {
                ...actual.api.presentations,
                list: listPresentationsMock,
            },
            practice: {
                ...actual.api.practice,
                createSession: createSessionMock,
            },
        },
    };
});

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
}));

describe("AgentPersonaSelectPage", () => {
    beforeEach(() => {
        backMock.mockReset();
        pushMock.mockReset();
        getAgentWithPersonasMock.mockReset();
        listPresentationsMock.mockReset();
        createSessionMock.mockReset();

        getAgentWithPersonasMock.mockResolvedValue({
            id: "agent-1",
            name: "标准路演教练",
            description: "帮助学员练习标准PPT。",
            category: "presentation",
            personas: [
                {
                    id: "persona-1",
                    name: "评委",
                    description: "关注结构与表达",
                    difficulty: "medium",
                    is_default: true,
                },
            ],
        });

        listPresentationsMock.mockResolvedValue([
            {
                presentation_id: "ppt-1",
                title: "石犀标准路演",
                status: "ready",
                version_number: 3,
                page_count: 6,
                total_pages: 6,
            },
            {
                presentation_id: "ppt-2",
                title: "替换中的标准模板",
                status: "processing",
                version_number: 4,
                page_count: 8,
                total_pages: 8,
            },
        ]);

        createSessionMock.mockResolvedValue({ session_id: "session-123" });
    });

    it("shows current version and material status for presentation options", async () => {
        render(<AgentPersonaSelectPage />);

        await screen.findByText("标准路演教练");

        expect(listPresentationsMock).toHaveBeenCalledWith({ limit: 100 });
        expect(await screen.findByRole("option", { name: /石犀标准路演（v3 · 可用 · 6 页）/i })).toBeTruthy();
        expect(await screen.findByRole("option", { name: /替换中的标准模板（v4 · 处理中 · 8 页）/i })).toBeTruthy();
        expect(screen.getByText(/当前版本：v3/i)).toBeTruthy();
        expect(screen.getByText(/材料状态：可用/i)).toBeTruthy();
    });

    it("creates the next session with the same stable presentation_id while showing version info", async () => {
        render(<AgentPersonaSelectPage />);

        await screen.findByText("标准路演教练");
        await screen.findByText(/当前版本：v3/i);

        fireEvent.click(screen.getByRole("button", { name: /开始对练/i }));

        await waitFor(() => {
            expect(createSessionMock).toHaveBeenCalledTimes(1);
        });
        expect(createSessionMock).toHaveBeenCalledWith({
            agent_id: "agent-1",
            persona_id: "persona-1",
            scenario_type: "presentation",
            presentation_id: "ppt-1",
            voice_mode: "stepfun_realtime",
        });
        expect(pushMock).toHaveBeenCalledWith(
            "/practice/session-123?agent_id=agent-1&persona_id=persona-1&scenario_type=presentation&voice_mode=stepfun_realtime&presentation_id=ppt-1",
        );
    });
});
