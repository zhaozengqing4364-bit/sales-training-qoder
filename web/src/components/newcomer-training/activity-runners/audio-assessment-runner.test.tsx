import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/lib/api/client";
import type { ActivityDetailResponse } from "@/lib/api/types/newcomer-training";
import { AudioAssessmentRunner } from "./audio-assessment-runner";

const { startRecorder, submitAudio } = vi.hoisted(() => ({
    startRecorder: vi.fn(),
    submitAudio: vi.fn(),
}));

vi.mock("./use-browser-audio-recorder", () => ({
    useBrowserAudioRecorder: () => ({
        state: "idle",
        durationSeconds: 0,
        audioFile: null,
        audioUrl: null,
        start: startRecorder,
        stop: vi.fn(),
        reset: vi.fn(),
        error: null,
    }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>(
        "@/lib/api/client",
    );
    return {
        ...actual,
        api: {
            ...actual.api,
            salesTrainer: {
                ...actual.api.salesTrainer,
                getMaterialVersionFileUrl: (versionId: string) =>
                    `/api/material-versions/${versionId}/file`,
            },
            newcomerTraining: {
                ...actual.api.newcomerTraining,
                submitAudio,
            },
        },
    };
});

function audioDetail(exampleTranscript: string | null = "先说客户问题，再讲方案价值。"):
    ActivityDetailResponse {
    return {
        enrollment_id: "enrollment-1",
        path_revision_id: "path-revision-1",
        phase_id: "phase-1",
        module_id: "module-1",
        activity: {
            activity_id: "ppt-intro-audio",
            activity_type: "audio_assessment",
            title: "PPT 讲解录音",
            description: null,
            objective: "完成一次清晰、完整的 PPT 讲解",
            why_it_matters: null,
            steps: [],
            success_criteria: [],
            primary_action_label: null,
            required: true,
            estimated_minutes: 15,
            status: "not_started",
            completed: false,
            passed: null,
            score: null,
            max_score: null,
            locked: false,
            lock_reason: null,
            action_key: "record_audio",
            is_primary_next_action: true,
        },
        runner: {
            type: "audio_assessment",
            material_id: "material-1",
            material_version_id: "material-version-v3",
            material_title: "新人销售 PPT",
            material_version_label: "v3.0",
            material_file_name: "新人销售标准讲解-v3.pptx",
            material_content_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            scoring_rubric_revision_id: "rubric-revision-2",
            scoring_rubric_revision_no: 2,
            scoring_rubric_title: "PPT 标准讲解评分",
            scoring_focuses: [
                { label: "讲解结构", description: "开场、方案和下一步衔接自然", weight: 40 },
                { label: "客户语言", description: null, weight: null },
            ],
            example_transcript: exampleTranscript,
            pass_score: 80,
            max_attempts: 3,
        },
    };
}

describe("AudioAssessmentRunner", () => {
    beforeEach(() => {
        startRecorder.mockReset();
        submitAudio.mockReset();
    });

    it("keeps the preparation material, scoring focuses and example in the current page", async () => {
        const user = userEvent.setup();
        render(<AudioAssessmentRunner detail={audioDetail()} />);

        expect(screen.getByRole("heading", { name: "录音前，先看完这 3 项" })).toBeTruthy();
        expect(screen.getByText("新人销售标准讲解-v3.pptx")).toBeTruthy();
        expect(screen.getByText("当前使用 v3.0")).toBeTruthy();
        expect(screen.getByText("讲解结构")).toBeTruthy();
        expect(screen.getByText("开场、方案和下一步衔接自然")).toBeTruthy();
        expect(screen.getByText("先说客户问题，再讲方案价值。")).toBeTruthy();
        const originalFileLink = screen.getByRole("link", { name: "在新标签页查看 PPT 原文件" });
        expect(originalFileLink.getAttribute("target")).toBe("_blank");
        expect(originalFileLink.getAttribute("rel")).toContain("noopener");

        const startButton = screen.getByRole("button", { name: "开始录音" });
        expect(startButton.hasAttribute("disabled")).toBe(true);
        await user.click(screen.getByRole("checkbox", { name: "我已看过材料、评分重点和讲解示例" }));
        expect(startButton.hasAttribute("disabled")).toBe(false);
        await user.click(startButton);
        expect(startRecorder).toHaveBeenCalledOnce();
    });

    it("labels the legacy fallback as a system reference instead of an approved example", () => {
        render(<AudioAssessmentRunner detail={audioDetail(null)} />);

        expect(screen.getByRole("heading", { name: "参考表达结构（系统默认）" })).toBeTruthy();
        expect(screen.queryByRole("heading", { name: "优秀讲解示例（文字版）" })).toBeNull();
        expect(screen.getByText(/旧版任务未配置专属示例/)).toBeTruthy();
    });

    it("submits the exact material and scoring rubric revisions shown to the learner", async () => {
        const detail = audioDetail();
        submitAudio.mockResolvedValue(detail);
        const user = userEvent.setup();
        render(<AudioAssessmentRunner detail={detail} />);

        await user.click(screen.getByRole("checkbox", { name: "我已看过材料、评分重点和讲解示例" }));
        const input = screen.getByLabelText("选择录音文件");
        const file = new File(["audio"], "讲解.webm", { type: "audio/webm" });
        await user.upload(input, file);
        await user.click(screen.getByRole("button", { name: "提交录音评分" }));

        await waitFor(() => expect(submitAudio).toHaveBeenCalledOnce());
        expect(submitAudio).toHaveBeenCalledWith(
            "ppt-intro-audio",
            expect.objectContaining({
                file,
                confirmed_material_version_id: "material-version-v3",
                confirmed_scoring_rubric_revision_id: "rubric-revision-2",
            }),
        );
    });

    it("reuses the same idempotency token when an uncertain submit is retried", async () => {
        const detail = audioDetail();
        submitAudio
            .mockRejectedValueOnce(new Error("response lost"))
            .mockResolvedValueOnce(detail);
        const user = userEvent.setup();
        render(<AudioAssessmentRunner detail={detail} />);

        await user.click(screen.getByRole("checkbox", { name: "我已看过材料、评分重点和讲解示例" }));
        await user.upload(
            screen.getByLabelText("选择录音文件"),
            new File(["audio"], "讲解.webm", { type: "audio/webm" }),
        );
        await user.click(screen.getByRole("button", { name: "提交录音评分" }));
        expect(await screen.findByRole("alert")).toBeTruthy();
        await user.click(screen.getByRole("button", { name: "提交录音评分" }));

        await waitFor(() => expect(submitAudio).toHaveBeenCalledTimes(2));
        expect(submitAudio.mock.calls[1][1].client_token).toBe(
            submitAudio.mock.calls[0][1].client_token,
        );
    });

    it("shows the backend business message instead of a vaguer fallback", async () => {
        submitAudio.mockRejectedValueOnce(
            new ApiRequestError({
                status: 409,
                errorCode: "[NEWCOMER_AUDIO_RUBRIC_NOT_PUBLISHED]",
                message: "录音评分标准尚未发布，请重新选择或新建评分标准。",
                traceId: "trace-audio-1",
            }),
        );
        const user = userEvent.setup();
        render(<AudioAssessmentRunner detail={audioDetail()} />);

        await user.click(screen.getByRole("checkbox", { name: "我已看过材料、评分重点和讲解示例" }));
        await user.upload(
            screen.getByLabelText("选择录音文件"),
            new File(["audio"], "讲解.webm", { type: "audio/webm" }),
        );
        await user.click(screen.getByRole("button", { name: "提交录音评分" }));

        const alert = await screen.findByRole("alert");
        expect(alert.textContent).toContain(
            "录音评分标准尚未发布，请重新选择或新建评分标准。",
        );
        expect(alert.textContent).toContain("trace-audio-1");
    });
});
