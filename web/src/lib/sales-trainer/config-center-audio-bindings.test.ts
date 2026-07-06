import { describe, expect, it } from "vitest";

import type {
    NewcomerPathConfigDiagnostics,
    NewcomerPathConfigResponse,
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerSettings,
} from "@/lib/api/types";

import { buildNewcomerConfigCenter } from "./config-center";

function pathConfigDiagnostics(): NewcomerPathConfigDiagnostics {
    return {
        surface_key: "newcomer_training_path_v1",
        resource_type: "newcomer_training_path",
        source: "active_revision",
        legacy_snapshot_only: false,
        fallback_applied: false,
        fallback_reason: null,
        realtime_provider_readiness: [],
        management_entry: "/admin/newcomer-training/path-config",
        permission_policy: {
            view: "sales_trainer.manage_modules",
            save: "sales_trainer.manage_modules",
            publish: "sales_trainer.manage_modules",
            rollback: "sales_trainer.manage_modules",
            high_risk_ai_coach: "sales_trainer.manage_prompts",
            regrade: "sales_trainer.regrade_history",
        },
        active_revision: null,
        working_revision: null,
        high_risk_actions: {
            publish: {
                requires_reason: true,
                requires_trace_id: true,
                audit_action: "newcomer_path_config.publish",
                impact_scope: "future_learners_only",
                preview_endpoint: "/api/v1/admin/newcomer-training/path-config/publish/preview",
            },
            rollback: {
                requires_reason: true,
                requires_trace_id: true,
                audit_action: "newcomer_path_config.rollback",
                impact_scope: "future_learners_only",
                preview_endpoint: "/api/v1/admin/newcomer-training/path-config/rollback/preview",
            },
            regrade: {
                requires_reason: true,
                requires_trace_id: true,
                audit_action: "historical_regrade.completed",
                impact_scope: "append_only_history",
                history_overwrite: false,
            },
        },
    };
}

function settings(): SalesTrainerSettings {
    return {
        storage_backend: "local",
        direct_upload_supported: false,
        cos_configured: false,
        cos_public_read: false,
        oss_configured: false,
        asr_mode: "mock",
        asr_model: "fun-asr",
        dashscope_configured: true,
        deucate_configured: true,
        deucate_model: "score-model",
        max_file_size_mb: 200,
        allowed_mime_types: ["audio/wav"],
        file_url_expires_seconds: 3600,
    };
}

const prompt: SalesTrainerAudioScorePrompt = {
    prompt_id: "prompt-from-path",
    name: "PPT 录音评分标准",
    purpose: "ppt_pitch",
    system_prompt: "system",
    scoring_template: "{transcript}",
    output_schema: {},
    learner_rubric: {},
    version: 2,
    status: "published",
    created_by: null,
    updated_by: null,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
};

const material: SalesTrainerMaterial = {
    material_id: "material-from-path",
    material_key: "ppt-main",
    name: "PPT 标准讲解材料",
    material_type: "ppt_deck",
    description: null,
    purpose: "ppt_pitch",
    status: "published",
    current_version_id: "version-from-path",
    current_version: {
        version_id: "version-from-path",
        material_id: "material-from-path",
        version_label: "v2",
        title: "PPT 标准讲解材料 v2",
        file_name: "ppt-v2.pptx",
        content_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size_bytes: 1024,
        storage_key: "materials/ppt-v2.pptx",
        file_hash: null,
        release_notes: null,
        status: "published",
        published_at: "2026-06-01T00:00:00Z",
        published_by: "admin",
        created_by: "admin",
        created_at: "2026-06-01T00:00:00Z",
        updated_at: "2026-06-01T00:00:00Z",
    },
    versions: [],
    created_by: null,
    updated_by: null,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
};

const pathConfig: NewcomerPathConfigResponse = {
    source: "active_revision",
    fallback_reason: null,
    legacy_snapshot_only: false,
    management_entry: "/admin/newcomer-training/path-config",
    permission: "sales_trainer.manage_modules",
    path: {
        path_key: "newcomer_training_path_v1",
        title: "新人训练路径",
        goal_title: "完成新人训练",
        description: null,
        enabled: true,
        modules: [
            {
                module_key: "ppt_explanation",
                module_type: "audio_scoring",
                enabled: true,
                order_index: 1,
                title: "PPT 讲解录音",
                description: "上传 PPT 讲解录音",
                target_unit_id: "ppt-audio-unit",
                learning_content_id: null,
                exam_paper_id: null,
                material_id: "material-from-path",
                material_version_id: "version-from-path",
                scoring_prompt_id: "prompt-from-path",
                disabled_reason: null,
                unlock_after_unit_ids: [],
                completion_rule: "scored",
                primary_action_label: "上传录音",
                retry_action_label: null,
                review_action_label: null,
                guidance_templates: {},
            },
        ],
    },
    active_revision_id: "path-revision-1",
    active_revision_no: 1,
    working_revision_id: null,
    working_revision_no: null,
    has_unpublished_revision: false,
    diagnostics: pathConfigDiagnostics(),
};

describe("buildNewcomerConfigCenter audio path bindings", () => {
    it("uses path module material and scoring prompt refs before legacy unit config", () => {
        const center = buildNewcomerConfigCenter({
            units: [],
            articles: [],
            papers: [],
            materials: [material],
            scorePrompts: [prompt],
            settings: settings(),
            boundArticle: null,
            pathConfig,
        });

        const pptModule = center.modules.find((item) => item.moduleKey === "ppt_explanation");

        expect(pptModule?.status).toBe("ready");
        expect(pptModule?.issues).toEqual([]);
        expect(pptModule?.bindings).toContain("评分标准：PPT 录音评分标准 v2");
        expect(pptModule?.bindings).toContain("材料：PPT 标准讲解材料（v2）");
    });
});
