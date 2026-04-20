import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    DEFAULT_TRAINING_PREFERENCES,
    TRAINING_PREFERENCES_STORAGE_KEY,
    normalizeTrainingPreferences,
    persistTrainingPreferences,
    readTrainingPreferences,
    useTrainingPreferences,
} from "./use-training-preferences";

describe("useTrainingPreferences", () => {
    beforeEach(() => {
        localStorage.clear();
        vi.restoreAllMocks();
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
        })).toEqual({
            voiceMode: "legacy",
            agentId: "agent-1",
            personaId: "persona-1",
            presentationId: "ppt-1",
        });
    });

    it("reads invalid localStorage JSON as the default preference", () => {
        localStorage.setItem(TRAINING_PREFERENCES_STORAGE_KEY, "not-json");

        expect(readTrainingPreferences()).toEqual(DEFAULT_TRAINING_PREFERENCES);
    });

    it("persists a merged preference patch", () => {
        persistTrainingPreferences({ agentId: "agent-1", personaId: "persona-1" });
        const saved = persistTrainingPreferences({ voiceMode: "legacy", presentationId: "ppt-1" });

        expect(saved).toEqual({
            agentId: "agent-1",
            personaId: "persona-1",
            presentationId: "ppt-1",
            voiceMode: "legacy",
        });
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
        expect(persistTrainingPreferences({ voiceMode: "legacy" }, throwingStorage)).toEqual({
            ...DEFAULT_TRAINING_PREFERENCES,
            voiceMode: "legacy",
        });
    });

    it("hydrates from localStorage and saves updates through the hook", () => {
        localStorage.setItem(TRAINING_PREFERENCES_STORAGE_KEY, JSON.stringify({
            voiceMode: "legacy",
            agentId: "agent-1",
            personaId: "persona-1",
            presentationId: null,
        }));

        const { result } = renderHook(() => useTrainingPreferences());

        expect(result.current.trainingPreferences).toEqual({
            voiceMode: "legacy",
            agentId: "agent-1",
            personaId: "persona-1",
            presentationId: null,
        });

        act(() => {
            result.current.saveTrainingPreferences({ personaId: "persona-2", presentationId: "ppt-1" });
        });

        expect(result.current.trainingPreferences).toEqual({
            voiceMode: "legacy",
            agentId: "agent-1",
            personaId: "persona-2",
            presentationId: "ppt-1",
        });
        expect(readTrainingPreferences()).toEqual(result.current.trainingPreferences);
    });
});
