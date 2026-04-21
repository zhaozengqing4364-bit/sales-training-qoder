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
        const hotkeyTarget = document.createElement("button");
        hotkeyTarget.dataset.practiceRecordingHotkeyScope = "true";
        document.body.appendChild(hotkeyTarget);

        renderHook(() =>
            usePracticeRecordingHotkeys({
                onToggleRecording,
                onStopRecording,
                isRecordingRef,
            }),
        );

        const keydown = new KeyboardEvent("keydown", { code: "Space", bubbles: true, cancelable: true });
        const keyup = new KeyboardEvent("keyup", { code: "Space", bubbles: true, cancelable: true });

        hotkeyTarget.dispatchEvent(keydown);
        hotkeyTarget.dispatchEvent(keyup);

        expect(onToggleRecording).toHaveBeenCalledTimes(1);
        expect(onStopRecording).toHaveBeenCalledTimes(1);
        expect(keydown.defaultPrevented).toBe(true);
        expect(keyup.defaultPrevented).toBe(true);
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

    it("does not prevent default page scroll when Space originates outside the recording scope", () => {
        const onToggleRecording = vi.fn();
        const onStopRecording = vi.fn();
        const isRecordingRef = { current: false };

        renderHook(() =>
            usePracticeRecordingHotkeys({
                onToggleRecording,
                onStopRecording,
                isRecordingRef,
            }),
        );

        const keydown = new KeyboardEvent("keydown", { code: "Space", bubbles: true, cancelable: true });
        document.body.dispatchEvent(keydown);

        expect(onToggleRecording).not.toHaveBeenCalled();
        expect(keydown.defaultPrevented).toBe(false);
    });

    it("does not intercept Space from a scrollable history region even inside practice UI", () => {
        const onToggleRecording = vi.fn();
        const onStopRecording = vi.fn();
        const isRecordingRef = { current: false };
        const scrollableHistory = document.createElement("div");
        scrollableHistory.dataset.practiceRecordingHotkeyScope = "true";
        Object.defineProperty(scrollableHistory, "scrollHeight", { value: 1000, configurable: true });
        Object.defineProperty(scrollableHistory, "clientHeight", { value: 300, configurable: true });
        document.body.appendChild(scrollableHistory);

        renderHook(() =>
            usePracticeRecordingHotkeys({
                onToggleRecording,
                onStopRecording,
                isRecordingRef,
            }),
        );

        const keydown = new KeyboardEvent("keydown", { code: "Space", bubbles: true, cancelable: true });
        scrollableHistory.dispatchEvent(keydown);

        expect(onToggleRecording).not.toHaveBeenCalled();
        expect(keydown.defaultPrevented).toBe(false);
    });
});
