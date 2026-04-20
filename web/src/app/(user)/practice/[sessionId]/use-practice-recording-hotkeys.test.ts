import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { usePracticeRecordingHotkeys } from "./use-practice-recording-hotkeys";

describe("usePracticeRecordingHotkeys", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = "";
    });

    it("toggles recording on space key and stops active recording on keyup", () => {
        const onToggleRecording = vi.fn();
        const onStopRecording = vi.fn();
        const isRecordingRef = { current: true };

        renderHook(() =>
            usePracticeRecordingHotkeys({
                onToggleRecording,
                onStopRecording,
                isRecordingRef,
            }),
        );

        window.dispatchEvent(new KeyboardEvent("keydown", { code: "Space" }));
        window.dispatchEvent(new KeyboardEvent("keyup", { code: "Space" }));

        expect(onToggleRecording).toHaveBeenCalledTimes(1);
        expect(onStopRecording).toHaveBeenCalledTimes(1);
    });

    it("ignores space hotkeys originating from editable elements", () => {
        const onToggleRecording = vi.fn();
        const onStopRecording = vi.fn();
        const isRecordingRef = { current: true };

        renderHook(() =>
            usePracticeRecordingHotkeys({
                onToggleRecording,
                onStopRecording,
                isRecordingRef,
            }),
        );

        const input = document.createElement("input");
        document.body.appendChild(input);

        input.dispatchEvent(new KeyboardEvent("keydown", { code: "Space", bubbles: true }));
        input.dispatchEvent(new KeyboardEvent("keyup", { code: "Space", bubbles: true }));

        expect(onToggleRecording).not.toHaveBeenCalled();
        expect(onStopRecording).not.toHaveBeenCalled();
    });
});
