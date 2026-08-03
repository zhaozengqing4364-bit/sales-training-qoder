import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BrowserAudioDraft } from "./browser-audio-draft-store";
import { useBrowserAudioRecorder } from "./use-browser-audio-recorder";

const mocks = vi.hoisted(() => ({
    appendChunk: vi.fn(),
    cleanup: vi.fn(),
    createDraft: vi.fn(),
    createFromFile: vi.fn(),
    createPreview: vi.fn(),
    deleteDraft: vi.fn(),
    loadDraft: vi.fn(),
    updateDraft: vi.fn(),
}));

vi.mock("./browser-audio-draft-store", () => ({
    appendBrowserAudioChunk: mocks.appendChunk,
    browserAudioDraftScope: (ownerId: string, activityId: string, segmentId: string) =>
        `${ownerId}:${activityId}:${segmentId}`,
    cleanupExpiredBrowserAudioDrafts: mocks.cleanup,
    createBrowserAudioDraft: mocks.createDraft,
    createBrowserAudioDraftFromFile: mocks.createFromFile,
    createBrowserAudioPreviewBlob: mocks.createPreview,
    deleteBrowserAudioDraft: mocks.deleteDraft,
    loadBrowserAudioDraft: mocks.loadDraft,
    updateBrowserAudioDraft: mocks.updateDraft,
}));

class FakeMediaRecorder {
    static instances: FakeMediaRecorder[] = [];
    static isTypeSupported = () => true;
    state: RecordingState = "inactive";
    mimeType = "audio/webm";
    ondataavailable: ((event: { data: Blob }) => void) | null = null;
    onstop: (() => void) | null = null;

    constructor(stream: MediaStream, options?: MediaRecorderOptions) {
        void stream;
        void options;
        FakeMediaRecorder.instances.push(this);
    }
    start() { this.state = "recording"; }
    pause() { this.state = "paused"; }
    resume() { this.state = "recording"; }
    requestData() { this.ondataavailable?.({ data: new Blob(["audio"], { type: this.mimeType }) }); }
    stop() {
        if (this.state === "inactive") return;
        this.state = "inactive";
        this.ondataavailable?.({ data: new Blob(["final"], { type: this.mimeType }) });
        this.onstop?.();
    }
}

function draft(changes: Partial<BrowserAudioDraft> = {}): BrowserAudioDraft {
    return {
        draftId: "draft-1",
        scopeKey: "user-1:activity-1:primary",
        activityId: "activity-1",
        segmentId: "primary",
        source: "browser",
        filename: "讲解录音.webm",
        mimeType: "audio/webm",
        state: "recording",
        durationSeconds: 0,
        sizeBytes: 0,
        chunkCount: 0,
        createdAt: 1,
        updatedAt: 1,
        expiresAt: Date.now() + 60_000,
        ...changes,
    };
}

