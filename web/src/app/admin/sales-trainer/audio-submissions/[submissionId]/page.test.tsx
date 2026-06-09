import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerAudioSubmissionDetailPage from "./page";

const {
    getAudioSubmissionMock,
    getAudioSubmissionFileUrlMock,
    previewAudioSubmissionRegradeMock,
    retryAudioScoringMock,
    retryAudioTranscriptionMock,
    runAudioSubmissionRegradeMock,
} = vi.hoisted(() => ({
    getAudioSubmissionMock: vi.fn(),
    getAudioSubmissionFileUrlMock: vi.fn(),
    previewAudioSubmissionRegradeMock: vi.fn(),
    retryAudioScoringMock: vi.fn(),
    retryAudioTranscriptionMock: vi.fn(),
    runAudioSubmissionRegradeMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ submissionId: "submission-1" }),
    usePathname: () => "/admin/sales-trainer/audio-submissions/submission-1",
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: vi.fn(),
        error: vi.fn(),
    }),
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
                    getAudioSubmission: getAudioSubmissionMock,
                    getAudioSubmissionFileUrl: getAudioSubmissionFileUrlMock,
                    previewAudioSubmissionRegrade: previewAudioSubmissionRegradeMock,
                    retryAudioScoring: retryAudioScoringMock,
                    retryAudioTranscription: retryAudioTranscriptionMock,
                    runAudioSubmissionRegrade: runAudioSubmissionRegradeMock,
                },
            },
        },
    };
});

describe("SalesTrainerAudioSubmissionDetailPage", () => {
    beforeEach(() => {
        getAudioSubmissionMock.mockReset();
        getAudioSubmissionFileUrlMock.mockReset();
        previewAudioSubmissionRegradeMock.mockReset();
        retryAudioScoringMock.mockReset();
        retryAudioTranscriptionMock.mockReset();
        runAudioSubmissionRegradeMock.mockReset();

        getAudioSubmissionFileUrlMock.mockReturnValue("http://localhost/audio.wav");
        getAudioSubmissionMock.mockResolvedValue({
            submission_id: "submission-1",
            unit_id: "unit-1",
            user_id: "user-1",
            user_name: "张三",
            user_email: "zhangsan@example.com",
            user_department: "销售一部",
            purpose: "ppt_pitch",
            original_filename: "ppt.wav",
            content_type: "audio/wav",
            size_bytes: 2048,
            storage_key: "sales-trainer/audio/ppt.wav",
            file_hash: "file-hash",
            duration_seconds: 90,
            source_page: "sales_trainer_audio_upload",
            confirmed_material_version_id: null,
            confirmed_material_at: null,
            material_snapshot: null,
            score_scheme_snapshot: null,
            task_brief_snapshot: null,
            path_key: "newcomer_training_path_v1",
            path_revision_id: "path-revision-1",
            path_revision_no: 1,
            module_key: "ppt_explanation",
            legacy_snapshot_only: false,
            status: "scored",
            error_code: null,
            error_message: null,
            created_at: "2026-06-04T00:00:00Z",
            updated_at: "2026-06-04T00:01:00Z",
            transcript: {
                transcript_id: "transcript-1",
                provider: "dashscope",
                transcript_text: "大家好，下面介绍产品。",
                raw_payload: null,
                started_at: null,
                completed_at: null,
                created_at: "2026-06-04T00:01:00Z",
            },
            score_result: {
                score_id: "score-1",
                submission_id: "submission-1",
                prompt_id: "prompt-1",
                prompt_version: 1,
                prompt_hash: "source-prompt-hash",
                deucate_model: "fake-deucate",
                transcript_snapshot: "大家好，下面介绍产品。",
                total_score: 88,
                passed: true,
                summary: "表达清楚。",
                strengths: ["结构完整"],
                improvements: [],
                dimension_scores: { structure: 88 },
                raw_response: { total_score: 88 },
                error_code: null,
                error_message: null,
                latency_ms: 12,
                created_at: "2026-06-04T00:02:00Z",
            },
        });
        previewAudioSubmissionRegradeMock.mockResolvedValue({
            target_type: "audio_submission",
            target_id: "submission-1",
            target_revision_id: "prompt-revision-2",
            impact_scope: {
                record_count: 1,
                affected_submission_ids: ["submission-1"],
                source_score_result_ids: ["score-1"],
                future_records_changed: false,
                history_overwrite: false,
                requires_reason: true,
            },
            before_snapshot: {
                total_score: 88,
                prompt_hash: "source-prompt-hash",
            },
            after_snapshot: {
                total_score: 42,
                prompt_hash: "target-prompt-hash",
            },
        });
        runAudioSubmissionRegradeMock.mockResolvedValue({
            regrade_run_id: "run-1",
            target_type: "audio_submission",
            target_id: "submission-1",
            target_revision_id: "prompt-revision-2",
            status: "completed",
            reason: "评分 prompt 发布新版后追加重评记录",
            impact_scope: {
                record_count: 1,
                affected_submission_ids: ["submission-1"],
                source_score_result_ids: ["score-1"],
                future_records_changed: false,
                history_overwrite: false,
                requires_reason: true,
            },
            before_snapshot: {
                total_score: 88,
                prompt_hash: "source-prompt-hash",
            },
            after_snapshot: {
                total_score: 42,
                prompt_hash: "target-prompt-hash",
            },
            trace_id: "trace-audio-regrade-1",
            created_at: "2026-06-04T00:03:00Z",
        });
    });

    it("previews and runs append-only audio regrade from the submission detail page", async () => {
        render(<SalesTrainerAudioSubmissionDetailPage />);

        expect(await screen.findByText("ppt.wav")).toBeTruthy();
        expect(await screen.findByText("重新评分历史记录")).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "预览重评影响" }));

        await waitFor(() => {
            expect(previewAudioSubmissionRegradeMock).toHaveBeenCalledWith("submission-1", {});
        });
        expect(screen.getByText("1 条历史记录")).toBeTruthy();
        expect(screen.getAllByText("88").length).toBeGreaterThanOrEqual(2);
        expect(screen.getByText("42")).toBeTruthy();

        fireEvent.change(screen.getByLabelText("重评原因"), {
            target: { value: "评分 prompt 发布新版后追加重评记录" },
        });
        fireEvent.click(screen.getByRole("button", { name: "确认重评" }));

        await waitFor(() => {
            expect(runAudioSubmissionRegradeMock).toHaveBeenCalledWith("submission-1", {
                target_revision_id: "prompt-revision-2",
                reason: "评分 prompt 发布新版后追加重评记录",
            });
        });
        expect(await screen.findByText(/已生成录音重评记录，追踪号 trace-audio-regrade-1/)).toBeTruthy();
    });
});
