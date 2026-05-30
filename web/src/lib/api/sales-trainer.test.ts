import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";

const fetchMock = vi.fn();

describe("api.salesTrainer facade", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("loads learner sales-trainer units through the central facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    items: [
                        {
                            unit_id: "unit-1",
                            name: "首轮问答",
                            description: "做题训练",
                            unit_type: "quiz",
                            config: {},
                            status: "published",
                            created_by: "admin-1",
                            updated_by: "admin-1",
                            created_at: "2026-05-28T00:00:00Z",
                            updated_at: "2026-05-28T00:00:00Z",
                            questions: [],
                        },
                    ],
                    total: 1,
                },
            }),
        });

        const result = await api.salesTrainer.listUnits();

        expect(result.items[0].unit_id).toBe("unit-1");
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/sales-trainer/units"),
            expect.any(Object),
        );
    });

    it("loads learner goal-oriented sales-trainer paths through the central facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    items: [
                        {
                            path_key: "new_seller",
                            title: "新人销售闯关",
                            goal_title: "掌握首次客户沟通",
                            total_levels: 1,
                            completed_levels: 0,
                            current_level_id: "unit-1",
                            next_level_id: "unit-1",
                            levels: [],
                        },
                    ],
                    total: 1,
                },
            }),
        });

        const result = await api.salesTrainer.listPaths();

        expect(result.items[0].path_key).toBe("new_seller");
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/sales-trainer/paths"),
            expect.any(Object),
        );
    });

    it("submits quiz attempts through the central facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    attempt_id: "attempt-1",
                    unit_id: "unit-1",
                    user_id: "user-1",
                    total_score: 80,
                    max_score: 100,
                    passed: true,
                    status: "scored",
                    submitted_at: "2026-05-28T00:00:00Z",
                    answers: [],
                },
            }),
        });

        await api.salesTrainer.submitQuizAttempt({
            unit_id: "unit-1",
            answers: [{ question_id: "question-1", answer_payload: "A" }],
        });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/sales-trainer/quiz-attempts"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    unit_id: "unit-1",
                    answers: [{ question_id: "question-1", answer_payload: "A" }],
                }),
            }),
        );
    });

    it("uploads learner audio without adding a fixed duration field", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    submission_id: "submission-1",
                    unit_id: "unit-2",
                    user_id: "user-1",
                    purpose: "general_audio_scoring",
                    original_filename: "pitch.wav",
                    content_type: "audio/wav",
                    size_bytes: 1234,
                    storage_key: "private.wav",
                    file_hash: null,
                    duration_seconds: null,
                    source_page: "sales_trainer_audio_upload",
                    status: "uploaded",
                    error_code: null,
                    error_message: null,
                    created_at: "2026-05-28T00:00:00Z",
                    updated_at: "2026-05-28T00:00:00Z",
                    transcript: null,
                    score_result: null,
                },
            }),
        });

        await api.salesTrainer.uploadAudioSubmission({
            unit_id: "unit-2",
            file: new File(["audio"], "pitch.wav", { type: "audio/wav" }),
            source_page: "sales_trainer_audio_upload",
        });

        const body = fetchMock.mock.calls[0][1].body as FormData;
        expect(body.get("unit_id")).toBe("unit-2");
        expect(body.get("source_page")).toBe("sales_trainer_audio_upload");
        expect(body.get("duration_seconds")).toBeNull();
    });

    it("supports presigned upload registration through the central facade", async () => {
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    upload_url: "local://sales-trainer/audio/user/audio.wav",
                    storage_key: "sales-trainer/audio/user/audio.wav",
                    expires_at: "2026-05-28T00:15:00Z",
                    content_type: "audio/wav",
                    storage_backend: "local",
                },
            }),
        }).mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    submission_id: "submission-1",
                    unit_id: "unit-2",
                    user_id: "user-1",
                    purpose: "ppt_pitch",
                    original_filename: "pitch.wav",
                    content_type: "audio/wav",
                    size_bytes: 1234,
                    storage_key: "sales-trainer/audio/user/audio.wav",
                    file_hash: null,
                    duration_seconds: null,
                    source_page: "sales_trainer_upload_url",
                    status: "uploaded",
                    error_code: null,
                    error_message: null,
                    created_at: "2026-05-28T00:00:00Z",
                    updated_at: "2026-05-28T00:00:00Z",
                    transcript: null,
                    score_result: null,
                },
            }),
        });

        await api.salesTrainer.getAudioUploadUrl({
            filename: "pitch.wav",
            content_type: "audio/wav",
        });
        await api.salesTrainer.registerAudioSubmission({
            unit_id: "unit-2",
            purpose: "ppt_pitch",
            original_filename: "pitch.wav",
            content_type: "audio/wav",
            size_bytes: 1234,
            storage_key: "sales-trainer/audio/user/audio.wav",
            source_page: "sales_trainer_upload_url",
        });

        expect(fetchMock).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining("/sales-trainer/audio-submissions/upload-url"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    filename: "pitch.wav",
                    content_type: "audio/wav",
                }),
            }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining("/sales-trainer/audio-submissions"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    unit_id: "unit-2",
                    purpose: "ppt_pitch",
                    original_filename: "pitch.wav",
                    content_type: "audio/wav",
                    size_bytes: 1234,
                    storage_key: "sales-trainer/audio/user/audio.wav",
                    source_page: "sales_trainer_upload_url",
                }),
            }),
        );
    });

    it("falls back to multipart upload when presign reports local storage", async () => {
        const file = new File(["audio"], "pitch.wav", { type: "audio/wav" });
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    upload_url: "local://sales-trainer/audio/user/audio.wav",
                    storage_key: "sales-trainer/audio/user/audio.wav",
                    expires_at: "2026-05-28T00:15:00Z",
                    content_type: "audio/wav",
                    storage_backend: "local",
                },
            }),
        }).mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    submission_id: "submission-local",
                    unit_id: "unit-2",
                    user_id: "user-1",
                    purpose: "ppt_pitch",
                    original_filename: "pitch.wav",
                    content_type: "audio/wav",
                    size_bytes: 5,
                    storage_key: "sales-trainer/audio/user/audio.wav",
                    file_hash: null,
                    duration_seconds: null,
                    source_page: "sales_trainer_audio_upload",
                    status: "uploaded",
                    error_code: null,
                    error_message: null,
                    created_at: "2026-05-28T00:00:00Z",
                    updated_at: "2026-05-28T00:00:00Z",
                    transcript: null,
                    score_result: null,
                },
            }),
        });

        await api.salesTrainer.uploadAudioSubmissionDirect({
            file,
            unit_id: "unit-2",
            purpose: "ppt_pitch",
            source_page: "sales_trainer_audio_upload",
        });

        expect(fetchMock).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining("/sales-trainer/audio-submissions/upload-url"),
            expect.objectContaining({ method: "POST" }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining("/sales-trainer/audio-submissions/upload"),
            expect.objectContaining({ method: "POST" }),
        );
        const body = fetchMock.mock.calls[1][1].body as FormData;
        expect(body.get("file")).toBe(file);
        expect(body.get("unit_id")).toBe("unit-2");
        expect(body.get("purpose")).toBe("ppt_pitch");
        expect(body.get("source_page")).toBe("sales_trainer_audio_upload");
    });

    it("uploads to object storage before registering non-local audio submissions", async () => {
        const file = new File(["audio"], "pitch.wav", { type: "audio/wav" });
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    upload_url: "https://cos.example.com/sales-trainer/audio/user/audio.wav",
                    storage_key: "cos://sales-trainer/audio/user/audio.wav",
                    expires_at: "2026-05-28T00:15:00Z",
                    content_type: "audio/wav",
                    storage_backend: "cos",
                },
            }),
        }).mockResolvedValueOnce({
            ok: true,
            text: async () => "",
        }).mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    submission_id: "submission-cos",
                    unit_id: "unit-2",
                    user_id: "user-1",
                    purpose: "ppt_pitch",
                    original_filename: "pitch.wav",
                    content_type: "audio/wav",
                    size_bytes: 5,
                    storage_key: "cos://sales-trainer/audio/user/audio.wav",
                    file_hash: null,
                    duration_seconds: null,
                    source_page: "sales_trainer_audio_upload",
                    status: "uploaded",
                    error_code: null,
                    error_message: null,
                    created_at: "2026-05-28T00:00:00Z",
                    updated_at: "2026-05-28T00:00:00Z",
                    transcript: null,
                    score_result: null,
                },
            }),
        });

        await api.salesTrainer.uploadAudioSubmissionDirect({
            file,
            unit_id: "unit-2",
            purpose: "ppt_pitch",
            source_page: "sales_trainer_audio_upload",
        });

        expect(fetchMock).toHaveBeenNthCalledWith(
            2,
            "https://cos.example.com/sales-trainer/audio/user/audio.wav",
            expect.objectContaining({
                method: "PUT",
                body: file,
                headers: { "Content-Type": "audio/wav" },
            }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            3,
            expect.stringContaining("/sales-trainer/audio-submissions"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    unit_id: "unit-2",
                    purpose: "ppt_pitch",
                    original_filename: "pitch.wav",
                    content_type: "audio/wav",
                    size_bytes: file.size,
                    storage_key: "cos://sales-trainer/audio/user/audio.wav",
                    source_page: "sales_trainer_audio_upload",
                    auto_process: true,
                }),
            }),
        );
    });

    it("falls back to multipart upload when browser object-storage PUT is blocked", async () => {
        const file = new File(["audio"], "pitch.wav", { type: "audio/wav" });
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    upload_url: "https://cos.example.com/sales-trainer/audio/user/audio.wav",
                    storage_key: "cos://sales-trainer/audio/user/audio.wav",
                    expires_at: "2026-05-28T00:15:00Z",
                    content_type: "audio/wav",
                    storage_backend: "cos",
                },
            }),
        }).mockRejectedValueOnce(new TypeError("Failed to fetch"))
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: {
                        submission_id: "submission-fallback",
                        unit_id: "unit-2",
                        user_id: "user-1",
                        purpose: "ppt_pitch",
                        original_filename: "pitch.wav",
                        content_type: "audio/wav",
                        size_bytes: 5,
                        storage_key: "cos://sales-trainer/audio/user/audio.wav",
                        file_hash: null,
                        duration_seconds: null,
                        source_page: "sales_trainer_audio_upload",
                        status: "uploaded",
                        error_code: null,
                        error_message: null,
                        created_at: "2026-05-28T00:00:00Z",
                        updated_at: "2026-05-28T00:00:00Z",
                        transcript: null,
                        score_result: null,
                    },
                }),
            });

        const result = await api.salesTrainer.uploadAudioSubmissionDirect({
            file,
            unit_id: "unit-2",
            purpose: "ppt_pitch",
            source_page: "sales_trainer_audio_upload",
        });

        expect(result.submission_id).toBe("submission-fallback");
        expect(fetchMock).toHaveBeenCalledTimes(3);
        expect(fetchMock).toHaveBeenNthCalledWith(
            3,
            expect.stringContaining("/sales-trainer/audio-submissions/upload"),
            expect.objectContaining({ method: "POST" }),
        );
        const body = fetchMock.mock.calls[2][1].body as FormData;
        expect(body.get("file")).toBe(file);
        expect(body.get("unit_id")).toBe("unit-2");
        expect(body.get("purpose")).toBe("ppt_pitch");
        expect(body.get("source_page")).toBe("sales_trainer_audio_upload");
    });

    it("returns an actionable error when object-storage PUT and multipart fallback both fail", async () => {
        const file = new File(["audio"], "pitch.wav", { type: "audio/wav" });
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    upload_url: "https://cos.example.com/sales-trainer/audio/user/audio.wav",
                    storage_key: "cos://sales-trainer/audio/user/audio.wav",
                    expires_at: "2026-05-28T00:15:00Z",
                    content_type: "audio/wav",
                    storage_backend: "cos",
                },
            }),
        }).mockRejectedValueOnce(new TypeError("Failed to fetch"))
            .mockResolvedValueOnce({
                ok: false,
                status: 413,
                json: async () => ({
                    success: false,
                    error: "[AUDIO_FILE_TOO_LARGE]",
                    message: "音频文件超过大小限制。",
                }),
            });

        await expect(api.salesTrainer.uploadAudioSubmissionDirect({
            file,
            unit_id: "unit-2",
            purpose: "ppt_pitch",
            source_page: "sales_trainer_audio_upload",
        })).rejects.toThrow(
            "对象存储直传失败，请检查 COS/OSS 跨域 CORS 配置。 已自动尝试后端中转上传但仍失败：音频文件超过大小限制。",
        );
    });

    it("builds authorized learner and admin audio URLs from the facade helpers", () => {
        expect(api.salesTrainer.getAudioSubmissionFileUrl("submission-1")).toContain(
            "/sales-trainer/audio-submissions/submission-1/file",
        );
        expect(api.admin.salesTrainer.getAudioSubmissionFileUrl("submission-1")).toContain(
            "/admin/sales-trainer/audio-submissions/submission-1/file",
        );
    });

    it("loads admin quiz attempts through the central facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    items: [
                        {
                            attempt_id: "attempt-1",
                            unit_id: "unit-1",
                            user_id: "user-1",
                            user_name: "张三",
                            user_email: "zhangsan@example.com",
                            user_department: "销售一部",
                            total_score: 18,
                            max_score: 20,
                            passed: true,
                            status: "scored",
                            submitted_at: "2026-05-28T00:00:00Z",
                            answers: [],
                        },
                    ],
                    total: 1,
                },
            }),
        });

        const result = await api.admin.salesTrainer.listQuizAttempts({
            user_id: "user-1",
            unit_id: "unit-1",
            limit: 100,
        });

        expect(result.items[0].attempt_id).toBe("attempt-1");
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/sales-trainer/quiz-attempts?user_id=user-1&unit_id=unit-1&limit=100"),
            expect.any(Object),
        );
    });

    it("loads an admin quiz attempt detail through the central facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    attempt_id: "attempt-1",
                    unit_id: "unit-1",
                    user_id: "user-1",
                    total_score: 18,
                    max_score: 20,
                    passed: true,
                    status: "scored",
                    submitted_at: "2026-05-28T00:00:00Z",
                    answers: [],
                },
            }),
        });

        const result = await api.admin.salesTrainer.getQuizAttempt("attempt-1");

        expect(result.attempt_id).toBe("attempt-1");
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/sales-trainer/quiz-attempts/attempt-1"),
            expect.any(Object),
        );
    });
});
