"use client";

import * as React from "react";

export type RecordingConnectionState = "connecting" | "connected" | "reconnecting" | "failed";
export type RecordingSessionStatus = "preparing" | "in_progress" | "paused" | "completed" | "scoring";
export type RecordingLifecycleAction = "pause" | "resume" | null;
export type RecordingTransition = "idle" | "requesting_permission" | "starting" | "stopping";

export type RecordingToggleIntent =
    | { action: "start" }
    | { action: "stop" }
    | { action: "request_permission" }
    | { action: "blocked"; reason: "connection" | "session_status" | "lifecycle" | "transitioning" };

interface RecordingStateMachineInput {
    connectionState: RecordingConnectionState;
    sessionStatus: RecordingSessionStatus;
    hasPermission: boolean | null;
    isRecording: boolean;
    pendingLifecycleAction: RecordingLifecycleAction;
}

type RecordingTransitionEvent =
    | { type: "begin"; transition: Exclude<RecordingTransition, "idle"> }
    | { type: "end" };

function recordingTransitionReducer(
    state: RecordingTransition,
    event: RecordingTransitionEvent,
): RecordingTransition {
    if (event.type === "end") {
        return "idle";
    }

    if (state !== "idle") {
        return state;
    }

    return event.transition;
}

function resolveRecordingToggleIntent(
    input: RecordingStateMachineInput,
    transition: RecordingTransition,
): RecordingToggleIntent {
    if (transition !== "idle") {
        return { action: "blocked", reason: "transitioning" };
    }

    if (input.connectionState !== "connected") {
        return { action: "blocked", reason: "connection" };
    }

    if (input.sessionStatus !== "in_progress") {
        return { action: "blocked", reason: "session_status" };
    }

    if (input.pendingLifecycleAction !== null) {
        return { action: "blocked", reason: "lifecycle" };
    }

    if (input.isRecording) {
        return { action: "stop" };
    }

    if (input.hasPermission === false) {
        return { action: "request_permission" };
    }

    return { action: "start" };
}

export function useRecordingStateMachine(input: RecordingStateMachineInput) {
    const inputRef = React.useRef(input);
    const transitionRef = React.useRef<RecordingTransition>("idle");
    const [transition, dispatch] = React.useReducer(recordingTransitionReducer, "idle");

    React.useEffect(() => {
        inputRef.current = input;
    }, [input]);

    React.useEffect(() => {
        transitionRef.current = transition;
    }, [transition]);

    const beginTransition = React.useCallback((nextTransition: Exclude<RecordingTransition, "idle">): boolean => {
        if (transitionRef.current !== "idle") {
            return false;
        }

        transitionRef.current = nextTransition;
        dispatch({ type: "begin", transition: nextTransition });
        return true;
    }, []);

    const endTransition = React.useCallback(() => {
        transitionRef.current = "idle";
        dispatch({ type: "end" });
    }, []);

    const resolveToggleIntent = React.useCallback((): RecordingToggleIntent => {
        return resolveRecordingToggleIntent(inputRef.current, transitionRef.current);
    }, []);

    const currentIntent = resolveRecordingToggleIntent(input, transition);

    return {
        transition,
        isTransitioning: transition !== "idle",
        canRecord: currentIntent.action === "start" || currentIntent.action === "stop",
        canRequestPermission: currentIntent.action === "request_permission",
        resolveToggleIntent,
        beginTransition,
        endTransition,
    };
}
