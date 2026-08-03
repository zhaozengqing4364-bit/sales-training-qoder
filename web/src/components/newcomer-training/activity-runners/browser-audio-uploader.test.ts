import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
    FoundationActivityWorkspace,
    FoundationAudioUploadSession,
} from "@/lib/api/types/newcomer-training";

import type { BrowserAudioDraft } from "./browser-audio-draft-store";
import { uploadBrowserAudioDraft } from "./browser-audio-uploader";

const mocks = vi.hoisted(() => ({
    buildManifest: vi.fn(),
    deleteDraft: vi.fn(),
    executeCommand: vi.fn(),
    readPart: vi.fn(),
}));

vi.mock("./browser-audio-draft-store", () => ({
    buildBrowserAudioUploadManifest: mocks.buildManifest,
    deleteBrowserAudioDraft: mocks.deleteDraft,
    readBrowserAudioUploadPart: mocks.readPart,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            newcomerTraining: {
                ...actual.api.newcomerTraining,
                executeCommand: mocks.executeCommand,
            },
        },
    };
});

const draft: BrowserAudioDraft = {
    draftId: "draft-1",
    scopeKey: "scope-1",
    activityId: "audio-1",
    segmentId: "primary",
    source: "browser",
    filename: "讲解.webm",
    mimeType: "audio/webm;codecs=opus",
    state: "ready",
    durationSeconds: 65,
    sizeBytes: 8,
    chunkCount: 2,
    createdAt: 1,
    updatedAt: 2,
    expiresAt: Date.now() + 60_000,
};

function uploadSession(uploadedParts = 0, url = "/api/v1/upload/part"): FoundationAudioUploadSession {
    return {
        upload_session_id: "upload-1",
        submission_id: "submission-1",
        state: "uploading",
        expires_at: new Date(Date.now() + 60_000).toISOString(),
        part_size_bytes: 4,
        expected_part_count: 2,
        uploaded_part_count: uploadedParts,
        parts: [1, 2].map((partNumber) => ({
            part_number: partNumber,
            upload_url: `${url}-${partNumber}`,
            required_headers: {
                "Content-Type": "audio/webm",
                "X-Audio-Sha256": String(partNumber).repeat(64),
            },
            uploaded: partNumber <= uploadedParts,
            size_bytes: 4,
            sha256: String(partNumber).repeat(64),
        })),
    };
}

function workspace(activeUpload: FoundationAudioUploadSession | null, version = 2): FoundationActivityWorkspace {
    return {
        contract_version: "activity_workspace_v1",
        generated_at: new Date().toISOString(),
        data_freshness: "fresh",
        capabilities: ["execute_activity"],
        enrollment_version: 1,
        activity: {
            id: "audio-1",
            type: "audio_assessment",
            title: "产品讲解",
            objective: "完成讲解",
            why_it_matters: "验证表达",
            steps: ["录音"],
            success_criteria: ["清晰完整"],
            estimated_minutes: 10,
        },
        attempt: {
            attempt_id: "attempt-1",
            organization_id: "org-1",
            enrollment_id: "enrollment-1",
            path_revision_id: "path-1",
            activity_id: "audio-1",
            activity_type: "audio_assessment",
            attempt_no: 1,
            status: "in_progress",
            version: 1,
            task_id: null,
            outcome_id: null,
        },
        runner: {
            kind: "audio_assessment",
            detail_id: "run-1",
            run_id: "run-1",
            status: "in_progress",
            version,
            rules: {
                allowed_recording_modes: ["browser", "file"],
                allowed_content_types: ["audio/webm"],
                max_duration_seconds: 1_800,
                max_size_bytes: 100 * 1024 * 1024,
                part_size_bytes: 4,
                local_draft_ttl_seconds: 3_600,
                language: "zh-CN",
                pass_score: 75,
            },
            segments: [{
                submission_id: "submission-1",
                segment_id: "primary",
                title: "产品讲解",
                prompt: "请完成讲解",
                customer_context: null,
                preparation_hints: [],
                state: activeUpload ? "uploading" : "draft",
                version: 1,
                task_id: null,
                error: null,
                transcript: null,
                quality: null,
                result: null,
            }],
            active_upload: activeUpload,
            result: null,
        },
        task: null,
        outcome: null,
        available_commands: ["create_upload_session", "confirm_upload_part", "finalize_upload", "cancel"],
        recovery: {
            input_preserved: true,
            refresh_on_version_conflict: true,
            retry_from_current_activity: true,
        },
    };
}

