import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
    FoundationActivityWorkspace,
    FoundationAudioRunner,
} from "@/lib/api/types/newcomer-training";
import { toActivityViewModel } from "@/lib/newcomer-training/view-models";

import { AudioAssessmentRunner } from "./audio-assessment-runner";

vi.mock("@/lib/newcomer-training/ux-events", () => ({ trackFoundationUxEvent: vi.fn() }));

const { executeCommandMock, recorderMock, uploadDraftMock } = vi.hoisted(() => ({
    executeCommandMock: vi.fn(),
    uploadDraftMock: vi.fn(),
    recorderMock: {
        state: "idle",
        draft: null as null | {
            draftId: string;
            scopeKey: string;
            activityId: string;
            segmentId: string;
            source: "browser";
            filename: string;
            mimeType: string;
            state: "ready";
            durationSeconds: number;
            sizeBytes: number;
            chunkCount: number;
            createdAt: number;
            updatedAt: number;
            expiresAt: number;
        },
        durationSeconds: 0,
        audioUrl: null as string | null,
        start: vi.fn(),
        pause: vi.fn(),
        resume: vi.fn(),
        stop: vi.fn(),
        finish: vi.fn(),
        reset: vi.fn(),
        preview: vi.fn(),
        importFile: vi.fn(),
        restored: false,
        canResume: false,
        error: null as string | null,
    },
}));

vi.mock("@/hooks/use-current-user", () => ({
    useCurrentUser: () => ({ data: { user_id: "learner-1" } }),
}));

vi.mock("@/lib/api/client", () => ({
    api: { newcomerTraining: { executeCommand: executeCommandMock } },
    getApiErrorMessage: (cause: unknown) => cause instanceof Error ? cause.message : "操作失败",
}));

vi.mock("./browser-audio-uploader", () => ({
    uploadBrowserAudioDraft: uploadDraftMock,
}));

vi.mock("./use-browser-audio-recorder", () => ({
    useBrowserAudioRecorder: () => recorderMock,
}));

function segment(
    segmentId: string,
    title: string,
    state: string,
): FoundationAudioRunner["segments"][number] {
    return {
        submission_id: `submission-${segmentId}`,
        segment_id: segmentId,
        title,
        prompt: `请完成${title}。`,
        customer_context: "客户正在评估首次合作。",
        preparation_hints: ["先确认客户目标", "用事实说明价值"],
        state,
        version: 2,
        task_id: state === "transcribing" ? "task-1" : null,
        error: null,
        transcript: null,
        quality: null,
        result: null,
    };
}

function audioWorkspace(input: {
    kind?: "audio_assessment" | "assignment";
    state?: string;
    started?: boolean;
    segments?: FoundationAudioRunner["segments"];
} = {}): FoundationActivityWorkspace {
    const kind = input.kind ?? "audio_assessment";
    const started = input.started ?? true;
    const segments = input.segments ?? [segment("primary", "产品价值讲解", input.state ?? "draft")];
    return {
        contract_version: "activity_workspace_v1",
        generated_at: "2026-07-17T00:00:00Z",
        data_freshness: "fresh",
        capabilities: ["view_activity", "execute_activity"],
        enrollment_version: 4,
        activity: {
            id: "audio-1",
            type: kind,
            title: kind === "assignment" ? "客户场景回答" : "产品讲解录音",
            objective: "清晰表达产品价值",
            why_it_matters: "帮助新人形成稳定表达",
            steps: [],
            success_criteria: [],
            estimated_minutes: 20,
        },
        attempt: started ? {
            attempt_id: "attempt-1",
            organization_id: "org-1",
            enrollment_id: "enrollment-1",
            path_revision_id: "path-r1",
            activity_id: "audio-1",
            activity_type: kind,
            attempt_no: 1,
            status: "in_progress",
            version: 2,
            task_id: null,
            outcome_id: null,
        } : null,
        runner: {
            kind,
            detail_id: started ? "run-1" : "not-started",
            run_id: "run-1",
            status: input.state ?? "draft",
            version: 2,
            rules: {
                allowed_recording_modes: ["browser", "file"],
                allowed_content_types: ["audio/wav", "audio/webm"],
                max_duration_seconds: 1_800,
                max_size_bytes: 100 * 1024 * 1024,
                part_size_bytes: 5 * 1024 * 1024,
                local_draft_ttl_seconds: 604_800,
                language: "zh-CN",
                pass_score: 80,
            },
            segments,
            active_upload: null,
            result: null,
        },
        task: null,
        outcome: null,
        available_commands: started ? ["create_upload_session", "cancel"] : ["start"],
        recovery: {
            input_preserved: true,
            refresh_on_version_conflict: true,
            retry_from_current_activity: true,
        },
    };
}

