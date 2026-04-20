import { useCallback, useState } from "react";

export const TRAINING_PREFERENCES_STORAGE_KEY = "training_preferences_v1";
export const TRAINING_VOICE_MODES = ["legacy", "stepfun_realtime"] as const;
export type TrainingVoiceMode = (typeof TRAINING_VOICE_MODES)[number];

export interface TrainingPreferences {
    voiceMode: TrainingVoiceMode;
    agentId: string | null;
    personaId: string | null;
    presentationId: string | null;
}

export type TrainingPreferencePatch = Partial<TrainingPreferences>;

export const DEFAULT_TRAINING_PREFERENCES: TrainingPreferences = {
    voiceMode: "stepfun_realtime",
    agentId: null,
    personaId: null,
    presentationId: null,
};

function isTrainingVoiceMode(value: unknown): value is TrainingVoiceMode {
    return TRAINING_VOICE_MODES.includes(value as TrainingVoiceMode);
}

function normalizeOptionalId(value: unknown): string | null {
    if (typeof value !== "string") {
        return null;
    }

    const trimmed = value.trim();
    return trimmed ? trimmed : null;
}

function toRecord(value: unknown): Record<string, unknown> {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return {};
    }

    return value as Record<string, unknown>;
}

function getBrowserStorage(): Pick<Storage, "getItem" | "setItem"> | null {
    if (typeof window === "undefined") {
        return null;
    }

    return window.localStorage;
}

export function normalizeTrainingPreferences(value: unknown): TrainingPreferences {
    const record = toRecord(value);

    return {
        voiceMode: isTrainingVoiceMode(record.voiceMode)
            ? record.voiceMode
            : DEFAULT_TRAINING_PREFERENCES.voiceMode,
        agentId: normalizeOptionalId(record.agentId),
        personaId: normalizeOptionalId(record.personaId),
        presentationId: normalizeOptionalId(record.presentationId),
    };
}

export function readTrainingPreferences(
    storage: Pick<Storage, "getItem"> | null = getBrowserStorage(),
): TrainingPreferences {
    if (!storage) {
        return DEFAULT_TRAINING_PREFERENCES;
    }

    try {
        const raw = storage.getItem(TRAINING_PREFERENCES_STORAGE_KEY);
        if (!raw) {
            return DEFAULT_TRAINING_PREFERENCES;
        }

        return normalizeTrainingPreferences(JSON.parse(raw));
    } catch {
        return DEFAULT_TRAINING_PREFERENCES;
    }
}

export function persistTrainingPreferences(
    patch: TrainingPreferencePatch,
    storage: Pick<Storage, "getItem" | "setItem"> | null = getBrowserStorage(),
): TrainingPreferences {
    const current = readTrainingPreferences(storage);
    const normalizedPatch = normalizeTrainingPreferences({
        ...current,
        ...patch,
    });

    if (!storage) {
        return normalizedPatch;
    }

    try {
        storage.setItem(
            TRAINING_PREFERENCES_STORAGE_KEY,
            JSON.stringify(normalizedPatch),
        );
    } catch {
        // Ignore persistence failures and keep the in-memory preference.
    }

    return normalizedPatch;
}

export interface UseTrainingPreferencesReturn {
    trainingPreferences: TrainingPreferences;
    saveTrainingPreferences: (patch: TrainingPreferencePatch) => TrainingPreferences;
}

export function useTrainingPreferences(): UseTrainingPreferencesReturn {
    const [trainingPreferences, setTrainingPreferences] = useState<TrainingPreferences>(() => (
        readTrainingPreferences()
    ));

    const saveTrainingPreferences = useCallback((patch: TrainingPreferencePatch) => {
        const nextPreferences = persistTrainingPreferences(patch);
        setTrainingPreferences(nextPreferences);
        return nextPreferences;
    }, []);

    return {
        trainingPreferences,
        saveTrainingPreferences,
    };
}
