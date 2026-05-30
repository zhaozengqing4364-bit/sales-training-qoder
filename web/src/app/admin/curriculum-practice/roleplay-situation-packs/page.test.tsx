import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RoleplaySituationPacksPage from "./page";

const {
    listRoleplaySituationPacksMock,
    getRoleplaySituationPackReferencesMock,
    resolveRoleplaySituationPackMock,
    listConfigBundleVersionsMock,
    createConfigBundleDraftMock,
    validateConfigBundleMock,
    previewConfigBundleMock,
    publishConfigBundleMock,
    rollbackConfigBundleMock,
    disableConfigBundleMock,
} = vi.hoisted(() => ({
    listRoleplaySituationPacksMock: vi.fn(),
    getRoleplaySituationPackReferencesMock: vi.fn(),
    resolveRoleplaySituationPackMock: vi.fn(),
    listConfigBundleVersionsMock: vi.fn(),
    createConfigBundleDraftMock: vi.fn(),
    validateConfigBundleMock: vi.fn(),
    previewConfigBundleMock: vi.fn(),
    publishConfigBundleMock: vi.fn(),
    rollbackConfigBundleMock: vi.fn(),
    disableConfigBundleMock: vi.fn(),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                listRoleplaySituationPacks: listRoleplaySituationPacksMock,
                getRoleplaySituationPackReferences: getRoleplaySituationPackReferencesMock,
                resolveRoleplaySituationPack: resolveRoleplaySituationPackMock,
                listConfigBundleVersions: listConfigBundleVersionsMock,
                createConfigBundleDraft: createConfigBundleDraftMock,
                validateConfigBundle: validateConfigBundleMock,
                previewConfigBundle: previewConfigBundleMock,
                publishConfigBundle: publishConfigBundleMock,
                rollbackConfigBundle: rollbackConfigBundleMock,
                disableConfigBundle: disableConfigBundleMock,
            },
        },
    };
});

vi.mock("@/lib/debug", () => ({
    debug: {
        warn: vi.fn(),
    },
}));

const firstVisitPack = {
    code: "first_visit",
    label: "首次拜访",
    version: "v1",
    status: "published",
    initial_stage_hint: "opening",
    default_relationship_context: {
        prior_interactions: "none",
        has_prior_meeting: false,
        meeting_history_summary: null,
    },
    default_visible_information_scope: {
        initial_visible_keys: ["industry", "company_profile"],
        conditionally_visible_keys: ["hidden_information"],
        hidden_by_default_keys: ["hidden_information"],
    },
    default_forbidden_claim_patterns: ["上次拜访"],
    default_forbidden_topic_codes: ["contract_closing"],
    default_forbidden_stage_codes: ["price_negotiation"],
    stage_transition_notes: [],
    default_conflict_response_strategy: "customer_confused_correction",
    default_behavior_rules_for_prompt_only: [],
    default_runtime_violation_policy: {
        relationship_history_contradiction: "cancel_or_regenerate_once",
        hidden_information_leak: "cancel_or_regenerate_once",
        forbidden_topic: "mark_and_continue",
        persona_style_drift: "mark_for_report",
    },
    default_disclosure_policy: {
        default_hidden: true,
        phases: [],
        never_disclose_keys: [],
    },
    compatible_practice_modes: ["customer_roleplay"],
    compatible_scenario_types: ["sales"],
};

const ruleset = {
    version: "roleplay_situation_packs_v1",
    enabled: true,
    packs: [firstVisitPack],
};

const packListResponse = {
    items: [
        {
            code: "first_visit",
            label: "首次拜访",
            version: "v1",
            status: "published",
            initial_stage_hint: "opening",
            relationship_context_defaults: firstVisitPack.default_relationship_context,
            default_visible_information_scope: firstVisitPack.default_visible_information_scope,
            default_forbidden_claim_patterns: firstVisitPack.default_forbidden_claim_patterns,
            default_forbidden_topic_codes: firstVisitPack.default_forbidden_topic_codes,
            default_forbidden_stage_codes: firstVisitPack.default_forbidden_stage_codes,
            stage_transition_notes: [],
            default_conflict_response_strategy: "customer_confused_correction",
            default_behavior_rules_for_prompt_only: [],
            default_runtime_violation_policy: firstVisitPack.default_runtime_violation_policy,
            default_disclosure_policy: firstVisitPack.default_disclosure_policy,
            compatible_practice_modes: ["customer_roleplay"],
            compatible_scenario_types: ["sales"],
            audit: {},
        },
    ],
    total: 1,
    config_key: "roleplay.situation_packs.ruleset",
    management: {
        read_path: "SituationPackRepository.from_database",
    },
};

