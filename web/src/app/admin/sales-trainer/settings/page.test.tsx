import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerSettingsPage from "./page";

const {
    getSettingsMock,
    getPathConfigMock,
    listPathConfigRevisionsMock,
    listAudioSubmissionsMock,
    listScoreResultsMock,
} = vi.hoisted(() => ({
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
        getSettingsMock.mockReset();
        getPathConfigMock.mockReset();
        listPathConfigRevisionsMock.mockReset();
        listAudioSubmissionsMock.mockReset();
        listScoreResultsMock.mockReset();
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
        expect(screen.getByText("当前生效版本 v3")).toBeTruthy();
        expect(screen.getByText("最近发布原因：发布绑定")).toBeTruthy();
        expect(screen.getByText("legacy 快照记录 2 条")).toBeTruthy();
        expect(screen.getByText("第1关：PPT讲解")).toBeTruthy();
        expect(screen.getByText("材料已绑定，缺少录音评分标准。")).toBeTruthy();
        expect(screen.getByText("第2关：商务技巧")).toBeTruthy();
        expect(screen.getByText("学习文章和考卷已绑定。")).toBeTruthy();
        expect(screen.getByText("最近失败任务")).toBeTruthy();
        expect(screen.getAllByText("[ASR_TIMEOUT]").length).toBeGreaterThan(0);
        expect(screen.getAllByText("[AI_SCORING_FAILED]").length).toBeGreaterThan(0);
        expect(screen.getByRole("link", { name: "查看学员录音" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/audio-submissions",
        );
        expect(screen.getByRole("link", { name: "查看学员录音" }).querySelector("button")).toBeNull();
        expect(screen.getByRole("link", { name: "查看评分结果" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/score-results",
        );
        expect(screen.getByRole("link", { name: "查看评分结果" }).querySelector("button")).toBeNull();
    });
});
