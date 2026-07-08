import { describe, expect, it } from "vitest";

import type {
    NewcomerPathConfigDiagnostics,
    NewcomerPathConfigResponse,
    NewcomerPathRevisionSummary,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
} from "@/lib/api/types";

import { buildNewcomerOperationalDiagnostics } from "./operational-diagnostics";

function pathConfigDiagnostics(
    overrides: Partial<NewcomerPathConfigDiagnostics> = {},
): NewcomerPathConfigDiagnostics {
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
        ...overrides,
    };
}

const failedSubmission = {
    submission_id: "sub-1",
    unit_id: "ppt-unit",
    user_id: "learner-1",
    user_name: "张三",
    user_email: null,
    user_department: "销售一部",
    purpose: "ppt_explanation",
    original_filename: "ppt.wav",
    content_type: "audio/wav",
    size_bytes: 1024,
    storage_key: "sales-trainer/sub-1.wav",
    file_hash: null,
    duration_seconds: 90,
    source_page: "/sales-trainer/audio/ppt-unit",
    confirmed_material_version_id: null,
    confirmed_material_at: null,
    material_snapshot: null,
    score_scheme_snapshot: null,
    task_brief_snapshot: null,
    path_key: null,
    path_revision_id: null,
    path_revision_no: null,
    module_key: null,
    legacy_snapshot_only: true,
    status: "transcription_failed",
    error_code: "[ASR_TIMEOUT]",
    error_message: "ASR 服务超时",
    created_at: "2026-06-03T08:00:00Z",
    updated_at: "2026-06-03T08:01:00Z",
    transcript: null,
    score_result: null,
} satisfies SalesTrainerAudioSubmission;

const scoredSubmission = {
    ...failedSubmission,
    submission_id: "sub-2",
    legacy_snapshot_only: false,
    status: "scored",
    error_code: null,
    error_message: null,
} satisfies SalesTrainerAudioSubmission;

const failedScoreResult = {
    score_id: "score-1",
    submission_id: "sub-3",
    prompt_id: "prompt-1",
    prompt_version: 2,
    prompt_hash: "hash",
    deucate_model: "deucate-v1",
    transcript_snapshot: "hello",
    total_score: null,
    passed: null,
    summary: null,
    strengths: [],
    improvements: [],
    dimension_scores: {},
    raw_response: null,
    error_code: "[AI_SCORING_FAILED]",
    error_message: "评分服务失败",
    latency_ms: 1200,
    path_key: null,
    path_revision_id: null,
    path_revision_no: null,
    module_key: null,
    legacy_snapshot_only: true,
    created_at: "2026-06-03T08:02:00Z",
} satisfies SalesTrainerAudioScoreResult;

const pathConfig = {
    source: "active_revision",
    fallback_reason: null,
    legacy_snapshot_only: false,
    management_entry: "/admin/newcomer-training/path-config",
    permission: "sales_trainer.manage_modules",
    path: {
        path_key: "newcomer_training_path_v1",
        title: "新人训练路径",
        goal_title: "新人训练路径",
        description: "从学习到考试再到录音评分",
        enabled: true,
        modules: [
            {
                module_key: "ppt_explanation",
                module_type: "audio_scoring",
                enabled: true,
                order_index: 1,
                title: "第1关：PPT讲解",
                description: "上传PPT讲解录音并获取评分。",
                target_unit_id: "ppt-unit",
                learning_content_id: null,
                exam_paper_id: null,
                material_id: "material-1",
                material_version_id: "material-version-1",
                scoring_prompt_id: null,
                disabled_reason: null,
                unlock_after_unit_ids: [],
                completion_rule: "scored",
                primary_action_label: "开始录音",
                retry_action_label: "重新录音",
                review_action_label: "查看结果",
                guidance_templates: {},
            },
            {
                module_key: "business_skills",
                module_type: "article_exam",
                enabled: true,
                order_index: 2,
                title: "第2关：商务技巧",
                description: "先学习商务礼仪，再完成考试。",
                target_unit_id: "business-unit",
                learning_content_id: "article-1",
                exam_paper_id: "paper-1",
                disabled_reason: null,
                unlock_after_unit_ids: ["ppt-unit"],
                completion_rule: "passed",
                primary_action_label: "开始学习",
                retry_action_label: "重新考试",
                review_action_label: "查看结果",
                guidance_templates: {},
            },
        ],
    },
    active_revision_id: "path-revision-3",
    active_revision_no: 3,
    working_revision_id: null,
    working_revision_no: null,
    has_unpublished_revision: false,
    diagnostics: pathConfigDiagnostics(),
} satisfies NewcomerPathConfigResponse;

