import { describe, expect, it } from "vitest";

import type {
    NewcomerArticle,
    NewcomerExamPaper,
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerSettings,
    SalesTrainerUnit,
} from "@/lib/api/types";

import { buildNewcomerConfigCenter } from "./config-center";
import { NEWCOMER_TRAINING_PATH_KEY } from "./module-path";

function unit(overrides: Partial<SalesTrainerUnit>): SalesTrainerUnit {
    return {
        unit_id: "unit",
        name: "训练单元",
        description: null,
        unit_type: "audio_scoring",
        config: {},
        status: "published",
        created_by: null,
        updated_by: null,
        created_at: "2026-06-01T00:00:00Z",
        updated_at: "2026-06-01T00:00:00Z",
        questions: [],
        ...overrides,
    };
}

function settings(overrides: Partial<SalesTrainerSettings> = {}): SalesTrainerSettings {
    return {
        storage_backend: "local",
        direct_upload_supported: false,
        cos_configured: false,
        cos_public_read: false,
        oss_configured: false,
        asr_mode: "mock",
        asr_model: "fun-asr",
        dashscope_configured: false,
        deucate_configured: false,
        deucate_model: null,
        max_file_size_mb: 200,
        allowed_mime_types: ["audio/wav"],
        file_url_expires_seconds: 3600,
        ...overrides,
    };
}

