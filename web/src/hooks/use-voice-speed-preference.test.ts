import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    DEFAULT_VOICE_SPEED_PREFERENCE,
    VOICE_SPEED_PREFERENCE_STORAGE_KEY,
    normalizeVoiceSpeedPreference,
    persistVoiceSpeedPreference,
    readVoiceSpeedPreference,
    useVoiceSpeedPreference,
} from "./use-voice-speed-preference";

describe("useVoiceSpeedPreference", () => {
    beforeEach(() => {
        localStorage.clear();
        vi.restoreAllMocks();
    });

    it("normalizes malformed values to the supported default", () => {
        expect(normalizeVoiceSpeedPreference(undefined)).toBe(DEFAULT_VOICE_SPEED_PREFERENCE);
        expect(normalizeVoiceSpeedPreference(null)).toBe(DEFAULT_VOICE_SPEED_PREFERENCE);
        expect(normalizeVoiceSpeedPreference(0.5)).toBe(DEFAULT_VOICE_SPEED_PREFERENCE);
        expect(normalizeVoiceSpeedPreference("")).toBe(DEFAULT_VOICE_SPEED_PREFERENCE);
        expect(normalizeVoiceSpeedPreference("1.1")).toBe(DEFAULT_VOICE_SPEED_PREFERENCE);
        expect(normalizeVoiceSpeedPreference("abc")).toBe(DEFAULT_VOICE_SPEED_PREFERENCE);
        expect(normalizeVoiceSpeedPreference("1.5")).toBe(1.5);
        expect(normalizeVoiceSpeedPreference(0.75)).toBe(0.75);
    });

    it("reads invalid localStorage values as the default preference", () => {
        localStorage.setItem(VOICE_SPEED_PREFERENCE_STORAGE_KEY, "2.0");

        expect(readVoiceSpeedPreference()).toBe(DEFAULT_VOICE_SPEED_PREFERENCE);
    });

    it("falls back to the default when storage access throws", () => {
        const throwingStorage = {
            getItem: vi.fn(() => {
                throw new Error("blocked");
            }),
            setItem: vi.fn(() => {
                throw new Error("blocked");
            }),
        };

        expect(readVoiceSpeedPreference(throwingStorage)).toBe(DEFAULT_VOICE_SPEED_PREFERENCE);
        expect(persistVoiceSpeedPreference(1.25, throwingStorage)).toBe(1.25);
    });

    it("hydrates from localStorage, normalizes bad values, and persists updates", async () => {
        localStorage.setItem(VOICE_SPEED_PREFERENCE_STORAGE_KEY, "not-a-rate");

        const { result } = renderHook(() => useVoiceSpeedPreference());

        expect(result.current.voiceSpeedPreference).toBe(DEFAULT_VOICE_SPEED_PREFERENCE);

        await waitFor(() => {
            expect(localStorage.getItem(VOICE_SPEED_PREFERENCE_STORAGE_KEY)).toBe("1.0");
        });

        act(() => {
            result.current.setVoiceSpeedPreference("1.5");
        });

        expect(result.current.voiceSpeedPreference).toBe(1.5);
        await waitFor(() => {
            expect(localStorage.getItem(VOICE_SPEED_PREFERENCE_STORAGE_KEY)).toBe("1.5");
        });
    });
});
