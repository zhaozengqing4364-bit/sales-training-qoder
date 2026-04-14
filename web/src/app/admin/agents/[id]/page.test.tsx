import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
    errorToastMock,
    getAgentMock,
    getAgentPersonasMock,
    getPersonasMock,
    getModelConfigsMock,
    getVoiceRuntimeProfilesMock,
    getAgentVoicePolicyMock,
    getAgentIndustryPackContractMock,
} = vi.hoisted(() => ({
    errorToastMock: vi.fn(),
    getAgentMock: vi.fn(),
    getAgentPersonasMock: vi.fn(),
    getPersonasMock: vi.fn(),
    getModelConfigsMock: vi.fn(),
    getVoiceRuntimeProfilesMock: vi.fn(),
    getAgentVoicePolicyMock: vi.fn(),
    getAgentIndustryPackContractMock: vi.fn(),
}));

vi.mock("react", async () => {
    const actual = await vi.importActual<typeof import("react")>("react");
    return {
        ...actual,
        use: (value: unknown) => {
            if (value && typeof value === "object" && "then" in (value as Promise<unknown>)) {
                return { id: "agent-1" };
            }
            return (actual as typeof import("react")).use(value as never);
        },
    };
});

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        back: vi.fn(),
        push: vi.fn(),
    }),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        error: errorToastMock,
        success: vi.fn(),
        showToast: vi.fn(),
    }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getAgent: getAgentMock,
                getAgentPersonas: getAgentPersonasMock,
                getPersonas: getPersonasMock,
                getModelConfigs: getModelConfigsMock,
                getVoiceRuntimeProfiles: getVoiceRuntimeProfilesMock,
                getAgentVoicePolicy: getAgentVoicePolicyMock,
                getAgentIndustryPackContract: getAgentIndustryPackContractMock,
            },
        },
    };
});

import AgentEditPage from "./page";

describe("AgentEditPage", () => {
    beforeEach(() => {
        errorToastMock.mockReset();
        getAgentMock.mockReset();
        getAgentPersonasMock.mockReset();
        getPersonasMock.mockReset();
        getModelConfigsMock.mockReset();
        getVoiceRuntimeProfilesMock.mockReset();
        getAgentVoicePolicyMock.mockReset();
        getAgentIndustryPackContractMock.mockReset();

        getAgentMock.mockResolvedValue({
            id: "agent-1",
            name: "销售教练",
            description: "用于验证 agent runtime contract。",
            category: "sales",
            status: "published",
            created_at: "2026-03-24T00:00:00Z",
            updated_at: "2026-03-24T00:00:00Z",
            capabilities_config: {},
        });
        getAgentPersonasMock.mockResolvedValue([]);
        getPersonasMock.mockResolvedValue({ items: [] });
        getModelConfigsMock.mockResolvedValue({ llm: [], embedding: [], asr: [], tts: [], total: 0 });
        getVoiceRuntimeProfilesMock.mockResolvedValue({ items: [] });
        getAgentVoicePolicyMock.mockResolvedValue({ enabled: true, runtime_profile_id: null, voice_mode_override: null });
        getAgentIndustryPackContractMock.mockResolvedValue({
            contract_version: 1,
            industry_pack: {
                authority_model: "composed_from_existing_admin_surfaces",
                summary: "Industry pack is composed from existing agent/persona/knowledge/scenario surfaces.",
            },
            runtime_authorities: [
                "sales_bot.services.voice_runtime_policy.resolve_effective_policy",
                "practice_sessions.voice_policy_snapshot",
            ],
            observability_surfaces: [
                "/api/v1/admin/personas/policy-health",
                "practice_sessions.voice_policy_snapshot",
            ],
            composition_rules: [
                "Agent owns runtime shell and capability defaults, not customer-pressure semantics.",
            ],
        });
    });

    it("renders the industry-pack runtime contract so admins can see agent/runtime boundaries", async () => {
        render(<AgentEditPage params={Promise.resolve({ id: "agent-1" })} />);

        expect(await screen.findByText("Industry Pack 运行合同")).toBeTruthy();
        expect(screen.getByText("智能体继续只负责 runtime shell；行业包语义仍由 persona / knowledge / scenario surfaces 组合。")).toBeTruthy();
        expect(screen.getByText("sales_bot.services.voice_runtime_policy.resolve_effective_policy")).toBeTruthy();
        expect(screen.getByText("practice_sessions.voice_policy_snapshot")).toBeTruthy();
        expect(screen.getByText("Agent owns runtime shell and capability defaults, not customer-pressure semantics.")).toBeTruthy();
    });
});
