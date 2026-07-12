import { describe, expect, it } from "vitest";

import type { TrainingPathPayload } from "@/lib/api/types/newcomer-training";

import { duplicateModule, moveModule } from "./editor-state";

function pathPayload(): TrainingPathPayload {
    return {
        schema_version: "newcomer_training_orchestration_v1",
        title: "新人训练",
        description: null,
        phases: [{
            phase_id: "phase-product",
            title: "产品能力",
            description: null,
            outcome: null,
            order_index: 1,
            required: true,
            modules: [{
                module_id: "module-product-a",
                title: "产品 A",
                description: null,
                outcome: null,
                order_index: 1,
                required: true,
                estimated_minutes: null,
                audience_rule: { learner_levels: [], roles: [], departments: [] },
                prerequisites: [],
                completion_policy: { mode: "all_required", activity_ids: [], count: null },
                activities: [
                    {
                        activity_id: "activity-product-a-lesson",
                        type: "lesson",
                        title: "学习",
                        description: null,
                        objective: null,
                        why_it_matters: null,
                        steps: [],
                        success_criteria: [],
                        primary_action_label: null,
                        order_index: 1,
                        required: true,
                        estimated_minutes: null,
                        prerequisites: [],
                        config: { learning_content_id: "content-a", completion_mode: "all_chapters" },
                    },
                    {
                        activity_id: "activity-product-a-quiz",
                        type: "quiz",
                        title: "考试",
                        description: null,
                        objective: null,
                        why_it_matters: null,
                        steps: [],
                        success_criteria: [],
                        primary_action_label: null,
                        order_index: 2,
                        required: true,
                        estimated_minutes: null,
                        prerequisites: [],
                        config: { exam_paper_id: "paper-a", pass_score: 80, max_attempts: null },
                    },
                    {
                        activity_id: "activity-product-a-audio",
                        type: "audio_assessment",
                        title: "讲解",
                        description: null,
                        objective: null,
                        why_it_matters: null,
                        steps: [],
                        success_criteria: [],
                        primary_action_label: null,
                        order_index: 3,
                        required: true,
                        estimated_minutes: null,
                        prerequisites: [],
                        config: {
                            scoring_rubric_id: "rubric-a",
                            material_id: null,
                            pass_score: 80,
                            max_attempts: null,
                        },
                    },
                ],
            }],
        }],
    };
}

describe("newcomer training editor state", () => {
    it("duplicates a product module with new stable IDs and unchanged activity types", () => {
        let sequence = 0;
        const next = duplicateModule(pathPayload(), "module-product-a", () => `new-${++sequence}`);
        const modules = next.phases[0].modules;

        expect(modules).toHaveLength(2);
        expect(modules[1].module_id).not.toBe(modules[0].module_id);
        expect(modules[1].activities.map((item) => item.type)).toEqual([
            "lesson",
            "quiz",
            "audio_assessment",
        ]);
        expect(new Set(modules.flatMap((item) => item.activities.map((activity) => activity.activity_id))).size).toBe(6);
    });

    it("reorders siblings and normalizes order indexes", () => {
        const source = pathPayload();
        const base = source.phases[0].modules[0];
        source.phases[0].modules = [
            { ...base, module_id: "module-a", order_index: 1 },
            { ...base, module_id: "module-b", order_index: 2 },
            { ...base, module_id: "module-c", order_index: 3 },
        ];

        const next = moveModule(source, "module-c", "before", "module-a");

        expect(next.phases[0].modules.map((item) => [item.module_id, item.order_index])).toEqual([
            ["module-c", 1],
            ["module-a", 2],
            ["module-b", 3],
        ]);
    });
});
