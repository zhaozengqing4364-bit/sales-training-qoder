import { describe, expect, it } from "vitest";

import {
    buildUnitFormPayload,
    initialUnitFormModel,
} from "./unit-form-model";
import type { SalesTrainerUnit } from "@/lib/api/types";

describe("unit-form-model", () => {
    it("preserves newcomer module ownership when the form saves a diagnostic template", () => {
        const initialUnit: SalesTrainerUnit = {
            unit_id: "",
            name: "第一关：PPT 讲解录音",
            description: "确认材料后上传讲解录音。",
            unit_type: "audio_scoring",
            config: {
                audio: {
                    scoring_prompt_id: "prompt-1",
                    purpose: "ppt_pitch",
                },
                materials: {
                    bindings: [
                        {
                            material_id: "material-1",
                            required: true,
                            confirmation_required: true,
                            version_policy: "current_published",
                            display_order: 1,
                        },
                    ],
                    require_latest_confirmation: true,
                },
                path: {
                    enabled: true,
                    path_key: "newcomer_training_path_v1",
                    module_key: "ppt_explanation",
                    module_type: "audio_scoring",
                    path_title: "新人训练路径",
                    level_title: "第一关：PPT 讲解录音",
                    order_index: 1,
                    completion_rule: "scored",
                },
            },
            status: "draft",
            created_by: null,
            updated_by: null,
            created_at: "",
            updated_at: "",
            questions: [],
        };

        const model = initialUnitFormModel(initialUnit);
        const payload = buildUnitFormPayload({
            ...model,
            description: initialUnit.description ?? "",
            name: initialUnit.name,
            unitType: initialUnit.unit_type,
        });

        if (!payload.config?.path) {
            throw new Error("新人训练路径模板提交时必须包含路径配置。");
        }
        expect(payload.config.path).toEqual(expect.objectContaining({
            enabled: true,
            module_key: "ppt_explanation",
            module_type: "audio_scoring",
            path_key: "newcomer_training_path_v1",
        }));
    });
});
