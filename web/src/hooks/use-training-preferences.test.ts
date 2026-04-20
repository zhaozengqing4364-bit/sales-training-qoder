import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getTrainingPreferencesMock, updateTrainingPreferencesMock } = vi.hoisted(() => ({
    getTrainingPreferencesMock: vi.fn(),
    updateTrainingPreferencesMock: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
    api: {
        user: {
            getTrainingPreferences: getTrainingPreferencesMock,
            updateTrainingPreferences: updateTrainingPreferencesMock,
        },
    },
}));

import {
    DEFAULT_TRAINING_PREFERENCES,
    TRAINING_PREFERENCES_STORAGE_KEY,
    normalizeTrainingPreferences,
    mergeTrainingPreferences,
    normalizeRemoteTrainingPreferences,
    persistTrainingPreferences,
    readTrainingPreferences,
    useTrainingPreferences,
} from "./use-training-preferences";

describe("useTrainingPreferences", () => {
    beforeEach(() => {
        localStorage.clear();
        vi.restoreAllMocks();
        getTrainingPreferencesMock.mockReset();
        updateTrainingPreferencesMock.mockReset();
        getTrainingPreferencesMock.mockResolvedValue(null);
        updateTrainingPreferencesMock.mockResolvedValue(null);
    });

    it("normalizes malformed storage values to safe defaults", () => {
        expect(normalizeTrainingPreferences(null)).toEqual(DEFAULT_TRAINING_PREFERENCES);
        expect(normalizeTrainingPreferences({ voiceMode: "unknown", agentId: "", personaId: 123 })).toEqual(
            DEFAULT_TRAINING_PREFERENCES,
        );
        expect(normalizeTrainingPreferences({
            voiceMode: "legacy",
            agentId: " agent-1 ",
            personaId: "persona-1",
            presentationId: "ppt-1",
            updatedAt: "2026-04-20T10:00:00.000Z",
        })).toEqual({
            voiceMode: "legacy",
            agentId: "agent-1",
            personaId: "persona-1",
            presentationId: "ppt-1",
            updatedAt: "2026-04-20T10:00:00.000Z",
            source: "default",
        });
    });

    it("reads invalid localStorage JSON as the default preference", () => {
        localStorage.setItem(TRAINING_PREFERENCES_STORAGE_KEY, "not-json");

        expect(readTrainingPreferences()).toEqual(DEFAULT_TRAINING_PREFERENCES);
    });

    it("normalizes remote preferences separately from local metadata", () => {
        expect(normalizeRemoteTrainingPreferences(null)).toBeNull();
        expect(normalizeRemoteTrainingPreferences({
            voiceMode: "legacy",
            agentId: "agent-remote",
            personaId: "persona-remote",
            presentationId: "ppt-remote",
            updatedAt: "2026-04-20T10:00:00.000Z",
        })).toEqual({
            voiceMode: "legacy",
            agentId: "agent-remote",
            personaId: "persona-remote",
            presentationId: "ppt-remote",
            updatedAt: "2026-04-20T10:00:00.000Z",
            source: "remote",
        });
    });

    it("merges remote and local preferences by updatedAt while preserving fallback semantics", () => {
        const olderLocal = {
            voiceMode: "legacy",
            agentId: "agent-local",
            personaId: "persona-local",
            presentationId: null,
            updatedAt: "2026-04-20T09:00:00.000Z",
        };
        const newerRemote = {
            voiceMode: "stepfun_realtime",
            agentId: "agent-remote",
            personaId: "persona-remote",
            presentationId: "ppt-remote",
            updatedAt: "2026-04-20T10:00:00.000Z",
        };

        expect(mergeTrainingPreferences({ remote: newerRemote, local: olderLocal })).toEqual({
            voiceMode: "stepfun_realtime",
            agentId: "agent-remote",
            personaId: "persona-remote",
            presentationId: "ppt-remote",
            updatedAt: "2026-04-20T10:00:00.000Z",
            source: "remote",
        });
        expect(mergeTrainingPreferences({ remote: olderLocal, local: newerRemote })).toEqual({
            voiceMode: "stepfun_realtime",
            agentId: "agent-remote",
            personaId: "persona-remote",
            presentationId: "ppt-remote",
            updatedAt: "2026-04-20T10:00:00.000Z",
            source: "local",
        });
        expect(mergeTrainingPreferences({ remote: null, local: newerRemote })).toEqual({
            voiceMode: "stepfun_realtime",
            agentId: "agent-remote",
            personaId: "persona-remote",
            presentationId: "ppt-remote",
            updatedAt: "2026-04-20T10:00:00.000Z",
            source: "local",
        });
        expect(mergeTrainingPreferences({ remote: {}, local: {} })).toEqual(DEFAULT_TRAINING_PREFERENCES);
    });

    it("persists a merged preference patch", () => {
        persistTrainingPreferences({ agentId: "agent-1", personaId: "persona-1" });
        const saved = persistTrainingPreferences({ voiceMode: "legacy", presentationId: "ppt-1" });

        expect(saved).toEqual({
            agentId: "agent-1",
            personaId: "persona-1",
            presentationId: "ppt-1",
            voiceMode: "legacy",
            updatedAt: expect.any(String),
            source: "local",
        });
        expect(Date.parse(saved.updatedAt || "")).not.toBeNaN();
        expect(readTrainingPreferences()).toEqual(saved);
    });

    it("falls back to in-memory updates when storage access throws", () => {
        const throwingStorage = {
            getItem: vi.fn(() => {
                throw new Error("blocked");
            }),
            setItem: vi.fn(() => {
                throw new Error("blocked");
            }),
        };

        expect(readTrainingPreferences(throwingStorage)).toEqual(DEFAULT_TRAINING_PREFERENCES);
        const saved = persistTrainingPreferences({ voiceMode: "legacy" }, throwingStorage);
        expect(saved).toEqual({
            ...DEFAULT_TRAINING_PREFERENCES,
            voiceMode: "legacy",
            updatedAt: expect.any(String),
            source: "local",
        });
    });



    it("hydrates newer remote preferences and caches them locally", async () => {
        localStorage.setItem(TRAINING_PREFERENCES_STORAGE_KEY, JSON.stringify({
            voiceMode: "legacy",
            agentId: "agent-local",
            personaId: "persona-local",
            presentationId: null,
            updatedAt: "2026-04-20T09:00:00.000Z",
            source: "local",
        }));
        getTrainingPreferencesMock.mockResolvedValueOnce({
            voiceMode: "stepfun_realtime",
            agentId: "agent-remote",
            personaId: "persona-remote",
            presentationId: "ppt-remote",
            updatedAt: "2026-04-20T10:00:00.000Z",
        });

        const { result } = renderHook(() => useTrainingPreferences());

        expect(result.current.trainingPreferences.agentId).toBe("agent-local");
        await waitFor(() => {
            expect(result.current.trainingPreferences).toEqual({
                voiceMode: "stepfun_realtime",
                agentId: "agent-remote",
                personaId: "persona-remote",
                presentationId: "ppt-remote",
                updatedAt: "2026-04-20T10:00:00.000Z",
                source: "remote",
            });
        });
        expect(readTrainingPreferences()).toEqual(result.current.trainingPreferences);
    });

    it("keeps local preferences when remote loading fails and best-effort saves remotely", () => {
        getTrainingPreferencesMock.mockRejectedValueOnce(new Error("unauthorized"));
        updateTrainingPreferencesMock.mockRejectedValueOnce(new Error("offline"));
        localStorage.setItem(TRAINING_PREFERENCES_STORAGE_KEY, JSON.stringify({
            voiceMode: "legacy",
            agentId: "agent-local",
            personaId: "persona-local",
            presentationId: null,
            updatedAt: "2026-04-20T09:00:00.000Z",
            source: "local",
        }));

        const { result } = renderHook(() => useTrainingPreferences());

        expect(result.current.trainingPreferences.agentId).toBe("agent-local");
        act(() => {
            result.current.saveTrainingPreferences({ personaId: "persona-next" });
        });

        expect(result.current.trainingPreferences.personaId).toBe("persona-next");
        expect(updateTrainingPreferencesMock).toHaveBeenCalledWith(result.current.trainingPreferences);
    });

    it("hydrates from localStorage and saves updates through the hook", () => {
        localStorage.setItem(TRAINING_PREFERENCES_STORAGE_KEY, JSON.stringify({
            voiceMode: "legacy",
            agentId: "agent-1",
            personaId: "persona-1",
            presentationId: null,
        }));

        const { result } = renderHook(() => useTrainingPreferences(null));

        expect(result.current.trainingPreferences).toEqual({
            voiceMode: "legacy",
            agentId: "agent-1",
            personaId: "persona-1",
            presentationId: null,
            updatedAt: null,
            source: "local",
        });

        act(() => {
            result.current.saveTrainingPreferences({ personaId: "persona-2", presentationId: "ppt-1" });
        });

        expect(result.current.trainingPreferences).toEqual({
            voiceMode: "legacy",
            agentId: "agent-1",
            personaId: "persona-2",
            presentationId: "ppt-1",
            updatedAt: expect.any(String),
            source: "local",
        });
        expect(readTrainingPreferences()).toEqual(result.current.trainingPreferences);
    });
});
