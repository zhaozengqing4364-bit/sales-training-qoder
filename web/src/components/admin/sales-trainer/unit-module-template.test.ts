import { describe, expect, it } from "vitest";

import { buildUnitTemplateForModule } from "./unit-module-template";
import type {
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
} from "@/lib/api/types";

const publishedPrompt: SalesTrainerAudioScorePrompt = {
    prompt_id: "prompt-1",
    name: "PPT 讲解评分",
    purpose: "ppt_pitch",
    system_prompt: "system",
    scoring_template: "{transcript}",
    output_schema: {},
    learner_rubric: {},
    version: 1,
    status: "published",
    created_by: "admin-1",
    updated_by: "admin-1",
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
};

const publishedMaterial: SalesTrainerMaterial = {
    material_id: "material-1",
    material_key: "company_master_deck",
    name: "公司主胶片",
    material_type: "ppt_deck",
    description: null,
    purpose: "ppt_pitch",
    status: "published",
    current_version_id: "version-1",
    current_version: {
        version_id: "version-1",
        material_id: "material-1",
        version_label: "v2026.06",
        title: "公司主胶片 2026-06",
        file_name: "deck.pptx",
        content_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size_bytes: 1024,
        storage_key: "cos://deck.pptx",
        file_hash: null,
        release_notes: null,
        status: "published",
        published_at: "2026-06-01T00:00:00Z",
        published_by: "admin-1",
        created_by: "admin-1",
        created_at: "2026-06-01T00:00:00Z",
        updated_at: "2026-06-01T00:00:00Z",
    },
    versions: [],
    created_by: "admin-1",
    updated_by: "admin-1",
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
};

describe("unit-module-template", () => {
    it("prefills the PPT explanation unit from diagnostics", () => {
        const template = buildUnitTemplateForModule({
            materials: [publishedMaterial],
            moduleKey: "ppt_explanation",
            prompts: [publishedPrompt],
        });

        expect(template).toEqual(expect.objectContaining({
            name: "第一关：PPT 讲解",
            unit_type: "audio_scoring",
        }));
        expect(template?.config.audio?.purpose).toBe("ppt_pitch");
        expect(template?.config.audio?.scoring_prompt_id).toBe("prompt-1");
        expect(template?.config.materials?.bindings?.[0]?.material_id).toBe("material-1");
        expect(template?.config.path).toEqual(expect.objectContaining({
            module_key: "ppt_explanation",
            module_type: "audio_scoring",
            order_index: 1,
            path_key: "newcomer_training_path_v1",
        }));
    });
});
