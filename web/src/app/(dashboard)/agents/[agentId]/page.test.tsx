import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TRAINING_PREFERENCES_STORAGE_KEY } from "@/hooks/use-training-preferences";

import AgentPersonaSelectPage from "./page";

const {
    backMock,
    pushMock,
    searchParamsMock,
    getAgentWithPersonasMock,
    listPresentationsMock,
    createSessionMock,
} = vi.hoisted(() => ({
    backMock: vi.fn(),
    pushMock: vi.fn(),
    searchParamsMock: vi.fn(),
    getAgentWithPersonasMock: vi.fn(),
    listPresentationsMock: vi.fn(),
    createSessionMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ agentId: "agent-1" }),
    useSearchParams: () => searchParamsMock(),
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
        localStorage.clear();
        backMock.mockReset();
        pushMock.mockReset();
        getAgentWithPersonasMock.mockReset();
        listPresentationsMock.mockReset();
        createSessionMock.mockReset();
        searchParamsMock.mockReset();
        searchParamsMock.mockReturnValue(new URLSearchParams());

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

    it("preselects the requested sales persona and creates sessions with 80/20 focus intent", async () => {
        localStorage.setItem(TRAINING_PREFERENCES_STORAGE_KEY, JSON.stringify({
            agentId: "agent-1",
            personaId: "persona-cold",
            presentationId: null,
            voiceMode: "stepfun_realtime",
        }));
        const focusIntent = {
            version: "sales_core_combination_v1",
            source_session_id: "sales-core-combination-c7",
            main_issue: {
                issue_type: "异议处理",
                issue_text: "本轮重点练习「异议处理」在「强势质疑型客户」场景下的对话短板。",
                recovery_rule: "围绕强势质疑型客户，优先演练异议处理。",
            },
            next_goal: {
                goal_type: "异议处理",
                goal_text: "用一轮完整销售对练完成「异议处理 × 强势质疑型客户」。",
                rule: "sales_core_combination",
            },
        };
        searchParamsMock.mockReturnValue(new URLSearchParams({
            persona_id: "persona-strong",
            focus_intent: JSON.stringify(focusIntent),
        }));
        getAgentWithPersonasMock.mockResolvedValueOnce({
            id: "agent-1",
            name: "销售陪练",
            description: "帮助学员练习销售对话。",
            category: "sales",
            personas: [
                {
                    id: "persona-cold",
                    name: "冷淡型",
                    description: "回应少，需要先破冰。",
                    difficulty: "medium",
                    is_default: true,
                },
                {
                    id: "persona-strong",
                    name: "强势质疑型",
                    description: "会持续质疑 ROI 和实施风险。",
                    difficulty: "hard",
                },
            ],
        });

        render(<AgentPersonaSelectPage />);

        await screen.findByText("销售陪练");

        expect(screen.getByText("本轮训练重点已带入")).toBeTruthy();
        expect(screen.getByText(`问题焦点：${focusIntent.main_issue.issue_text}`)).toBeTruthy();
        expect(screen.getByText(`训练目标：${focusIntent.next_goal.goal_text}`)).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: /开始对练/i }));

        await waitFor(() => {
            expect(createSessionMock).toHaveBeenCalledTimes(1);
        });
        expect(createSessionMock).toHaveBeenCalledWith({
            agent_id: "agent-1",
            persona_id: "persona-strong",
            scenario_type: "sales",
            presentation_id: undefined,
            voice_mode: "stepfun_realtime",
            focus_intent: focusIntent,
        });
        expect(pushMock).toHaveBeenCalledWith(
            "/practice/session-123?agent_id=agent-1&persona_id=persona-strong&scenario_type=sales&voice_mode=stepfun_realtime",
        );
    });

    it("uses the last local training preference for non-recommended entry points", async () => {
        localStorage.setItem(TRAINING_PREFERENCES_STORAGE_KEY, JSON.stringify({
            agentId: "agent-1",
            personaId: "persona-returning",
            presentationId: null,
            voiceMode: "legacy",
        }));
        getAgentWithPersonasMock.mockResolvedValueOnce({
            id: "agent-1",
            name: "销售陪练",
            description: "帮助学员练习销售对话。",
            category: "sales",
            personas: [
                {
                    id: "persona-default",
                    name: "默认角色",
                    description: "默认入口角色。",
                    difficulty: "medium",
                    is_default: true,
                },
                {
                    id: "persona-returning",
                    name: "上次角色",
                    description: "上次选择的对练角色。",
                    difficulty: "hard",
                },
            ],
        });

        render(<AgentPersonaSelectPage />);

        await screen.findByText("销售陪练");
        fireEvent.click(screen.getByRole("button", { name: /开始对练/i }));

        await waitFor(() => {
            expect(createSessionMock).toHaveBeenCalledTimes(1);
        });
        expect(createSessionMock).toHaveBeenCalledWith({
            agent_id: "agent-1",
            persona_id: "persona-returning",
            scenario_type: "sales",
            presentation_id: undefined,
            voice_mode: "legacy",
            focus_intent: undefined,
        });
        expect(pushMock).toHaveBeenCalledWith(
            "/practice/session-123?agent_id=agent-1&persona_id=persona-returning&scenario_type=sales&voice_mode=legacy",
        );
    });

    it("saves the latest voice, persona, agent, and presentation choices locally", async () => {
        render(<AgentPersonaSelectPage />);

        await screen.findByText("标准路演教练");
        await screen.findByText(/当前版本：v3/i);

        fireEvent.click(screen.getByRole("button", { name: /经典模式/i }));
        fireEvent.click(screen.getByRole("button", { name: /开始对练/i }));

        await waitFor(() => {
            expect(createSessionMock).toHaveBeenCalledTimes(1);
        });
        expect(JSON.parse(localStorage.getItem(TRAINING_PREFERENCES_STORAGE_KEY) || "{}")).toEqual({
            agentId: "agent-1",
            personaId: "persona-1",
            presentationId: "ppt-1",
            voiceMode: "legacy",
        });
        expect(createSessionMock).toHaveBeenCalledWith({
            agent_id: "agent-1",
            persona_id: "persona-1",
            scenario_type: "presentation",
            presentation_id: "ppt-1",
            voice_mode: "legacy",
        });
    });

    it("explains that both voice modes use the same sales scoring rubric", async () => {
        getAgentWithPersonasMock.mockResolvedValueOnce({
            id: "agent-sales",
            name: "销售陪练",
            description: "帮助学员练习销售对话。",
            category: "sales",
            personas: [
                {
                    id: "persona-sales",
                    name: "采购经理",
                    description: "关注 ROI 与实施风险",
                    difficulty: "medium",
                    is_default: true,
                },
            ],
        });

        render(<AgentPersonaSelectPage />);

        await screen.findByText("销售陪练");

        expect(screen.getByText(/两种模式都使用同一套销售评分维度与下一轮建议/i)).toBeTruthy();
        expect(screen.getByText(/经典模式/i)).toBeTruthy();
        expect(screen.getByText(/练中仍按同一套销售维度评分/i)).toBeTruthy();
        expect(screen.getByText(/同样输出相同的销售维度评分与建议/i)).toBeTruthy();
    });

    it("shows current version and material status for presentation options", async () => {
        render(<AgentPersonaSelectPage />);

        await screen.findByText("标准路演教练");

        await waitFor(() => {
            expect(listPresentationsMock).toHaveBeenCalledWith({ limit: 100 });
        });
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
