import { describe, expect, it } from "vitest";

import type { AssetRefPickerOption } from "@/components/admin/asset-ref-picker";
import { validateTemplateFormPreflight } from "@/lib/admin/template-form-preflight";

const publishedOption = (id: string, label: string): AssetRefPickerOption => ({
    id,
    label,
    status: "published",
    editHref: "/admin",
    selectable: true,
});

describe("validateTemplateFormPreflight", () => {
    const context = {
        agentOptions: [publishedOption("agent-1", "Agent A")],
        personaOptions: [publishedOption("persona-1", "Persona A")],
        runtimeOptions: [publishedOption("runtime-1", "Runtime A")],
        scoringOptions: [publishedOption("ruleset-1", "Ruleset A")],
        situationPackOptions: [publishedOption("first_visit", "首次拜访")],
        knowledgeBases: [{ id: "kb-1", name: "KB", status: "active" } as never],
    };

    it("returns no errors for a valid minimal form", () => {
        const result = validateTemplateFormPreflight(
            {
                name: "模板",
                agent_id: "agent-1",
                persona_id: "persona-1",
                runtime_profile_id: "runtime-1",
                scoring_ruleset_id: "ruleset-1",
                knowledge_base_refs: ["kb-1"],
                voice_mode: "stepfun_realtime",
                mode: "customer_roleplay",
                situation_pack_code: "first_visit",
            },
            context,
        );
        expect(result.errors).toEqual([]);
        expect(result.fieldErrors).toEqual({});
    });

    it("flags unpublished agent selections", () => {
        const result = validateTemplateFormPreflight(
            {
                name: "模板",
                agent_id: "agent-draft",
                persona_id: "persona-1",
                runtime_profile_id: "runtime-1",
                scoring_ruleset_id: "ruleset-1",
                knowledge_base_refs: [],
                voice_mode: "stepfun_realtime",
            },
            {
                ...context,
                agentOptions: [{
                    ...publishedOption("agent-draft", "Draft Agent"),
                    selectable: false,
                    status: "draft",
                }],
            },
        );
        expect(result.errors.some((item) => item.includes("智能体尚未发布"))).toBe(true);
        expect(result.fieldErrors.agent_id).toContain("智能体尚未发布");
    });

    it("flags unpublished optional case item selections", () => {
        const result = validateTemplateFormPreflight(
            {
                name: "模板",
                agent_id: "agent-1",
                persona_id: "persona-1",
                runtime_profile_id: "runtime-1",
                scoring_ruleset_id: "ruleset-1",
                knowledge_base_refs: [],
                voice_mode: "stepfun_realtime",
                case_item_id: "case-draft",
            },
            {
                ...context,
                caseOptions: [{
                    ...publishedOption("case-draft", "Draft Case"),
                    selectable: false,
                    status: "draft",
                }],
            },
        );
        expect(result.fieldErrors.case_item_id).toContain("训练案例尚未发布");
    });

    it("requires a published Situation Pack for customer roleplay templates", () => {
        const result = validateTemplateFormPreflight(
            {
                name: "模板",
                agent_id: "agent-1",
                persona_id: "persona-1",
                runtime_profile_id: "runtime-1",
                scoring_ruleset_id: "ruleset-1",
                knowledge_base_refs: [],
                voice_mode: "stepfun_realtime",
                mode: "customer_roleplay",
                situation_pack_code: "",
            },
            context,
        );
        expect(result.fieldErrors.situation_pack_code).toContain("必须选择 Situation Pack");
    });
});
