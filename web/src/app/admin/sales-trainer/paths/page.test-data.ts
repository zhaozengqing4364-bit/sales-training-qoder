import type {
    LearningContentListResponse,
    NewcomerArticle,
    NewcomerExamPaperListResponse,
    NewcomerPathConfigResponse,
    NewcomerPathModuleConfig,
    NewcomerPathRevisionListResponse,
    SalesTrainerAudioScorePromptListResponse,
    SalesTrainerMaterialListResponse,
    SalesTrainerSettings,
    SalesTrainerUnitListResponse,
} from "@/lib/api/types";

function businessSkillsModule(): NewcomerPathModuleConfig {
    return {
        module_key: "business_skills",
        module_type: "article_exam",
        enabled: true,
        order_index: 1,
        title: "商务技巧新修订",
        description: "从路径配置中心发布的商务技巧模块",
        target_unit_id: "business-unit",
        learning_content_id: "content-1",
        exam_paper_id: "paper-1",
        disabled_reason: null,
        unlock_after_unit_ids: [],
        completion_rule: "submitted",
        primary_action_label: "开始学习",
        retry_action_label: null,
        review_action_label: null,
        guidance_templates: {},
    };
}

export function defaultUnitsResponse(): SalesTrainerUnitListResponse {
    return {
        items: [{
            unit_id: "business-unit",
            name: "模块二：旧商务技巧",
            description: null,
            unit_type: "quiz",
            config: {
                path: {
                    enabled: true,
                    path_key: "newcomer_training_path_v1",
                    module_key: "business_skills",
                    module_type: "article_exam",
                    order_index: 2,
                    learning_content_id: "content-1",
                    exam_paper_id: "paper-1",
                },
            },
            status: "published",
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-01T00:00:00Z",
            questions: [],
        }],
        total: 1,
    };
}

export function defaultPathConfigResponse(): NewcomerPathConfigResponse {
    return {
        source: "active_revision",
        path: {
            path_key: "newcomer_training_path_v1",
            title: "新人训练路径",
            goal_title: "完成新人训练",
            description: null,
            enabled: true,
            modules: [businessSkillsModule()],
        },
        active_revision_id: "path-revision-2",
        active_revision_no: 2,
        working_revision_id: null,
        working_revision_no: null,
        has_unpublished_revision: false,
    };
}

export function pathConfigWithWorkingRevision(): NewcomerPathConfigResponse {
    return {
        ...defaultPathConfigResponse(),
        working_revision_id: "path-revision-3",
        working_revision_no: 3,
        has_unpublished_revision: true,
    };
}

export function defaultPathRevisionsResponse(): NewcomerPathRevisionListResponse {
    return {
        items: [{
            revision_id: "path-revision-2",
            revision_no: 2,
            status: "published",
            change_class: "semantic",
            title: "新人训练路径",
            module_count: 1,
            is_active: true,
            is_working: false,
            source_revision_id: "path-revision-1",
            payload_hash: "hash-2",
            reason: "更新商务技巧模块",
            trace_id: "trace-path-2",
            created_by: "admin-1",
            published_by: "admin-1",
            created_at: "2026-06-03T00:00:00Z",
            published_at: "2026-06-03T00:10:00Z",
        }],
        total: 1,
    };
}

export function pathRevisionsWithRollbackTarget(): NewcomerPathRevisionListResponse {
    return {
        items: [
            {
                ...defaultPathRevisionsResponse().items[0],
                revision_id: "path-revision-3",
                revision_no: 3,
                is_active: true,
                source_revision_id: "path-revision-2",
            },
            {
                ...defaultPathRevisionsResponse().items[0],
                revision_id: "path-revision-2",
                revision_no: 2,
                is_active: false,
                source_revision_id: "path-revision-1",
            },
        ],
        total: 2,
    };
}

export function defaultLearningContentsResponse(): LearningContentListResponse {
    return {
        items: [{
            learning_content_id: "content-1",
            title: "见客户前商务礼仪",
            summary: "学习商务礼仪",
            owner: "新人训练路径",
            source: "sales_trainer_business_skills",
            status: "published",
            safety_flagged: false,
            version: 1,
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-01T00:00:00Z",
            revision_state: {
                active_revision_id: "content-revision-1",
                active_revision_no: 1,
                working_revision_id: null,
                working_revision_no: null,
                has_unpublished_revision: false,
                edit_target: "working_revision",
                publish_label: "当前无待发布修订",
                save_result_copy: "已保存为待发布修订，发布修订后才会影响学员端。",
            },
            chapters: [{
                chapter_id: "chapter-1",
                learning_content_id: "content-1",
                title: "第一节",
                content: "正文",
                order_index: 1,
                created_at: "2026-06-01T00:00:00Z",
                updated_at: "2026-06-01T00:00:00Z",
            }],
        }],
        total: 1,
    };
}

export function defaultModuleArticle(): NewcomerArticle {
    return {
        module_key: "business_skills",
        learning_content_id: "content-1",
        title: "见客户前商务礼仪",
        summary: "学习商务礼仪",
        owner: "新人训练路径",
        source: "sales_trainer_business_skills",
        chapters: [{ chapter_id: "chapter-1", title: "第一节", content: "正文", order_index: 1 }],
    };
}

export function defaultPapersResponse(): NewcomerExamPaperListResponse {
    return {
        items: [{
            paper_id: "paper-1",
            paper_key: "business-paper",
            title: "商务技巧考卷",
            description: null,
            module_key: "business_skills",
            unit_id: "paper-unit",
            pass_threshold: 70,
            status: "published",
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-01T00:00:00Z",
            questions: [],
        }],
        total: 1,
    };
}

export function defaultMaterialsResponse(): SalesTrainerMaterialListResponse {
    return { items: [], total: 0 };
}

export function defaultScorePromptsResponse(): SalesTrainerAudioScorePromptListResponse {
    return { items: [], total: 0 };
}

export function defaultSettingsResponse(): SalesTrainerSettings {
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
    };
}