const versionsResponse = {
    items: [
        {
            version_id: "cfgv-draft",
            source_config_id: "cfg-draft",
            bundle_key: "roleplay.situation_packs.ruleset",
            version_number: 2,
            version_label: "roleplay_situation_packs_v1",
            status: "draft",
            snapshot: ruleset,
            created_at: "2026-05-26T10:00:00",
            updated_at: "2026-05-26T10:00:00",
        },
        {
            version_id: "cfgv-published",
            source_config_id: "cfg-published",
            bundle_key: "roleplay.situation_packs.ruleset",
            version_number: 1,
            version_label: "roleplay_situation_packs_v1",
            status: "published",
            snapshot: ruleset,
            created_at: "2026-05-25T10:00:00",
            updated_at: "2026-05-25T10:00:00",
        },
    ],
};

describe("RoleplaySituationPacksPage", () => {
    beforeEach(() => {
        listRoleplaySituationPacksMock.mockResolvedValue(packListResponse);
        listConfigBundleVersionsMock.mockResolvedValue(versionsResponse);
        getRoleplaySituationPackReferencesMock.mockResolvedValue({
            practice_templates: [
                {
                    asset_type: "practice_template",
                    asset_id: "template-1",
                    name: "首次拜访模板",
                    status: "published",
                    version: 1,
                },
            ],
            case_items: [],
            personas: [],
            total: 1,
        });
        resolveRoleplaySituationPackMock.mockResolvedValue({
            pack: {
                code: "first_visit",
                label: "首次拜访",
                version: "v1",
                status: "published",
                relationship_context: firstVisitPack.default_relationship_context,
                visible_information_scope: firstVisitPack.default_visible_information_scope,
                forbidden_claim_patterns: firstVisitPack.default_forbidden_claim_patterns,
                forbidden_topic_codes: firstVisitPack.default_forbidden_topic_codes,
                forbidden_stage_codes: firstVisitPack.default_forbidden_stage_codes,
                runtime_violation_policy: firstVisitPack.default_runtime_violation_policy,
                compatible_practice_modes: ["customer_roleplay"],
                compatible_scenario_types: ["sales"],
            },
            metadata: {
                config_key: "roleplay.situation_packs.ruleset",
                read_path: "SituationPackRepository.from_database",
                ruleset_version: "roleplay_situation_packs_v1",
                source: "published",
                config_id: "cfg-published",
                config_version: 1,
                resolved_at: "2026-05-27T10:00:00+00:00",
            },
        });
        createConfigBundleDraftMock.mockReset();
        validateConfigBundleMock.mockReset();
        previewConfigBundleMock.mockReset();
        publishConfigBundleMock.mockReset();
        rollbackConfigBundleMock.mockReset();
        disableConfigBundleMock.mockReset();
    });

    it("renders situation pack list, structured detail, references, and version status", async () => {
        render(<RoleplaySituationPacksPage />);

        expect(await screen.findByRole("heading", { name: "角色情景包" })).toBeTruthy();
        expect(screen.getAllByText("首次拜访").length).toBeGreaterThan(0);
        expect(screen.getByText("Relationship defaults")).toBeTruthy();
        expect(screen.getByText("Initial visible keys")).toBeTruthy();
        expect(await screen.findByText("首次拜访模板")).toBeTruthy();
        expect(await screen.findByText("已发布 canonical 解析")).toBeTruthy();
        expect(await screen.findByText(/read_path: SituationPackRepository\.from_database/)).toBeTruthy();
        expect(resolveRoleplaySituationPackMock).toHaveBeenCalledWith("first_visit");
        expect(screen.getByText("Draft Version")).toBeTruthy();
    });

    it("requires an audit reason before publishing a draft", async () => {
        render(<RoleplaySituationPacksPage />);

        await screen.findByRole("button", { name: /发布 draft/ });
        fireEvent.click(screen.getByRole("button", { name: /发布 draft/ }));

        expect(await screen.findByText(/必须填写操作原因/)).toBeTruthy();
        expect(publishConfigBundleMock).not.toHaveBeenCalled();
    });

    it("shows backend validation errors without publishing", async () => {
        validateConfigBundleMock.mockResolvedValue({
            valid: false,
            errors: [{ field: "packs[0].default_visible_information_scope", message: "hidden keys cannot be initially visible" }],
            audit: { audit_id: "audit-validate" },
        });

        render(<RoleplaySituationPacksPage />);

        fireEvent.click(await screen.findByRole("button", { name: "后端校验" }));

        await waitFor(() => {
            expect(validateConfigBundleMock).toHaveBeenCalled();
        });
        expect(await screen.findByText(/hidden keys cannot be initially visible/)).toBeTruthy();
        expect(publishConfigBundleMock).not.toHaveBeenCalled();
    });
});
