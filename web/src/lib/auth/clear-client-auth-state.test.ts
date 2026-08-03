import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/components/newcomer-training/activity-runners/browser-audio-draft-store", () => ({
    clearBrowserAudioDraftDatabase: vi.fn(),
}));

import { TRAINING_PREFERENCES_STORAGE_KEY } from "@/hooks/use-training-preferences";
import { VOICE_SPEED_PREFERENCE_STORAGE_KEY } from "@/hooks/use-voice-speed-preference";
import { clearBrowserAudioDraftDatabase } from "@/components/newcomer-training/activity-runners/browser-audio-draft-store";

import {
    REMEMBER_EMAIL_STORAGE_KEY,
    clearClientAuthState,
} from "./clear-client-auth-state";

describe("clearClientAuthState", () => {
    beforeEach(() => {
        localStorage.clear();
        sessionStorage.clear();
        vi.mocked(clearBrowserAudioDraftDatabase).mockClear();
    });

    it("removes remembered login email, training prefs, and qoder-prefixed drafts", () => {
        localStorage.setItem(REMEMBER_EMAIL_STORAGE_KEY, "learner@example.com");
        localStorage.setItem(TRAINING_PREFERENCES_STORAGE_KEY, JSON.stringify({ agentId: "a-1" }));
        localStorage.setItem(VOICE_SPEED_PREFERENCE_STORAGE_KEY, "1.25");
        localStorage.setItem("qoder.retrainingTaskSession.v1:session-1", "{}");
        localStorage.setItem("qoder.highlightReviewList.v1:session-1", "{}");
        localStorage.setItem("exam-answer-v1-exam-1-q-1", "draft");
        localStorage.setItem("exam-progress-v1-exam-1", "{}");
        localStorage.setItem("token", "legacy-token");
        localStorage.setItem("theme", "dark");
        localStorage.setItem("QODER_DEBUG", "1");

        clearClientAuthState();

        expect(localStorage.getItem(REMEMBER_EMAIL_STORAGE_KEY)).toBeNull();
        expect(localStorage.getItem(TRAINING_PREFERENCES_STORAGE_KEY)).toBeNull();
        expect(localStorage.getItem(VOICE_SPEED_PREFERENCE_STORAGE_KEY)).toBeNull();
        expect(localStorage.getItem("qoder.retrainingTaskSession.v1:session-1")).toBeNull();
        expect(localStorage.getItem("exam-answer-v1-exam-1-q-1")).toBeNull();
        expect(localStorage.getItem("token")).toBeNull();
        expect(localStorage.getItem("theme")).toBe("dark");
        expect(localStorage.getItem("QODER_DEBUG")).toBe("1");
        expect(clearBrowserAudioDraftDatabase).toHaveBeenCalledOnce();
    });
});
