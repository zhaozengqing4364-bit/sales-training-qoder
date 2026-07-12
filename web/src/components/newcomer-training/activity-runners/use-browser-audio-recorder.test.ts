import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useBrowserAudioRecorder } from "./use-browser-audio-recorder";

class FakeMediaRecorder {
    static isTypeSupported = () => true;
    state = "inactive";
    mimeType = "audio/webm";
    ondataavailable: ((event: { data: Blob }) => void) | null = null;
    onstop: (() => void) | null = null;

    constructor(stream: MediaStream, options?: MediaRecorderOptions) { void stream; void options; }
    start() { this.state = "recording"; }
    stop() {
        this.state = "inactive";
        this.ondataavailable?.({ data: new Blob(["audio"], { type: this.mimeType }) });
        this.onstop?.();
    }
}

describe("useBrowserAudioRecorder", () => {
    const stop = vi.fn();

    beforeEach(() => {
        vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
        vi.stubGlobal("URL", {
            createObjectURL: vi.fn(() => "blob:recording"),
            revokeObjectURL: vi.fn(),
        });
        Object.defineProperty(navigator, "mediaDevices", {
            configurable: true,
            value: { getUserMedia: vi.fn(async () => ({ getTracks: () => [{ stop }] })) },
        });
    });

    afterEach(() => vi.unstubAllGlobals());

    it("creates an uploadable audio file after recording", async () => {
        const { result } = renderHook(() => useBrowserAudioRecorder());

        await act(async () => result.current.start());
        expect(result.current.state).toBe("recording");

        act(() => result.current.stop());

        expect(result.current.state).toBe("ready");
        expect(result.current.audioFile?.name).toBe("讲解录音.webm");
        expect(result.current.audioUrl).toBe("blob:recording");
        expect(stop).toHaveBeenCalled();
    });

    it("maps denied microphone access to an actionable message", async () => {
        Object.defineProperty(navigator, "mediaDevices", {
            configurable: true,
            value: { getUserMedia: vi.fn(async () => { throw new DOMException("denied", "NotAllowedError"); }) },
        });
        const { result } = renderHook(() => useBrowserAudioRecorder());

        await act(async () => result.current.start());

        expect(result.current.state).toBe("error");
        expect(result.current.error).toContain("麦克风权限");
    });

    it("releases the previous preview when resetting", async () => {
        const { result } = renderHook(() => useBrowserAudioRecorder());
        await act(async () => result.current.start());
        act(() => result.current.stop());

        act(() => result.current.reset());

        expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:recording");
        expect(result.current.audioFile).toBeNull();
    });
});