describe("useBrowserAudioRecorder", () => {
    const stopTrack = vi.fn();
    let currentDraft: BrowserAudioDraft;

    beforeEach(() => {
        vi.clearAllMocks();
        FakeMediaRecorder.instances = [];
        currentDraft = draft();
        mocks.cleanup.mockResolvedValue(0);
        mocks.loadDraft.mockResolvedValue(null);
        mocks.createDraft.mockImplementation(async () => currentDraft);
        mocks.appendChunk.mockImplementation(async ({ blob, durationSeconds }: { blob: Blob; durationSeconds: number }) => {
            currentDraft = {
                ...currentDraft,
                sizeBytes: currentDraft.sizeBytes + blob.size,
                chunkCount: currentDraft.chunkCount + 1,
                durationSeconds,
            };
            return currentDraft;
        });
        mocks.updateDraft.mockImplementation(async (_id: string, changes: Partial<BrowserAudioDraft>) => {
            currentDraft = { ...currentDraft, ...changes };
            return currentDraft;
        });
        mocks.deleteDraft.mockResolvedValue(undefined);
        mocks.createPreview.mockResolvedValue(new Blob(["preview"], { type: "audio/webm" }));
        vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
        vi.stubGlobal("URL", {
            createObjectURL: vi.fn(() => "blob:recording"),
            revokeObjectURL: vi.fn(),
        });
        Object.defineProperty(navigator, "mediaDevices", {
            configurable: true,
            value: { getUserMedia: vi.fn(async () => ({ getTracks: () => [{ stop: stopTrack }] })) },
        });
    });

    afterEach(() => vi.unstubAllGlobals());

    it("persists recorder chunks and creates a preview only when requested", async () => {
        const { result } = renderHook(() => useBrowserAudioRecorder({
            ownerId: "user-1",
            activityId: "activity-1",
        }));
        await waitFor(() => expect(result.current.state).toBe("idle"));

        await act(async () => result.current.start());
        expect(result.current.state).toBe("recording");
        act(() => result.current.stop());
        await waitFor(() => expect(result.current.state).toBe("ready"));

        expect(mocks.appendChunk).toHaveBeenCalled();
        expect(result.current.draft?.chunkCount).toBeGreaterThan(0);
        expect(result.current.audioUrl).toBeNull();
        await act(async () => result.current.preview());
        expect(result.current.audioUrl).toBe("blob:recording");
    });

    it("supports pausing and continuing the same durable draft", async () => {
        const { result } = renderHook(() => useBrowserAudioRecorder());
        await waitFor(() => expect(result.current.state).toBe("idle"));
        await act(async () => result.current.start());

        act(() => result.current.pause());
        await waitFor(() => expect(result.current.state).toBe("paused"));
        expect(result.current.canResume).toBe(true);
        act(() => result.current.resume());
        expect(result.current.state).toBe("recording");
    });

    it("restores an interrupted recording as a paused local draft", async () => {
        currentDraft = draft({ state: "recording", durationSeconds: 12, chunkCount: 2, sizeBytes: 10 });
        mocks.loadDraft.mockResolvedValue(currentDraft);
        const { result } = renderHook(() => useBrowserAudioRecorder({
            ownerId: "user-1",
            activityId: "activity-1",
        }));

        await waitFor(() => expect(result.current.state).toBe("paused"));
        expect(result.current.restored).toBe(true);
        expect(result.current.durationSeconds).toBe(12);
        expect(mocks.updateDraft).toHaveBeenCalledWith("draft-1", { state: "paused" });
        expect(result.current.canResume).toBe(false);
    });

    it("maps denied microphone access without deleting the recovered draft", async () => {
        currentDraft = draft({ state: "ready", chunkCount: 1, sizeBytes: 5 });
        mocks.loadDraft.mockResolvedValue(currentDraft);
        Object.defineProperty(navigator, "mediaDevices", {
            configurable: true,
            value: { getUserMedia: vi.fn(async () => { throw new DOMException("denied", "NotAllowedError"); }) },
        });
        const { result } = renderHook(() => useBrowserAudioRecorder());
        await waitFor(() => expect(result.current.state).toBe("ready"));

        await act(async () => result.current.start());

        expect(result.current.state).toBe("error");
        expect(result.current.error).toContain("麦克风权限");
        expect(mocks.deleteDraft).not.toHaveBeenCalled();
        expect(result.current.draft?.draftId).toBe("draft-1");
    });

    it("deletes the persisted draft when resetting", async () => {
        const { result } = renderHook(() => useBrowserAudioRecorder());
        await waitFor(() => expect(result.current.state).toBe("idle"));
        await act(async () => result.current.start());
        act(() => result.current.stop());
        await waitFor(() => expect(result.current.state).toBe("ready"));

        await act(async () => result.current.reset());

        expect(mocks.deleteDraft).toHaveBeenCalledWith("draft-1");
        expect(result.current.draft).toBeNull();
        expect(stopTrack).toHaveBeenCalled();
    });
});
