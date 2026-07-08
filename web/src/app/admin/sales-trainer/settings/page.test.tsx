import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerSettingsPage from "./page";

const {
    getCapabilitiesMock,
    getSettingsMock,
    getPathConfigMock,
    listPathConfigRevisionsMock,
    listAudioSubmissionsMock,
    listScoreResultsMock,
} = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
    getSettingsMock: vi.fn(),
    getPathConfigMock: vi.fn(),
    listPathConfigRevisionsMock: vi.fn(),
    listAudioSubmissionsMock: vi.fn(),
    listScoreResultsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/settings",
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getCapabilities: getCapabilitiesMock,
                    getSettings: getSettingsMock,
                    listAudioSubmissions: listAudioSubmissionsMock,
                    listScoreResults: listScoreResultsMock,
                },
                newcomerTraining: {
                    ...actual.api.admin.newcomerTraining,
                    getPathConfig: getPathConfigMock,
                    listPathConfigRevisions: listPathConfigRevisionsMock,
                },
            },
        },
    };
});

describe("SalesTrainerSettingsPage", () => {
    beforeEach(() => {
        getCapabilitiesMock.mockReset();
        getSettingsMock.mockReset();
        getPathConfigMock.mockReset();
        listPathConfigRevisionsMock.mockReset();
        listAudioSubmissionsMock.mockReset();
        listScoreResultsMock.mockReset();
        getCapabilitiesMock.mockResolvedValue({
            role: "admin",
            role_label: "管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_questions: false,
                manage_modules: false,
                manage_prompts: false,
                view_records: false,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_logs: false,
                view_settings: true,
            },
            capability_keys: ["view_settings"],
        });
        getSettingsMock.mockResolvedValue({
            storage_backend: "local",
            direct_upload_supported: false,
            cos_configured: false,
            cos_public_read: false,
            oss_configured: false,
            asr_mode: "dashscope",
            asr_model: "paraformer",
            dashscope_configured: true,
            deucate_configured: false,
            deucate_model: null,
            max_file_size_mb: 200,
            allowed_mime_types: ["audio/wav"],
            file_url_expires_seconds: 3600,
            phase2_policy: {
                version: "sales_trainer_phase2_closed_loop_policy_v1",
                low_score_threshold: 70,
                repeat_practice_threshold: 2,
                dashboard_record_limit: 500,
                source: "database",
                config_version: 3,
                fallback_applied: false,
                fallback_reason: null,
                management_entry: "/admin/business-rules/sales-trainer-phase2",
            },
        });
        getPathConfigMock.mockResolvedValue({
            source: "active_revision",
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
        });
        listPathConfigRevisionsMock.mockResolvedValue({
            total: 1,
            items: [
                {
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
                },
            ],
        });
        listAudioSubmissionsMock.mockResolvedValue({
            total: 1,
            items: [
                {
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
                },
            ],
        });
        listScoreResultsMock.mockResolvedValue({
            total: 1,
            items: [
                {
                    score_id: "score-1",
                    submission_id: "sub-2",
                    prompt_id: "prompt-1",
                    prompt_version: 1,
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
                },
            ],
        });
    });

    it("shows recent failed tasks and frequent error codes with repair links", async () => {
        render(<SalesTrainerSettingsPage />);

        await waitFor(() => {
            expect(listAudioSubmissionsMock).toHaveBeenCalledWith({ limit: 100 });
        });
        expect(getPathConfigMock).toHaveBeenCalled();
        expect(listPathConfigRevisionsMock).toHaveBeenCalled();
        expect(listScoreResultsMock).toHaveBeenCalledWith({ limit: 100 });

        expect(screen.getByText("路径配置诊断")).toBeTruthy();
        expect(screen.getByText("阶段 2 训练闭环策略")).toBeTruthy();
        expect(screen.getByText("500")).toBeTruthy();
        expect(screen.getByText("database")).toBeTruthy();
        expect(screen.getByText("sales_trainer_phase2_closed_loop_policy_v1")).toBeTruthy();
        expect(screen.getByRole("link", { name: "打开策略治理" }).getAttribute("href")).toBe(
            "/admin/business-rules/sales-trainer-phase2",
        );
        expect(screen.getByRole("link", { name: "打开运行时健康" }).getAttribute("href")).toBe(
            "/support/runtime",
        );
        expect(screen.getByRole("link", { name: "查看运行时健康" }).getAttribute("href")).toBe(
            "/support/runtime",
        );
        expect(screen.getByText("当前生效版本 v3")).toBeTruthy();
        expect(screen.getByText("最近发布原因：发布绑定")).toBeTruthy();
        expect(screen.getByText("legacy 快照记录 2 条")).toBeTruthy();
        expect(screen.getByText("第1关：PPT讲解")).toBeTruthy();
        expect(screen.getByText("材料已绑定，缺少录音评分标准。")).toBeTruthy();
        expect(screen.getByText("第2关：商务技巧")).toBeTruthy();
        expect(screen.getByText("专题内容和考卷已绑定。")).toBeTruthy();
        expect(screen.getByText("最近失败任务")).toBeTruthy();
        expect(screen.getAllByText("[ASR_TIMEOUT]").length).toBeGreaterThan(0);
        expect(screen.getAllByText("[AI_SCORING_FAILED]").length).toBeGreaterThan(0);
        expect(screen.getByRole("link", { name: "查看学员录音" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/audio/submissions",
        );
        expect(screen.getByRole("link", { name: "查看学员录音" }).querySelector("button")).toBeNull();
        expect(screen.getByRole("link", { name: "查看评分结果" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/audio/results",
        );
        expect(screen.getByRole("link", { name: "查看评分结果" }).querySelector("button")).toBeNull();
    });

    it("shows a page-level loading state while configuration diagnostics are loading", () => {
        getSettingsMock.mockReturnValue(new Promise(() => undefined));

        render(<SalesTrainerSettingsPage />);

        expect(screen.getByRole("status").textContent).toContain("正在加载配置诊断...");
        expect(screen.queryByText("音频上传")).toBeNull();
    });

    it("keeps dependency failures visible and retries the diagnostics load", async () => {
        getSettingsMock.mockRejectedValueOnce(new Error("settings unavailable"));

        render(<SalesTrainerSettingsPage />);

        expect(await screen.findByText("配置诊断加载失败")).toBeTruthy();
        expect(screen.getByText("settings unavailable")).toBeTruthy();
        expect(screen.queryByText("音频上传")).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "重新加载配置" }));

        await waitFor(() => {
            expect(getSettingsMock).toHaveBeenCalledTimes(2);
        });
        expect(await screen.findByText("音频上传")).toBeTruthy();
    });

    it("fails closed before loading diagnostics when capabilities are unavailable", async () => {
        getCapabilitiesMock.mockRejectedValueOnce(new Error("capability unavailable"));

        render(<SalesTrainerSettingsPage />);

        expect(await screen.findByText("页面访问受限")).toBeTruthy();
        expect(screen.getByText("capability unavailable")).toBeTruthy();
        expect(getSettingsMock).not.toHaveBeenCalled();
        expect(getPathConfigMock).not.toHaveBeenCalled();
        expect(listPathConfigRevisionsMock).not.toHaveBeenCalled();
        expect(listAudioSubmissionsMock).not.toHaveBeenCalled();
        expect(listScoreResultsMock).not.toHaveBeenCalled();
        expect(screen.queryByText("音频上传")).toBeNull();
    });
});