const pathRevision = {
    revision_id: "path-revision-3",
    revision_no: 3,
    status: "published",
    change_class: "binding",
    title: "新人训练路径",
    module_count: 2,
    is_active: true,
    is_working: false,
    source_revision_id: "path-revision-2",
    payload_hash: "hash-3",
    reason: "发布绑定",
    trace_id: "trace-3",
    created_by: "admin",
    published_by: "admin",
    created_at: "2026-06-03T07:00:00Z",
    published_at: "2026-06-03T07:10:00Z",
} satisfies NewcomerPathRevisionSummary;

describe("buildNewcomerOperationalDiagnostics", () => {
    it("summarizes recent failed tasks and error code buckets", () => {
        const diagnostics = buildNewcomerOperationalDiagnostics({
            audioSubmissions: [scoredSubmission, failedSubmission],
            scoreResults: [failedScoreResult],
            pathConfig,
            pathRevisions: [pathRevision],
        });

        expect(diagnostics.failedCount).toBe(2);
        expect(diagnostics.failedTasks.map((item) => item.errorCode)).toEqual([
            "[AI_SCORING_FAILED]",
            "[ASR_TIMEOUT]",
        ]);
        expect(diagnostics.failedTasks[0]?.href).toBe("/admin/sales-trainer/score-results");
        expect(diagnostics.failedTasks[1]?.href).toBe("/admin/sales-trainer/audio-submissions/sub-1");
        expect(diagnostics.errorCodeBuckets).toEqual([
            { code: "[AI_SCORING_FAILED]", count: 1 },
            { code: "[ASR_TIMEOUT]", count: 1 },
        ]);
        expect(diagnostics.configuration?.activeRevisionLabel).toBe("当前生效版本 v3");
        expect(diagnostics.configuration?.latestReason).toBe("发布绑定");
        expect(diagnostics.configuration?.legacySnapshotOnlyCount).toBe(2);
        expect(diagnostics.configuration?.moduleBindings).toEqual([
            {
                title: "第1关：PPT讲解",
                status: "missing",
                detail: "材料已绑定，缺少录音评分标准。",
                href: "/admin/sales-trainer/paths?module=ppt_explanation",
            },
            {
                title: "第2关：商务技巧",
                status: "ready",
                detail: "专题内容和考卷已绑定。",
                href: "/admin/sales-trainer/paths?module=business_skills",
            },
        ]);
    });

    it("classifies realtime roleplay modules from runtime binding and provider readiness", () => {
        const diagnostics = buildNewcomerOperationalDiagnostics({
            audioSubmissions: [],
            scoreResults: [],
            pathConfig: {
                ...pathConfig,
                path: {
                    ...pathConfig.path,
                    modules: [
                        {
                            module_key: "realtime_roleplay",
                            module_type: "realtime_roleplay",
                            enabled: true,
                            order_index: 1,
                            title: "第4关：实时对练",
                            description: "进入真实实时对练。",
                            target_unit_id: null,
                            learning_content_id: null,
                            exam_paper_id: null,
                            material_id: null,
                            material_version_id: null,
                            scoring_prompt_id: null,
                            disabled_reason: null,
                            unlock_after_unit_ids: [],
                            completion_rule: "submitted",
                            primary_action_label: "开始对练",
                            retry_action_label: null,
                            review_action_label: null,
                            guidance_templates: {},
                            runtime_binding: {
                                binding_key: "newcomer_realtime_roleplay_v1",
                                runtime_owner: "training_runtime",
                                runtime_descriptor_id: "newcomer-realtime-runtime",
                                scenario_key: "newcomer-realtime-roleplay",
                                practice_template_id: "template-1",
                                runtime_config_revision_id: "runtime-config-rev-1",
                                roleplay_contract_revision_id: "roleplay-contract-rev-1",
                                provider_readiness_snapshot: {
                                    ready: true,
                                    provider: "stepfun_realtime",
                                    checked_at: "2026-06-27T00:00:00Z",
                                    failure_code: null,
                                    failure_message: null,
                                },
                            },
                        },
                        {
                            module_key: "realtime_roleplay_retry",
                            module_type: "realtime_roleplay",
                            enabled: true,
                            order_index: 2,
                            title: "第5关：实时复盘",
                            description: "复盘实时对练。",
                            target_unit_id: null,
                            learning_content_id: null,
                            exam_paper_id: null,
                            material_id: null,
                            material_version_id: null,
                            scoring_prompt_id: null,
                            disabled_reason: null,
                            unlock_after_unit_ids: [],
                            completion_rule: "submitted",
                            primary_action_label: "开始复盘",
                            retry_action_label: null,
                            review_action_label: null,
                            guidance_templates: {},
                            runtime_binding: {
                                binding_key: "newcomer_realtime_roleplay_v1",
                                runtime_owner: "training_runtime",
                                runtime_descriptor_id: "newcomer-realtime-runtime",
                                scenario_key: "newcomer-realtime-roleplay",
                                practice_template_id: "template-1",
                                runtime_config_revision_id: "runtime-config-rev-2",
                                roleplay_contract_revision_id: "roleplay-contract-rev-1",
                                provider_readiness_snapshot: {
                                    ready: false,
                                    provider: "stepfun_realtime",
                                    checked_at: "2026-06-27T00:00:00Z",
                                    failure_code: "credential_missing",
                                    failure_message: "StepFun 凭证缺失",
                                },
                            },
                        },
                    ],
                },
            },
            pathRevisions: [pathRevision],
        });

        expect(diagnostics.configuration?.moduleBindings).toEqual([
            {
                title: "第4关：实时对练",
                status: "ready",
                detail: "运行时 newcomer-realtime-runtime 与 provider readiness 已就绪。",
                href: "/support/runtime",
            },
            {
                title: "第5关：实时复盘",
                status: "missing",
                detail: "provider readiness 未通过：StepFun 凭证缺失",
                href: "/support/runtime",
            },
        ]);
    });

    it("uses path diagnostics readiness projection before falling back to runtime binding", () => {
        const diagnostics = buildNewcomerOperationalDiagnostics({
            audioSubmissions: [],
            scoreResults: [],
            pathConfig: {
                ...pathConfig,
                diagnostics: pathConfigDiagnostics({
                    realtime_provider_readiness: [{
                        module_key: "realtime_roleplay",
                        module_type: "realtime_roleplay",
                        title: "第4关：实时对练",
                        enabled: true,
                        runtime_descriptor_id: "newcomer-realtime-runtime",
                        ready: true,
                        provider_readiness_snapshot: {
                            ready: true,
                            provider: "stepfun_realtime",
                            checked_at: "2026-06-27T00:00:00Z",
                            config_revision_id: null,
                            failure_code: null,
                            failure_message: null,
                        },
                        failure_code: null,
                        failure_message: null,
                    }],
                }),
                path: {
                    ...pathConfig.path,
                    modules: [{
                        module_key: "realtime_roleplay",
                        module_type: "realtime_roleplay",
                        enabled: true,
                        order_index: 1,
                        title: "第4关：实时对练",
                        description: "进入真实实时对练。",
                        target_unit_id: null,
                        learning_content_id: null,
                        exam_paper_id: null,
                        material_id: null,
                        material_version_id: null,
                        scoring_prompt_id: null,
                        disabled_reason: null,
                        unlock_after_unit_ids: [],
                        completion_rule: "submitted",
                        primary_action_label: "开始对练",
                        retry_action_label: null,
                        review_action_label: null,
                        guidance_templates: {},
                        runtime_binding: null,
                    }],
                },
            },
            pathRevisions: [pathRevision],
        });

        expect(diagnostics.configuration?.moduleBindings).toEqual([{
            title: "第4关：实时对练",
            status: "ready",
            detail: "运行时 newcomer-realtime-runtime 与 provider readiness 已就绪。",
            href: "/support/runtime",
        }]);
    });
});