describe("uploadBrowserAudioDraft", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        document.cookie = "app_csrf=csrf-audio; path=/";
        mocks.buildManifest.mockResolvedValue({
            manifestSha256: "a".repeat(64),
            parts: [
                { part_number: 1, size_bytes: 4, sha256: "1".repeat(64) },
                { part_number: 2, size_bytes: 4, sha256: "2".repeat(64) },
            ],
        });
        mocks.readPart.mockResolvedValue(new Blob(["part"], { type: "audio/webm" }));
        mocks.deleteDraft.mockResolvedValue(undefined);
        vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));
    });

    it("creates, uploads, confirms and finalizes one bounded part at a time", async () => {
        const created = workspace(uploadSession(0), 3);
        const confirmedOne = workspace(uploadSession(1), 4);
        const confirmedTwo = workspace(uploadSession(2), 5);
        const finalized = workspace(null, 6);
        finalized.task = { task_id: "task-1", state: "processing" };
        mocks.executeCommand
            .mockResolvedValueOnce(created)
            .mockResolvedValueOnce(confirmedOne)
            .mockResolvedValueOnce(confirmedTwo)
            .mockResolvedValueOnce(finalized);

        const result = await uploadBrowserAudioDraft({
            activityId: "audio-1",
            workspace: workspace(null),
            segmentId: "primary",
            draft,
        });

        expect(result.task?.task_id).toBe("task-1");
        expect(mocks.executeCommand.mock.calls.map((call) => call[1].command_type)).toEqual([
            "create_upload_session",
            "confirm_upload_part",
            "confirm_upload_part",
            "finalize_upload",
        ]);
        expect(mocks.readPart).toHaveBeenNthCalledWith(1, "draft-1", 1);
        expect(mocks.readPart).toHaveBeenNthCalledWith(2, "draft-1", 2);
        expect(fetch).toHaveBeenCalledTimes(2);
        const firstOptions = vi.mocked(fetch).mock.calls[0]?.[1];
        expect(firstOptions?.credentials).toBe("include");
        expect(new Headers(firstOptions?.headers).get("X-CSRF-Token")).toBe("csrf-audio");
        expect(mocks.deleteDraft).toHaveBeenCalledWith("draft-1");
    });

    it("resumes only missing cloud parts without sending browser credentials", async () => {
        const cloudUpload = uploadSession(1, "https://storage.example.test/audio");
        const confirmed = workspace(uploadSession(2, "https://storage.example.test/audio"), 4);
        const finalized = workspace(null, 5);
        mocks.executeCommand.mockResolvedValueOnce(confirmed).mockResolvedValueOnce(finalized);

        await uploadBrowserAudioDraft({
            activityId: "audio-1",
            workspace: workspace(cloudUpload, 3),
            segmentId: "primary",
            draft,
        });

        expect(mocks.executeCommand.mock.calls.map((call) => call[1].command_type)).toEqual([
            "confirm_upload_part",
            "finalize_upload",
        ]);
        expect(mocks.readPart).toHaveBeenCalledOnce();
        expect(mocks.readPart).toHaveBeenCalledWith("draft-1", 2);
        const options = vi.mocked(fetch).mock.calls[0]?.[1];
        expect(options?.credentials).toBe("omit");
        expect(new Headers(options?.headers).has("X-CSRF-Token")).toBe(false);
    });

    it("keeps the local draft when direct upload is interrupted", async () => {
        mocks.executeCommand.mockResolvedValueOnce(workspace(uploadSession(0), 3));
        vi.mocked(fetch).mockRejectedValueOnce(new TypeError("offline"));

        await expect(uploadBrowserAudioDraft({
            activityId: "audio-1",
            workspace: workspace(null),
            segmentId: "primary",
            draft,
        })).rejects.toThrow("本地草稿仍已保留");

        expect(mocks.deleteDraft).not.toHaveBeenCalled();
    });
});
