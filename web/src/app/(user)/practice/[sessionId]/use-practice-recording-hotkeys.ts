"use client";

import * as React from "react";

interface UsePracticeRecordingHotkeysParams {
    onToggleRecording: () => void;
    onStopRecording: () => void;
    isRecordingRef: React.RefObject<boolean>;
}

function isEditableTarget(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) {
        return false;
    }

    return (
        target.tagName === "INPUT"
        || target.tagName === "TEXTAREA"
        || target.isContentEditable
    );
}

export function usePracticeRecordingHotkeys({
    onToggleRecording,
    onStopRecording,
    isRecordingRef,
}: UsePracticeRecordingHotkeysParams): void {
    const spaceHeldRef = React.useRef(false);

    React.useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (isEditableTarget(event.target)) {
                return;
            }

            if (event.code !== "Space") {
                return;
            }

            event.preventDefault();
            event.stopPropagation();

            if (event.repeat) {
                return;
            }

            spaceHeldRef.current = true;
            onToggleRecording();
        };

        const handleKeyUp = (event: KeyboardEvent) => {
            if (isEditableTarget(event.target)) {
                return;
            }

            if (event.code !== "Space") {
                return;
            }

            event.preventDefault();
            event.stopPropagation();

            if (spaceHeldRef.current && isRecordingRef.current) {
                onStopRecording();
            }

            spaceHeldRef.current = false;
        };

        window.addEventListener("keydown", handleKeyDown, true);
        window.addEventListener("keyup", handleKeyUp, true);

        return () => {
            window.removeEventListener("keydown", handleKeyDown, true);
            window.removeEventListener("keyup", handleKeyUp, true);
        };
    }, [isRecordingRef, onStopRecording, onToggleRecording]);
}
