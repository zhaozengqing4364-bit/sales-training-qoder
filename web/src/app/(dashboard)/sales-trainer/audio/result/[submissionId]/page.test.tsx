import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerAudioResultPage from "./page";

const { getAudioSubmissionMock, getUnitMock, listPathsMock } = vi.hoisted(() => ({
    getAudioSubmissionMock: vi.fn(),
    getUnitMock: vi.fn(),
    listPathsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ submissionId: "submission-1" }),
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
        getUnitMock.mockReset();
        listPathsMock.mockReset();
        listPathsMock.mockResolvedValue({
            items: [
                {
                    path_key: "new_seller",
                    title: "新人销售闯关",
                    goal_title: "掌握首次客户沟通",
                    total_levels: 2,
                    completed_levels: 1,
                    current_level_id: "audio-unit",
                    next_level_id: "audio-unit",
                    levels: [
                        {
                            unit_id: "audio-unit",
                            name: "录音单元",
                            description: "录音训练",
                            unit_type: "audio_scoring",
                            order_index: 2,
                            level_title: "第二关：录音表达",
                            level_description: "上传讲解录音。",
                            locked: false,
                            lock_reason: null,
                            status: "in_progress",
                            completion_rule: "passed",
                            primary_action_label: "上传语音作业",
                            retry_action_label: "重练本关",
                            review_action_label: "查看结果",
                            target_path: "/sales-trainer/audio/audio-unit",
                            latest_result: null,
                        },
                    ],
                    goal_context: {
                        goal_title: "掌握首次客户沟通",
                        score_basis: "sales_trainer_path_projection_v1",
                        evidence_items: [],
                        weak_points: [],
                        next_recommendation: {
                            title: "重练：第二关：录音表达",
                            reason: "表达结构还可以更清楚，建议重练本关。",
                            action_label: "重练本关",
                            target_path: "/sales-trainer/audio/audio-unit",
                            unit_id: "audio-unit",
                            level_title: "第二关：录音表达",
                            recommendation_kind: "retry_level",
                        },
                    },
                },
            ],
            total: 1,
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

    it("renders authorized playback and download links instead of exposing storage keys", async () => {
        render(<SalesTrainerAudioResultPage />);

        const playbackLink = await screen.findByRole("link", { name: /授权播放/ });
        const downloadLink = screen.getByRole("link", { name: /下载语音/ });

        expect(playbackLink.getAttribute("href")).toContain("/sales-trainer/audio-submissions/submission-1/file");
        expect(downloadLink.getAttribute("href")).toContain("/sales-trainer/audio-submissions/submission-1/file");
        expect(screen.queryByText("private/audio/pitch.wav")).toBeNull();
        expect(screen.queryByText(/storage_key/)).toBeNull();
        expect(await screen.findByText("语音作业反馈")).toBeTruthy();
        expect(screen.getAllByText("评分完成").length).toBeGreaterThanOrEqual(1);
        expect(await screen.findByText("练完下一步")).toBeTruthy();
        expect(screen.getByText("重练：第二关：录音表达")).toBeTruthy();
        expect(screen.getByRole("link", { name: /重练本关/ }).getAttribute("href")).toBe("/sales-trainer/audio/audio-unit");
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

    it("shows improvement suggestions when the submission did not pass", async () => {
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
