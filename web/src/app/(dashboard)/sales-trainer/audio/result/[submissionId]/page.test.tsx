import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerAudioResultPage from "./page";

const { getAudioSubmissionMock, getJourneyMock, getUnitMock, listPathsMock } = vi.hoisted(() => ({
    getAudioSubmissionMock: vi.fn(),
    getJourneyMock: vi.fn(),
    getUnitMock: vi.fn(),
    listPathsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ submissionId: "submission-1" }),
    useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            salesTrainer: {
                ...actual.api.salesTrainer,
                getAudioSubmission: getAudioSubmissionMock,
                getJourney: getJourneyMock,
                getUnit: getUnitMock,
                listPaths: listPathsMock,
            },
        },
    };
});

const scoredSubmission = {
    submission_id: "submission-1",
    unit_id: "audio-unit",
    user_id: "user-1",
    purpose: "general_audio_scoring",
    original_filename: "pitch.wav",
    content_type: "audio/wav",
    size_bytes: 1024,
    storage_key: "private/audio/pitch.wav",
    file_hash: null,
    duration_seconds: null,
    status: "scored" as const,
    error_code: null,
    error_message: null,
    created_at: "2026-05-28T00:00:00Z",
    updated_at: "2026-05-28T00:05:00Z",
    transcript: null,
    score_result: {
        score_id: "score-1",
        submission_id: "submission-1",
        prompt_id: "prompt-1",
        prompt_version: 1,
        prompt_hash: "hash",
        deucate_model: "model",
        transcript_snapshot: "转写文本",
        total_score: 88,
        passed: true,
        summary: "表达清楚",
        strengths: [],
        improvements: [],
        dimension_scores: {},
        raw_response: null,
        error_code: null,
        error_message: null,
        latency_ms: 1200,
        created_at: "2026-05-28T00:05:00Z",
    },
};

