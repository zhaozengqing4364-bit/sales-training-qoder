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

    it("stops an active recording before considering microphone permission", () => {
        const { result } = renderHook(() =>
            useRecordingStateMachine({
                connectionState: "connected",
                sessionStatus: "in_progress",
                hasPermission: false,
                isRecording: true,
                pendingLifecycleAction: null,
            }),
        );

        expect(result.current.resolveToggleIntent()).toEqual({ action: "stop" });
        expect(result.current.canRecord).toBe(true);
        expect(result.current.canRequestPermission).toBe(false);
    });

    it("treats an unknown initial permission as startable so the recorder can request it", () => {
        const { result } = renderHook(() =>
            useRecordingStateMachine({
                connectionState: "connected",
                sessionStatus: "in_progress",
                hasPermission: null,
                isRecording: false,
                pendingLifecycleAction: null,
            }),
        );

        expect(result.current.resolveToggleIntent()).toEqual({ action: "start" });
    });

    it("uses transition, connection, session, then lifecycle as blocker priority", () => {
        const { result } = renderHook(() =>
            useRecordingStateMachine({
                connectionState: "reconnecting",
                sessionStatus: "paused",
                hasPermission: false,
                isRecording: false,
                pendingLifecycleAction: "resume",
            }),
        );

        expect(result.current.resolveToggleIntent()).toEqual({
            action: "blocked",
            reason: "connection",
        });

        act(() => {
            expect(result.current.beginTransition("requesting_permission")).toBe(true);
        });

        expect(result.current.resolveToggleIntent()).toEqual({
            action: "blocked",
            reason: "transitioning",
        });
    });

    it("resolves against the latest inputs after rerender and preserves transition lifecycle", () => {
        type HookProps = Parameters<typeof useRecordingStateMachine>[0];
        const initialProps: HookProps = {
            connectionState: "connected",
            sessionStatus: "in_progress",
            hasPermission: true,
            isRecording: false,
            pendingLifecycleAction: null,
        };
        const { result, rerender } = renderHook(
            (props: HookProps) => useRecordingStateMachine(props),
            { initialProps },
        );

        act(() => {
            expect(result.current.beginTransition("starting")).toBe(true);
        });
        rerender({ ...initialProps, isRecording: true });
        expect(result.current.transition).toBe("starting");
        expect(result.current.resolveToggleIntent()).toEqual({
            action: "blocked",
            reason: "transitioning",
        });

        act(() => {
            result.current.endTransition();
        });
        expect(result.current.transition).toBe("idle");
        expect(result.current.resolveToggleIntent()).toEqual({ action: "stop" });

        rerender({ ...initialProps, hasPermission: false });
        expect(result.current.resolveToggleIntent()).toEqual({ action: "request_permission" });
    });

    it("rechecks current readiness after a pending permission request is granted", () => {
        type HookProps = Parameters<typeof useRecordingStateMachine>[0];
        const initialProps: HookProps = {
            connectionState: "connected",
            sessionStatus: "in_progress",
            hasPermission: false,
            isRecording: false,
            pendingLifecycleAction: null,
        };
        const { result, rerender } = renderHook(
            (props: HookProps) => useRecordingStateMachine(props),
            { initialProps },
        );

        act(() => {
            expect(result.current.beginTransition("requesting_permission")).toBe(true);
        });
        rerender({ ...initialProps, connectionState: "reconnecting" });

        expect(result.current.resolvePermissionGrantedIntent()).toEqual({
            action: "blocked",
            reason: "connection",
        });
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
