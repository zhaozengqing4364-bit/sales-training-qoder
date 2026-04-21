"use client";

import * as React from "react";
import {
    PRACTICE_RECORDING_HOTKEY_SCOPE_ATTRIBUTE,
    practiceUxConfig,
} from "@/lib/practice-ux-config";

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

function isScrollableElement(element: HTMLElement): boolean {
    return element.scrollHeight > element.clientHeight;
}

function isScrollableTarget(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) {
        return false;
    }

    let current: HTMLElement | null = target;
    while (current && current !== document.body && current !== document.documentElement) {
        if (isScrollableElement(current)) {
            return true;
        }

        if (current.hasAttribute(PRACTICE_RECORDING_HOTKEY_SCOPE_ATTRIBUTE)) {
            return false;
        }

        current = current.parentElement;
    }

    return false;
}

function isInsideRecordingHotkeyScope(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) {
        return false;
    }

    return Boolean(target.closest(`[${PRACTICE_RECORDING_HOTKEY_SCOPE_ATTRIBUTE}="true"]`));
}

export function usePracticeRecordingHotkeys({
    onToggleRecording,
    onStopRecording,
    isRecordingRef,
}: UsePracticeRecordingHotkeysParams): void {
    const spaceHeldRef = React.useRef(false);
    const hotkeyCode = practiceUxConfig.recordingHotkeyCode;

    React.useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (!hotkeyCode || event.code !== hotkeyCode) {
                return;
            }

            if (
                isEditableTarget(event.target)
                || isScrollableTarget(event.target)
                || !isInsideRecordingHotkeyScope(event.target)
            ) {
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
            if (!hotkeyCode || event.code !== hotkeyCode) {
                return;
            }

            if (
                isEditableTarget(event.target)
                || isScrollableTarget(event.target)
                || !isInsideRecordingHotkeyScope(event.target)
            ) {
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
    }, [hotkeyCode, isRecordingRef, onStopRecording, onToggleRecording]);
}
