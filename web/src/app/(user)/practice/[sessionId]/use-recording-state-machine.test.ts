import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useRecordingStateMachine } from "./use-recording-state-machine";

describe("useRecordingStateMachine", () => {
    it("blocks duplicate start attempts while the actual start transition is pending", () => {
        const { result } = renderHook(() =>
            useRecordingStateMachine({
                connectionState: "connected",
                sessionStatus: "in_progress",
                hasPermission: true,
                isRecording: false,
                pendingLifecycleAction: null,
            }),
        );

        expect(result.current.resolveToggleIntent().action).toBe("start");

        act(() => {
            expect(result.current.beginTransition("starting")).toBe(true);
        });

        expect(result.current.resolveToggleIntent()).toEqual({
            action: "blocked",
            reason: "transitioning",
        });
        expect(result.current.beginTransition("starting")).toBe(false);

        act(() => {
            result.current.endTransition();
        });

        expect(result.current.resolveToggleIntent().action).toBe("start");
    });

    it("returns to permission retry immediately after a denied permission request", () => {
        const { result } = renderHook(() =>
            useRecordingStateMachine({
                connectionState: "connected",
                sessionStatus: "in_progress",
                hasPermission: false,
                isRecording: false,
                pendingLifecycleAction: null,
            }),
        );

        expect(result.current.resolveToggleIntent().action).toBe("request_permission");

        act(() => {
            expect(result.current.beginTransition("requesting_permission")).toBe(true);
            result.current.endTransition();
        });

        expect(result.current.resolveToggleIntent().action).toBe("request_permission");
    });

    it("blocks recording changes when connection, lifecycle, or session status is not ready", () => {
        const disconnected = renderHook(() =>
            useRecordingStateMachine({
                connectionState: "reconnecting",
                sessionStatus: "in_progress",
                hasPermission: true,
                isRecording: false,
                pendingLifecycleAction: null,
            }),
        );
        expect(disconnected.result.current.resolveToggleIntent()).toEqual({
            action: "blocked",
            reason: "connection",
        });

        const paused = renderHook(() =>
            useRecordingStateMachine({
                connectionState: "connected",
                sessionStatus: "paused",
                hasPermission: true,
                isRecording: false,
                pendingLifecycleAction: null,
            }),
        );
        expect(paused.result.current.resolveToggleIntent()).toEqual({
            action: "blocked",
            reason: "session_status",
        });

        const lifecyclePending = renderHook(() =>
            useRecordingStateMachine({
                connectionState: "connected",
                sessionStatus: "in_progress",
                hasPermission: true,
                isRecording: false,
                pendingLifecycleAction: "pause",
            }),
        );
        expect(lifecyclePending.result.current.resolveToggleIntent()).toEqual({
            action: "blocked",
            reason: "lifecycle",
        });
    });
});