describe("buildNewcomerConfigCenter", () => {
    it("reports missing bindings with direct remediation entries", () => {
        const center = buildNewcomerConfigCenter({
            units: [],
            articles: [],
            papers: [],
            materials: [],
            scorePrompts: [],
            settings: settings(),
            boundArticle: null,
        });

        expect(center.modules).toHaveLength(4);
        expect(center.modules[0].status).toBe("missing");
        expect(center.modules[0].issues.map((issue) => issue.code)).toContain("module_unit_missing");
        expect(center.modules[1].issues.map((issue) => issue.code)).toEqual([
            "module_unit_missing",
            "article_missing",
            "paper_missing",
        ]);
        expect(center.modules[0].issues.find((issue) => issue.code === "module_unit_missing")?.href).toBe(
            "/admin/sales-trainer/paths?module=ppt_explanation",
        );
        expect(center.modules[1].remediationHref).toBe("/admin/sales-trainer/articles");
        expect(center.summary.ready).toBe(false);
        expect(center.summary.missingCount).toBeGreaterThan(0);
    });

    it("does not infer newcomer modules from order when module key is missing", () => {
        const ambiguousBusinessUnit = unit({
            unit_id: "ambiguous-business-unit",
            name: "第二关：商务技巧",
            unit_type: "quiz",
            config: {
                path: {
                    enabled: true,
                    path_key: NEWCOMER_TRAINING_PATH_KEY,
                    module_type: "article_exam",
                    order_index: 2,
                    learning_content_id: "content-1",
                    exam_paper_id: "paper-1",
                },
            },
        });

        const center = buildNewcomerConfigCenter({
            units: [ambiguousBusinessUnit],
            articles: [],
            papers: [],
            materials: [],
            scorePrompts: [],
            settings: settings(),
            boundArticle: null,
        });

        const businessModule = center.modules.find((item) => item.moduleKey === "business_skills");
        expect(businessModule?.unitIds).toEqual([]);
        expect(businessModule?.issues.map((issue) => issue.code)).toContain("module_unit_missing");
    });

    it("uses the path config revision as the path authority when it is available", () => {
        const staleBusinessUnit = unit({
            unit_id: "business-unit",
            name: "模块二：旧商务技巧",
            unit_type: "quiz",
            config: {
                path: {
                    enabled: true,
                    path_key: NEWCOMER_TRAINING_PATH_KEY,
                    module_key: "business_skills",
                    module_type: "article_exam",
                    order_index: 2,
                    learning_content_id: "legacy-content",
                    exam_paper_id: "legacy-paper",
                },
            },
        });

        const center = buildNewcomerConfigCenter({
            units: [staleBusinessUnit],
            articles: [],
            papers: [],
            materials: [],
            scorePrompts: [],
            settings: settings(),
            boundArticle: null,
            pathConfig: {
                source: "active_revision",
                active_revision_id: "path-revision-2",
                active_revision_no: 2,
                working_revision_id: null,
                working_revision_no: null,
                has_unpublished_revision: false,
                path: {
                    path_key: "newcomer_training_path_v1",
                    title: "新人训练路径",
                    goal_title: "完成新人训练",
                    description: null,
                    enabled: true,
                    modules: [{
                        module_key: "business_skills",
                        module_type: "article_exam",
                        enabled: true,
                        order_index: 1,
                        title: "商务技巧新修订",
                        description: "从路径配置修订读取的说明",
                        target_unit_id: "business-unit",
                        learning_content_id: "content-2",
                        exam_paper_id: "paper-2",
                        disabled_reason: null,
                        unlock_after_unit_ids: [],
                        completion_rule: "submitted",
                        primary_action_label: "开始学习",
                        retry_action_label: null,
                        review_action_label: null,
                        guidance_templates: {},
                    }],
                },
            },
        });

        const businessModule = center.modules.find((item) => item.moduleKey === "business_skills");
        expect(center.governance.source).toBe("active_revision");
        expect(center.governance.activeRevisionLabel).toBe("当前生效版本 v2");
        expect(businessModule?.title).toBe("商务技巧新修订");
        expect(businessModule?.description).toBe("从路径配置修订读取的说明");
        expect(businessModule?.unitIds).toEqual(["business-unit"]);
    });

    it("marks business skills ready when article and paper are published", () => {
        const businessUnit = unit({
            unit_id: "business-unit",
            name: "模块二：商务技巧",
            unit_type: "quiz",
            config: {
                path: {
                    enabled: true,
                    path_key: NEWCOMER_TRAINING_PATH_KEY,
                    module_key: "business_skills",
                    module_type: "article_exam",
                    order_index: 2,
                    learning_content_id: "content-1",
                    exam_paper_id: "paper-1",
                },
            },
        });
        const article: NewcomerArticle = {
            module_key: "business_skills",
            learning_content_id: "content-1",
            title: "见客户前商务礼仪",
            summary: null,
            owner: null,
            source: "sales_trainer_business_skills",
            chapters: [{ chapter_id: "chapter-1", title: "第一节", content: "正文", order_index: 1 }],
        };
        const paper: NewcomerExamPaper = {
            paper_id: "paper-1",
            paper_key: "business-paper",
            title: "商务技巧考卷",
            description: null,
            module_key: "business_skills",
            unit_id: "paper-unit",
            pass_threshold: null,
            status: "published",
            created_by: null,
            updated_by: null,
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-01T00:00:00Z",
            questions: [{ question_id: "q1", order_index: 1, points: 10, question_type: "single_choice", title: "题目", stem: "题干" }],
        };

        const center = buildNewcomerConfigCenter({
            units: [businessUnit],
            articles: [],
            papers: [paper],
            materials: [],
            scorePrompts: [],
            settings: settings(),
            boundArticle: article,
        });

        const businessModule = center.modules.find((item) => item.moduleKey === "business_skills");
        expect(businessModule?.status).toBe("ready");
        expect(businessModule?.bindings).toContain("学习文章：见客户前商务礼仪（1 节）");
        expect(businessModule?.bindings).toContain("考卷：商务技巧考卷（1 题）");
    });

    it("marks business skills missing when the bound article has no chapters", () => {
        const businessUnit = unit({
            unit_id: "business-unit",
            name: "模块二：商务技巧",
            unit_type: "quiz",
            config: {
                path: {
                    enabled: true,
                    path_key: NEWCOMER_TRAINING_PATH_KEY,
                    module_key: "business_skills",
                    module_type: "article_exam",
                    order_index: 2,
                    learning_content_id: "content-1",
                    exam_paper_id: "paper-1",
                },
            },
        });
        const article: NewcomerArticle = {
            module_key: "business_skills",
            learning_content_id: "content-1",
            title: "见客户前商务礼仪",
            summary: null,
            owner: null,
            source: "sales_trainer_business_skills",
            chapters: [],
        };
        const paper: NewcomerExamPaper = {
            paper_id: "paper-1",
            paper_key: "business-paper",
            title: "商务技巧考卷",
            description: null,
            module_key: "business_skills",
            unit_id: "paper-unit",
            pass_threshold: null,
            status: "published",
            created_by: null,
            updated_by: null,
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-01T00:00:00Z",
            questions: [{ question_id: "q1", order_index: 1, points: 10, question_type: "single_choice", title: "题目", stem: "题干" }],
        };

        const center = buildNewcomerConfigCenter({
            units: [businessUnit],
            articles: [],
            papers: [paper],
            materials: [],
            scorePrompts: [],
            settings: settings(),
            boundArticle: article,
        });

        const businessModule = center.modules.find((item) => item.moduleKey === "business_skills");
        expect(businessModule?.status).toBe("missing");
        expect(businessModule?.issues.map((issue) => issue.code)).toContain("article_chapters_missing");
        expect(businessModule?.canPublish).toBe(false);
    });

    it("checks PPT material version and scoring prompt readiness", () => {
        const prompt: SalesTrainerAudioScorePrompt = {
            prompt_id: "prompt-1",
            name: "PPT 评分",
            purpose: "ppt_pitch",
            system_prompt: "system",
            scoring_template: "{transcript}",
            output_schema: {},
            learner_rubric: {},
            version: 1,
            status: "published",
            created_by: null,
            updated_by: null,
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-01T00:00:00Z",
        };
        const material: SalesTrainerMaterial = {
            material_id: "material-1",
            material_key: "ppt",
            name: "主胶片",
            material_type: "ppt_deck",
            description: null,
            purpose: "ppt_pitch",
            status: "published",
            current_version_id: "version-1",
            current_version: {
                version_id: "version-1",
                material_id: "material-1",
                version_label: "v1",
                title: "主胶片 v1",
                file_name: "deck.pptx",
                content_type: "application/pptx",
                file_size_bytes: 100,
                storage_key: "deck",
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
        const pptUnit = unit({
            unit_id: "ppt-unit",
            config: {
                audio: { scoring_prompt_id: "prompt-1", purpose: "ppt_pitch" },
                materials: { bindings: [{ material_id: "material-1", required: true }] },
                path: {
                    enabled: true,
                    path_key: NEWCOMER_TRAINING_PATH_KEY,
                    module_key: "ppt_explanation",
                    module_type: "audio_scoring",
                    order_index: 1,
                },
            },
        });

        const center = buildNewcomerConfigCenter({
            units: [pptUnit],
            articles: [],
            papers: [],
            materials: [material],
            scorePrompts: [prompt],
            settings: settings({ deucate_configured: true, dashscope_configured: true }),
            boundArticle: null,
        });

        const pptModule = center.modules.find((item) => item.moduleKey === "ppt_explanation");
        expect(pptModule?.status).toBe("ready");
        expect(pptModule?.bindings).toContain("材料：主胶片（v1）");
        expect(pptModule?.bindings).toContain("评分标准：PPT 评分 v1");
    });
});
