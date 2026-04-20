import { useCallback, useEffect, useState } from "react";

export const VOICE_SPEED_PREFERENCE_STORAGE_KEY = "voice_speed_preference";
export const SUPPORTED_VOICE_SPEED_PREFERENCES = [0.75, 1, 1.25, 1.5] as const;
export type VoiceSpeedPreference = (typeof SUPPORTED_VOICE_SPEED_PREFERENCES)[number];
export const DEFAULT_VOICE_SPEED_PREFERENCE: VoiceSpeedPreference = 1;

const VOICE_SPEED_STORAGE_VALUE_MAP: Record<VoiceSpeedPreference, string> = {
    0.75: "0.75",
    1: "1.0",
    1.25: "1.25",
    1.5: "1.5",
};

export const VOICE_SPEED_PREFERENCE_OPTIONS = SUPPORTED_VOICE_SPEED_PREFERENCES.map((value) => ({
    value,
    storageValue: VOICE_SPEED_STORAGE_VALUE_MAP[value],
    label: `${VOICE_SPEED_STORAGE_VALUE_MAP[value]}x`,
}));

function isVoiceSpeedPreference(value: number): value is VoiceSpeedPreference {
    return SUPPORTED_VOICE_SPEED_PREFERENCES.includes(value as VoiceSpeedPreference);
}

function getBrowserStorage(): Pick<Storage, "getItem" | "setItem"> | null {
    if (typeof window === "undefined") {
        return null;
    }

    return window.localStorage;
}

export function serializeVoiceSpeedPreference(value: VoiceSpeedPreference): string {
    return VOICE_SPEED_STORAGE_VALUE_MAP[value];
}

export function normalizeVoiceSpeedPreference(value: unknown): VoiceSpeedPreference {
    if (typeof value === "number" && isVoiceSpeedPreference(value)) {
        return value;
    }

    if (typeof value === "string") {
        const trimmed = value.trim();
        if (!trimmed) {
            return DEFAULT_VOICE_SPEED_PREFERENCE;
        }

        const parsed = Number.parseFloat(trimmed);
        if (Number.isFinite(parsed) && isVoiceSpeedPreference(parsed)) {
            return parsed;
        }
    }

    return DEFAULT_VOICE_SPEED_PREFERENCE;
}

export function readVoiceSpeedPreference(
    storage: Pick<Storage, "getItem"> | null = getBrowserStorage(),
): VoiceSpeedPreference {
    if (!storage) {
        return DEFAULT_VOICE_SPEED_PREFERENCE;
    }

    try {
        return normalizeVoiceSpeedPreference(storage.getItem(VOICE_SPEED_PREFERENCE_STORAGE_KEY));
    } catch {
        return DEFAULT_VOICE_SPEED_PREFERENCE;
    }
}

export function persistVoiceSpeedPreference(
    value: unknown,
    storage: Pick<Storage, "setItem"> | null = getBrowserStorage(),
): VoiceSpeedPreference {
    const normalized = normalizeVoiceSpeedPreference(value);

    if (!storage) {
        return normalized;
    }

    try {
        storage.setItem(
            VOICE_SPEED_PREFERENCE_STORAGE_KEY,
            serializeVoiceSpeedPreference(normalized),
        );
    } catch {
        // Ignore persistence failures and keep the in-memory preference.
    }

    return normalized;
}

export interface UseVoiceSpeedPreferenceReturn {
    voiceSpeedPreference: VoiceSpeedPreference;
    setVoiceSpeedPreference: (value: unknown) => void;
}

export function useVoiceSpeedPreference(): UseVoiceSpeedPreferenceReturn {
    const [voiceSpeedPreference, setVoiceSpeedPreferenceState] = useState<VoiceSpeedPreference>(() => (
        readVoiceSpeedPreference()
    ));

    useEffect(() => {
        persistVoiceSpeedPreference(voiceSpeedPreference);
    }, [voiceSpeedPreference]);

    const setVoiceSpeedPreference = useCallback((value: unknown) => {
        setVoiceSpeedPreferenceState(normalizeVoiceSpeedPreference(value));
    }, []);

    return {
        voiceSpeedPreference,
        setVoiceSpeedPreference,
    };
}