describe("AudioAssessmentRunner", () => {
    beforeEach(() => {
        executeCommandMock.mockReset();
        uploadDraftMock.mockReset();
        recorderMock.state = "idle";
        recorderMock.draft = null;
        recorderMock.durationSeconds = 0;
        recorderMock.audioUrl = null;
        recorderMock.restored = false;
        recorderMock.canResume = false;
        recorderMock.error = null;
        Object.values(recorderMock).forEach((value) => {
            if (typeof value === "function" && "mockReset" in value) value.mockReset();
        });
    });

    it("starts the activity against the frozen enrollment version", async () => {
        const current = audioWorkspace({ started: false });
        executeCommandMock.mockResolvedValue(audioWorkspace());
        render(<AudioAssessmentRunner detail={toActivityViewModel(current)} />);

        fireEvent.click(screen.getByRole("button", { name: "开始录音任务" }));

        await waitFor(() => expect(executeCommandMock).toHaveBeenCalledTimes(1));
        expect(executeCommandMock.mock.calls[0][1]).toMatchObject({
            command_type: "start",
            expected_enrollment_version: 4,
            payload: { relearn_of_detail_id: null },
        });
    });

    it("shows the frozen prompt, configured limits, and truthful local-draft state", () => {
        recorderMock.state = "ready";
        recorderMock.restored = true;
        recorderMock.durationSeconds = 95;
        recorderMock.draft = {
            draftId: "draft-1",
            scopeKey: "scope-1",
            activityId: "audio-1",
            segmentId: "primary",
            source: "browser",
            filename: "产品讲解.webm",
            mimeType: "audio/webm",
            state: "ready",
            durationSeconds: 95,
            sizeBytes: 2_048,
            chunkCount: 2,
            createdAt: 1,
            updatedAt: 2,
            expiresAt: 3,
        };

        render(<AudioAssessmentRunner detail={toActivityViewModel(audioWorkspace())} />);

        expect(screen.getByText("请完成产品价值讲解。")).toBeTruthy();
        expect(screen.getByText(/最长 30 分钟，最大 100.0 MB/)).toBeTruthy();
        expect(screen.getByText("已恢复本地录音草稿")).toBeTruthy();
        expect(screen.getByText("仅保存在此设备，尚未上传。")).toBeTruthy();
    });

    it("keeps the task context visible while durable processing continues", () => {
        render(<AudioAssessmentRunner detail={toActivityViewModel(audioWorkspace({ state: "transcribing" }))} />);

        expect(screen.getByText("请完成产品价值讲解。")).toBeTruthy();
        expect(screen.getAllByText("正在转写内容").length).toBeGreaterThan(0);
        expect(screen.getByText(/可以返回训练路径/)).toBeTruthy();
        expect(screen.getByRole("button", { name: "取消处理" })).toBeTruthy();
    });

    it("requires an accessible confirmation before cancelling durable processing", async () => {
        executeCommandMock.mockResolvedValue(audioWorkspace({ state: "cancelled" }));
        render(<AudioAssessmentRunner detail={toActivityViewModel(audioWorkspace({ state: "transcribing" }))} />);

        fireEvent.click(screen.getByRole("button", { name: "取消处理" }));

        expect(screen.getByRole("heading", { name: "取消当前录音任务？" })).toBeTruthy();
        expect(executeCommandMock).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("button", { name: "取消录音任务" }));

        await waitFor(() => expect(executeCommandMock).toHaveBeenCalledTimes(1));
        expect(executeCommandMock.mock.calls[0][1]).toMatchObject({
            command_type: "cancel",
            expected_attempt_version: 2,
            payload: {},
        });
    });

    it("separates unscorable audio from a failed capability result", () => {
        const unscorable = segment("primary", "产品价值讲解", "needs_review");
        unscorable.quality = {
            scorable: false,
            flags: ["no_speech", "low_asr_confidence"],
            metrics: { speech_ratio: 0.01 },
        };
        unscorable.transcript = {
            text: "（可识别内容较少）",
            confidence: 0.2,
            language: "zh-CN",
            segments: [],
        };

        render(<AudioAssessmentRunner detail={toActivityViewModel(audioWorkspace({ segments: [unscorable] }))} />);

        expect(screen.getByText("这份录音暂时无法评分")).toBeTruthy();
        expect(screen.getByText(/这不是能力未达标，也不会按零分记录/)).toBeTruthy();
        expect(screen.getByRole("button", { name: "结束本次，返回重录" })).toBeTruthy();
        expect(screen.queryByText(/^0(?:\.0)? 分$/)).toBeNull();
        expect(screen.getByText("查看录音文字稿")).toBeTruthy();
    });

    it("gives terminal media failures an explicit re-record path", () => {
        const failed = segment("primary", "产品价值讲解", "failed_terminal");
        failed.error = {
            retryable: false,
            message: "无法识别录音格式，请重新录制或上传受支持的音频。",
            failed_stage: "validation",
        };

        render(<AudioAssessmentRunner detail={toActivityViewModel(audioWorkspace({ segments: [failed] }))} />);

        expect(screen.getByText("这份录音无法继续处理")).toBeTruthy();
        expect(screen.getByText(/当前上传记录已经保留/)).toBeTruthy();
        expect(screen.getByRole("button", { name: "结束本次，重新录制" })).toBeTruthy();
    });

    it("does not replace an active upload when its local draft is missing", () => {
        const workspace = audioWorkspace({ state: "uploading" });
        if (workspace.runner.kind === "audio_assessment" || workspace.runner.kind === "assignment") {
            workspace.runner.active_upload = {
                upload_session_id: "upload-1",
                submission_id: "submission-primary",
                state: "uploading",
                expires_at: "2026-07-18T00:00:00Z",
                part_size_bytes: 5 * 1024 * 1024,
                expected_part_count: 2,
                uploaded_part_count: 1,
                parts: [],
            };
        }

        render(<AudioAssessmentRunner detail={toActivityViewModel(workspace)} />);

        expect(screen.getByText("此设备没有找到待续传的录音草稿")).toBeTruthy();
        expect(screen.getByText(/不能用另一份录音替换当前会话/)).toBeTruthy();
        expect(screen.queryByRole("button", { name: "开始录音" })).toBeNull();
    });

    it("renders dimension scores, transcript evidence, and remediation", () => {
        const completed = segment("primary", "产品价值讲解", "completed");
        completed.transcript = {
            text: "先说明客户目标，再给出对应价值。",
            confidence: 0.94,
            language: "zh-CN",
            segments: [{
                sequence: 1,
                start_ms: 0,
                end_ms: 2_500,
                text: "先说明客户目标，再给出对应价值。",
                confidence: 0.94,
                speaker: null,
            }],
        };
        completed.quality = { scorable: true, flags: [], metrics: { asr_confidence: 0.94 } };
        completed.result = {
            score: 88,
            passed: true,
            dimension_scores: [
                { dimension_key: "structure", label: "表达结构", score: 90 },
                { dimension_key: "internal_accuracy_key", score: 86 },
            ],
            evidence_spans: [{
                dimension_key: "structure",
                segment_sequence: 1,
                quote: "先说明客户目标，再给出对应价值",
                rationale: "表达顺序清晰",
            }],
            missing_points: [],
            feedback: ["价值说明清楚"],
            remediation: ["补练量化收益表达"],
            critical_flags: [],
            uncertainty: 0.08,
        };

        render(<AudioAssessmentRunner detail={toActivityViewModel(audioWorkspace({ segments: [completed] }))} />);

        expect(screen.getByText("表达结构")).toBeTruthy();
        expect(screen.getByText("评分维度 2")).toBeTruthy();
        expect(screen.queryByText("internal_accuracy_key")).toBeNull();
        expect(screen.getAllByText(/先说明客户目标，再给出对应价值/)).toHaveLength(2);
        expect(screen.getByText("补练量化收益表达")).toBeTruthy();
        expect(screen.getByText("查看录音文字稿")).toBeTruthy();
        expect(screen.getByText("先说明客户目标，再给出对应价值。")).toBeTruthy();
        expect(screen.getByText(/转写语言：zh-CN · 置信度 94%/)).toBeTruthy();
    });

    it("advances assignment segments sequentially", () => {
        render(<AudioAssessmentRunner detail={toActivityViewModel(audioWorkspace({
            kind: "assignment",
            segments: [
                segment("discovery", "需求澄清", "completed"),
                segment("objection", "异议回应", "draft"),
                segment("commitment", "推进承诺", "draft"),
            ],
        }))} />);

        expect(screen.getByText("场景回答进度 1 / 3")).toBeTruthy();
        expect(screen.getByText("第 2 段")).toBeTruthy();
        expect(screen.getByRole("heading", { name: "异议回应" })).toBeTruthy();
    });
});
