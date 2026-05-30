import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TemplateForm } from "@/components/admin/curriculum-practice/template-form";

const listCaseItemsMock = vi.hoisted(() => vi.fn());
const listRoleProfilesMock = vi.hoisted(() => vi.fn());
const getAgentsMock = vi.hoisted(() => vi.fn());
const getPersonasMock = vi.hoisted(() => vi.fn());
const getVoiceRuntimeProfilesMock = vi.hoisted(() => vi.fn());
const listScoringRulesetsMock = vi.hoisted(() => vi.fn());
const listRoleplaySituationPacksMock = vi.hoisted(() => vi.fn());
const getKnowledgeBasesMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                listCaseItems: listCaseItemsMock,
                listRoleProfiles: listRoleProfilesMock,
                getAgents: getAgentsMock,
                getPersonas: getPersonasMock,
                getVoiceRuntimeProfiles: getVoiceRuntimeProfilesMock,
                listScoringRulesets: listScoringRulesetsMock,
                listRoleplaySituationPacks: listRoleplaySituationPacksMock,
                getKnowledgeBases: getKnowledgeBasesMock,
            },
        },
    };
});

vi.mock("@/lib/debug", () => ({ debug: { warn: vi.fn() } }));

const template = {
    template_id: "template-1",
    name: "客户异议处理训练",
    description: "最小模板",
    scenario_type: "sales",
    mode: "customer_roleplay",
    agent_id: "agent-1",
    persona_id: "persona-1",
    runtime_profile_id: "runtime-1",
    voice_mode: "stepfun_realtime",
    scoring_ruleset_id: "ruleset-1",
    knowledge_base_refs: ["kb-1"],
    status: "draft",
    version: 1,
    content_hash: null,
    published_at: null,
    created_at: "2026-05-12T00:00:00Z",
    updated_at: "2026-05-12T00:00:00Z",
    case_item_id: "case-1",
    role_profile_id: "role-1",
    situation_pack_code: "first_visit",
};

const publishedCaseItem = {
    case_item_id: "case-1",
    industry: "制造业",
    customer_role: "采购总监",
    company_profile: "大型制造客户",
    pain_points: ["成本高"],
    objections: ["预算不足"],
    hidden_information: "竞品报价",
    success_criteria: ["试点"],
    allowed_disclosure_policy: { phases: ["discovery"] },
    content_hash: "sha256:case",
    status: "published",
    version: 1,
    published_at: "2026-05-12T00:00:00Z",
    created_at: "2026-05-12T00:00:00Z",
    updated_at: "2026-05-12T00:00:00Z",
};

const publishedRoleProfile = {
    role_profile_id: "role-1",
    role_type: "customer" as const,
    role_name: "谨慎采购总监",
    persona_ref: "persona-1",
    communication_style: "谨慎",
    pressure_level: "high" as const,
    knowledge_boundary: ["价格"],
    behavior_rules: ["追问 ROI"],
    voice_style_hint: "低沉",
    content_hash: "sha256:role",
    status: "published",
    version: 1,
    published_at: "2026-05-12T00:00:00Z",
    created_at: "2026-05-12T00:00:00Z",
    updated_at: "2026-05-12T00:00:00Z",
};

const pickerAssets = {
    agents: [{ id: "agent-1", name: "默认智能体", category: "sales", status: "published" }],
    personas: [{ id: "persona-1", name: "默认 Persona", category: "customer", status: "active" }],
    runtimeProfiles: [{ id: "runtime-1", name: "默认语音", is_active: true, voice_mode: "stepfun_realtime" }],
    scoringRulesets: [{ ruleset_id: "ruleset-1", display_name: "默认评分", version: "v1", status: "published" }],
    situationPacks: [{
        code: "first_visit",
        label: "首次拜访",
        version: "v1",
        status: "published",
        compatible_practice_modes: ["customer_roleplay"],
        compatible_scenario_types: ["sales"],
        relationship_context_defaults: {},
        default_visible_information_scope: {},
        default_forbidden_claim_patterns: [],
        default_forbidden_topic_codes: [],
        default_forbidden_stage_codes: [],
        default_runtime_violation_policy: {},
    }],
    knowledgeBases: [{ id: "kb-1", name: "知识库 A", status: "active", document_count: 2 }],
};

function pickAssetRef(label: string, optionText: string) {
    const input = screen.getByLabelText(label);
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: optionText } });
    const option = screen.getAllByRole("button").find((button) => button.textContent?.includes(optionText));
    if (!option) throw new Error(`Picker option not found for ${label}: ${optionText}`);
    fireEvent.click(option);
}

describe("TemplateForm", () => {
    beforeEach(() => {
        listCaseItemsMock.mockResolvedValue({
            items: [
                publishedCaseItem,
                { ...publishedCaseItem, case_item_id: "case-2", customer_role: "运营总监" },
            ],
            total: 2,
        });
        listRoleProfilesMock.mockResolvedValue({ items: [publishedRoleProfile], total: 1 });
        getAgentsMock.mockResolvedValue({ items: pickerAssets.agents, total: pickerAssets.agents.length });
        getPersonasMock.mockResolvedValue({ items: pickerAssets.personas, total: pickerAssets.personas.length });
        getVoiceRuntimeProfilesMock.mockResolvedValue({ items: pickerAssets.runtimeProfiles });
        listScoringRulesetsMock.mockResolvedValue({ items: pickerAssets.scoringRulesets, total: pickerAssets.scoringRulesets.length });
        listRoleplaySituationPacksMock.mockResolvedValue({ items: pickerAssets.situationPacks, total: pickerAssets.situationPacks.length });
        getKnowledgeBasesMock.mockResolvedValue({ items: pickerAssets.knowledgeBases, total: pickerAssets.knowledgeBases.length });
    });

    it("shows republish banner when case or role binding changes", async () => {
        render(
            <TemplateForm
                mode="edit"
                templateId="template-1"
                initialTemplate={template}
                onSaved={vi.fn()}
                onCancel={vi.fn()}
            />,
        );

        await screen.findByRole("heading", { name: "编辑模板" });
        expect(screen.queryByText(/引用资产已变更/)).toBeNull();

        pickAssetRef("训练案例（可选）", "运营总监");

        await waitFor(() => {
            expect(screen.getByText(/引用资产已变更/)).toBeTruthy();
        });
    });
});
