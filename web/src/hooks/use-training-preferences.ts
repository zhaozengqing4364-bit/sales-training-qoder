import { useCallback, useState } from "react";

export const TRAINING_PREFERENCES_STORAGE_KEY = "training_preferences_v1";
export const TRAINING_VOICE_MODES = ["legacy", "stepfun_realtime"] as const;
export type TrainingVoiceMode = (typeof TRAINING_VOICE_MODES)[number];
export type TrainingPreferenceSource = "default" | "local" | "remote";

export interface TrainingPreferences {
    voiceMode: TrainingVoiceMode;
    agentId: string | null;
    personaId: string | null;
    presentationId: string | null;
    updatedAt: string | null;
    source: TrainingPreferenceSource;
}

export type TrainingPreferencePatch = Partial<Omit<TrainingPreferences, "source" | "updatedAt">>;

export const DEFAULT_TRAINING_PREFERENCES: TrainingPreferences = {
    voiceMode: "stepfun_realtime",
    agentId: null,
    personaId: null,
    presentationId: null,
    updatedAt: null,
    source: "default",
};

function isTrainingVoiceMode(value: unknown): value is TrainingVoiceMode {
    return TRAINING_VOICE_MODES.includes(value as TrainingVoiceMode);
}

function normalizeSource(value: unknown, fallback: TrainingPreferenceSource): TrainingPreferenceSource {
    return value === "local" || value === "remote" || value === "default" ? value : fallback;
}

function normalizeOptionalId(value: unknown): string | null {
    if (typeof value !== "string") {
        return null;
    }

    const trimmed = value.trim();
    return trimmed ? trimmed : null;
}

function normalizeUpdatedAt(value: unknown): string | null {
    if (typeof value !== "string") {
        return null;
    }
    const trimmed = value.trim();
    return Number.isFinite(Date.parse(trimmed)) ? trimmed : null;
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

export function normalizeTrainingPreferences(
    value: unknown,
    source: TrainingPreferenceSource = "default",
): TrainingPreferences {
    const record = toRecord(value);

    return {
        voiceMode: isTrainingVoiceMode(record.voiceMode)
            ? record.voiceMode
            : DEFAULT_TRAINING_PREFERENCES.voiceMode,
        agentId: normalizeOptionalId(record.agentId),
        personaId: normalizeOptionalId(record.personaId),
        presentationId: normalizeOptionalId(record.presentationId),
        updatedAt: normalizeUpdatedAt(record.updatedAt),
        source: normalizeSource(record.source, source),
    };
}

export function normalizeRemoteTrainingPreferences(value: unknown): TrainingPreferences | null {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return null;
    }

    return normalizeTrainingPreferences(value, "remote");
}

function getPreferenceTimestamp(preferences: TrainingPreferences): number | null {
    if (!preferences.updatedAt) {
        return null;
    }
    const timestamp = Date.parse(preferences.updatedAt);
    return Number.isFinite(timestamp) ? timestamp : null;
}

export function mergeTrainingPreferences({
    remote,
    local,
}: {
    remote?: unknown;
    local?: unknown;
}): TrainingPreferences {
    const remotePreferences = normalizeRemoteTrainingPreferences(remote);
    const localPreferences = local ? normalizeTrainingPreferences(local, "local") : null;

    if (!remotePreferences && !localPreferences) {
        return DEFAULT_TRAINING_PREFERENCES;
    }
    if (!remotePreferences) {
        return localPreferences ?? DEFAULT_TRAINING_PREFERENCES;
    }
    if (!localPreferences) {
        return remotePreferences;
    }

    const remoteTimestamp = getPreferenceTimestamp(remotePreferences);
    const localTimestamp = getPreferenceTimestamp(localPreferences);

    if (remoteTimestamp !== null && localTimestamp !== null) {
        return remoteTimestamp >= localTimestamp ? remotePreferences : localPreferences;
    }
    if (remoteTimestamp !== null) {
        return remotePreferences;
    }
    if (localTimestamp !== null) {
        return localPreferences;
    }

    return DEFAULT_TRAINING_PREFERENCES;
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

        return normalizeTrainingPreferences(JSON.parse(raw), "local");
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
        updatedAt: new Date().toISOString(),
        source: "local",
    }, "local");

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