describe("SalesTrainerAudioResultPage", () => {
    beforeEach(() => {
        getAudioSubmissionMock.mockReset();
        getJourneyMock.mockReset();
        getUnitMock.mockReset();
        listPathsMock.mockReset();
        getJourneyMock.mockResolvedValue({
            journey_id: "journey-user-1",
            learner_id: "user-1",
            learner_name: "新人",
            department: "销售一部",
            path_key: "newcomer_training_path_v1",
            path_revision_id: "revision-1",
            path_revision_no: 1,
            source: "active_revision",
            legacy_snapshot_only: false,
            role_capabilities: [],
            learner_level: {
                level_key: "unassigned",
                label: "未分配",
                source: "training_projection",
                rank: 0,
            },
            role_level: {
                level_key: "learner",
                label: "学员",
                source: "training_projection",
                rank: 0,
            },
            training_stage: "in_progress",
            modules: [{
                module_key: "audio-unit",
                title: "重练：第二关：录音表达",
                kind: "audio_submission",
                module_type: "audio_scoring",
                display_name: "重练：第二关：录音表达",
                order_index: 2,
                enabled: true,
                status: "in_progress",
                stage: "in_progress",
                passed: false,
                score: 88,
                max_score: 100,
                required: true,
                completion_satisfied: false,
                locked: false,
                block_reason: null,
                completion_rule: "passed",
                source: {
                    path_revision_id: "revision-1",
                    path_revision_no: 1,
                },
                learner_level_required: null,
                unmet_reasons: [],
                diagnostics: [],
                next_action: {
                    action_key: "retry_audio",
                    label: "重练本关",
                    target_path: "/sales-trainer/audio/audio-unit",
                    disabled: false,
                    disabled_reason: null,
                },
                latest_outcome: null,
                outcome_history: [],
            }],
            overall_progress: {
                total_modules: 1,
                completed_modules: 0,
                passed_modules: 0,
                failed_modules: 1,
                needs_remediation_modules: 1,
            },
            diagnostics: [],
        });
        getUnitMock.mockResolvedValue({
            unit_id: "audio-unit",
            name: "录音单元",
            description: "录音训练",
            unit_type: "audio_scoring",
            config: { audio: { pass_threshold: 70 } },
            status: "published",
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: "2026-05-28T00:00:00Z",
            updated_at: "2026-05-28T00:00:00Z",
            questions: [],
        });
        getAudioSubmissionMock.mockResolvedValue(scoredSubmission);
    });

    it("renders inline audio playback and download link instead of exposing storage keys", async () => {
        render(<SalesTrainerAudioResultPage />);

        const audio = await screen.findByTestId("audio-playback");
        const downloadLink = screen.getByRole("link", { name: /下载语音/ });

        expect(audio.getAttribute("src")).toContain("/sales-trainer/audio-submissions/submission-1/file");
        expect(downloadLink.getAttribute("href")).toContain("/sales-trainer/audio-submissions/submission-1/file");
        expect(screen.queryByText("private/audio/pitch.wav")).toBeNull();
        expect(screen.queryByText(/storage_key/)).toBeNull();
        expect(await screen.findByText("评分方式")).toBeTruthy();
        expect(screen.getByText("AI 评分")).toBeTruthy();
        expect(screen.queryByText("model")).toBeNull();
        expect(await screen.findByText("语音作业反馈")).toBeTruthy();
        expect(screen.getAllByText("评分完成").length).toBeGreaterThanOrEqual(1);
        expect(await screen.findByText("练完下一步")).toBeTruthy();
        expect(screen.getByText("重练：第二关：录音表达")).toBeTruthy();
        expect(screen.getByRole("link", { name: /重练本关/ }).getAttribute("href")).toBe("/sales-trainer/audio/audio-unit");
        expect(listPathsMock).not.toHaveBeenCalled();
    });

    it("shows a diagnostic instead of defaulting to 70 when the pass threshold is missing", async () => {
        getUnitMock.mockResolvedValueOnce({
            unit_id: "audio-unit",
            name: "录音单元",
            description: "录音训练",
            unit_type: "audio_scoring",
            config: { audio: {} },
            status: "published",
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: "2026-05-28T00:00:00Z",
            updated_at: "2026-05-28T00:00:00Z",
            questions: [],
        });

        render(<SalesTrainerAudioResultPage />);

        expect(await screen.findByText("评分标准配置不可用")).toBeTruthy();
        expect(screen.getByText(/训练单元缺少语音作业通过线配置/)).toBeTruthy();
        expect(screen.queryByText(/本关需达到 70 分通过/)).toBeNull();
    });

    it("polls until the submission reaches a terminal scored state", async () => {
        getAudioSubmissionMock
            .mockResolvedValueOnce({
                ...scoredSubmission,
                status: "transcribing",
                score_result: null,
            })
            .mockResolvedValueOnce(scoredSubmission);

        render(<SalesTrainerAudioResultPage />);

        expect((await screen.findAllByText("正在转写")).length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText(/转写与评分通常需要 1–3 分钟/)).toBeTruthy();

        await waitFor(() => {
            expect(getAudioSubmissionMock.mock.calls.length).toBeGreaterThanOrEqual(2);
        }, { timeout: 10000 });

        expect(screen.getAllByText("评分完成").length).toBeGreaterThanOrEqual(1);
    });

    it("shows actionable retry guidance when audio scoring times out", async () => {
        getAudioSubmissionMock.mockResolvedValue({
            submission_id: "submission-1",
            unit_id: "audio-unit",
            user_id: "user-1",
            purpose: "general_audio_scoring",
            original_filename: "pitch.wav",
            content_type: "audio/wav",
            size_bytes: 1024,
            storage_key: "private/audio/pitch.wav",
            file_hash: null,
            duration_seconds: null,
            status: "scoring_failed",
            error_code: "[DEUCATE_TIMEOUT]",
            error_message: "[DEUCATE_TIMEOUT]",
            created_at: "2026-05-28T00:00:00Z",
            updated_at: "2026-05-28T00:05:00Z",
            transcript: {
                transcript_id: "transcript-1",
                provider: "dashscope-paraformer-file",
                transcript_text: "helloworld",
                raw_payload: null,
                started_at: "2026-05-28T00:01:00Z",
                completed_at: "2026-05-28T00:02:00Z",
                created_at: "2026-05-28T00:02:00Z",
            },
            score_result: {
                score_id: "score-1",
                submission_id: "submission-1",
                prompt_id: "prompt-1",
                prompt_version: 1,
                prompt_hash: "hash",
                deucate_model: "model",
                transcript_snapshot: "helloworld",
                total_score: null,
                passed: null,
                summary: null,
                strengths: [],
                improvements: [],
                dimension_scores: {},
                raw_response: null,
                error_code: "[DEUCATE_TIMEOUT]",
                error_message: "[DEUCATE_TIMEOUT]",
                latency_ms: null,
                created_at: "2026-05-28T00:05:00Z",
            },
        });

        render(<SalesTrainerAudioResultPage />);

        expect(await screen.findByText(/评分服务响应超时/)).toBeTruthy();
        expect(screen.getByText("待重试")).toBeTruthy();
        expect(screen.queryByText("[DEUCATE_TIMEOUT]")).toBeNull();
    });

    it("does not fabricate a 70-point pass threshold when the unit lookup fails", async () => {
        getUnitMock.mockRejectedValueOnce(new Error("unit lookup failed"));

        render(<SalesTrainerAudioResultPage />);

        expect(await screen.findByText("语音作业反馈")).toBeTruthy();
        expect(screen.queryByText(/本关需达到 70 分通过/)).toBeNull();
        expect(await screen.findByText("评分标准配置不可用")).toBeTruthy();
        expect(screen.getByText(/unit lookup failed/)).toBeTruthy();
    });

    it("keeps submission load failures recoverable instead of treating them as missing results", async () => {
        getAudioSubmissionMock.mockRejectedValueOnce(new Error("submission lookup failed"));

        render(<SalesTrainerAudioResultPage />);

        expect(await screen.findByText("语音作业结果加载失败")).toBeTruthy();
        expect(screen.getByText("submission lookup failed")).toBeTruthy();
        expect(screen.queryByText("语音作业结果不存在。")).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "重新加载结果" }));

        await waitFor(() => {
            expect(getAudioSubmissionMock).toHaveBeenCalledTimes(2);
        });
        expect(await screen.findByText("语音作业反馈")).toBeTruthy();
        expect(screen.queryByText("语音作业结果加载失败")).toBeNull();
    });

    it("shows improvement suggestions when improvements exist regardless of passed", async () => {
        getAudioSubmissionMock.mockResolvedValue({
            ...scoredSubmission,
            score_result: {
                ...scoredSubmission.score_result,
                total_score: 55,
                passed: false,
                improvements: ["先讲客户痛点", "补充产品价值"],
            },
        });

        render(<SalesTrainerAudioResultPage />);

        expect(await screen.findByText("改进建议")).toBeTruthy();
        expect(screen.getByText("先讲客户痛点")).toBeTruthy();
        expect(screen.getByText("补充产品价值")).toBeTruthy();
    });

    it("shows strengths section for passed submissions", async () => {
        getAudioSubmissionMock.mockResolvedValue({
            ...scoredSubmission,
            score_result: {
                ...scoredSubmission.score_result,
                total_score: 88,
                passed: true,
                strengths: ["结构清晰", "重点突出"],
                improvements: [],
            },
        });

        render(<SalesTrainerAudioResultPage />);

        expect(await screen.findByText("优点")).toBeTruthy();
        expect(screen.getByText("结构清晰")).toBeTruthy();
        expect(screen.getByText("重点突出")).toBeTruthy();
    });

    it("shows improvements even when the submission passed", async () => {
        getAudioSubmissionMock.mockResolvedValue({
            ...scoredSubmission,
            score_result: {
                ...scoredSubmission.score_result,
                total_score: 88,
                passed: true,
                improvements: ["可以更精炼"],
            },
        });

        render(<SalesTrainerAudioResultPage />);

        expect(await screen.findByText("改进建议")).toBeTruthy();
        expect(screen.getByText("可以更精炼")).toBeTruthy();
    });

    it("renders PPT dimension scores from the frozen scoring snapshot", async () => {
        getAudioSubmissionMock.mockResolvedValue({
            ...scoredSubmission,
            score_scheme_snapshot: {
                name: "PPT 讲解评分",
                version: 2,
                learner_rubric: {
                    criteria: [
                        {
                            key: "ppt_structure",
                            label: "PPT 结构完整度",
                            description: "覆盖背景、方案核心、下一步。",
                            weight: 25,
                        },
                        {
                            key: "customer_value",
                            label: "客户价值表达",
                            weight: 20,
                        },
                    ],
                },
            },
            score_result: {
                ...scoredSubmission.score_result,
                dimension_scores: {
                    ppt_structure: {
                        score: 22,
                        max_score: 25,
                        comment: "结构完整，但下一步动作可以更具体。",
                    },
                    customer_value: 16,
                },
            },
        });

        render(<SalesTrainerAudioResultPage />);

        expect(await screen.findByText("分项评分")).toBeTruthy();
        expect(screen.getByText("PPT 结构完整度")).toBeTruthy();
        expect(screen.getByText("22 / 25")).toBeTruthy();
        expect(screen.getByText("结构完整，但下一步动作可以更具体。")).toBeTruthy();
        expect(screen.getByText("客户价值表达")).toBeTruthy();
        expect(screen.getByText("16 / 20")).toBeTruthy();
    });

    it("renders object-shaped improvement suggestions without crashing", async () => {
        getAudioSubmissionMock.mockResolvedValue({
            ...scoredSubmission,
            score_result: {
                ...scoredSubmission.score_result,
                total_score: 55,
                passed: false,
                improvements: [
                    { title: "客户痛点", text: "先复述客户当前困扰" },
                    { suggestion: "补充可量化价值" },
                ],
            },
        });

        render(<SalesTrainerAudioResultPage />);

        expect(await screen.findByText("客户痛点：先复述客户当前困扰")).toBeTruthy();
        expect(screen.getByText("补充可量化价值")).toBeTruthy();
    });
});
