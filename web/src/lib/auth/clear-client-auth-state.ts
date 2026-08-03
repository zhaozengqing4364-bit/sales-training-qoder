import { clearBrowserAudioDraftDatabase } from "@/components/newcomer-training/activity-runners/browser-audio-draft-store";

/** Remembered login email on the auth page — cleared on logout. */
export const REMEMBER_EMAIL_STORAGE_KEY = "qoder.login.rememberEmail.v1";

/** Keep in sync with `use-training-preferences` / `use-voice-speed-preference`. */
const TRAINING_PREFERENCES_STORAGE_KEY = "training_preferences_v1";
const VOICE_SPEED_PREFERENCE_STORAGE_KEY = "voice_speed_preference";

const LEGACY_AUTH_STORAGE_KEYS = ["token", "user"] as const;

/** Prefixes for learner session drafts and cached links tied to the signed-in user. */
const USER_SCOPED_STORAGE_PREFIXES = [
    "qoder.",
    "exam-answer-v1-",
    "exam-return-v1-",
    "exam-progress-v1-",
    "exam-learning-content-v1-",
] as const;

const USER_SCOPED_EXACT_STORAGE_KEYS = [
    REMEMBER_EMAIL_STORAGE_KEY,
    TRAINING_PREFERENCES_STORAGE_KEY,
    VOICE_SPEED_PREFERENCE_STORAGE_KEY,
    ...LEGACY_AUTH_STORAGE_KEYS,
] as const;

function removeStorageKeysMatchingPrefixes(
    storage: Storage,
    prefixes: readonly string[],
): void {
    const keysToRemove: string[] = [];

    for (let index = 0; index < storage.length; index += 1) {
        const key = storage.key(index);
        if (!key) {
            continue;
        }
        if (prefixes.some((prefix) => key.startsWith(prefix))) {
            keysToRemove.push(key);
        }
    }

    keysToRemove.forEach((key) => {
        storage.removeItem(key);
    });
}

/**
 * Remove browser-persisted learner/auth artifacts so the next login (including dev login)
 * starts from a clean client state. Intentionally keeps global UI prefs such as `theme`
 * and support flags such as `QODER_DEBUG`.
 */
export function clearClientAuthState(): void {
    if (typeof window === "undefined") {
        return;
    }

    const { localStorage, sessionStorage } = window;

    USER_SCOPED_EXACT_STORAGE_KEYS.forEach((key) => {
        localStorage.removeItem(key);
    });
    removeStorageKeysMatchingPrefixes(localStorage, USER_SCOPED_STORAGE_PREFIXES);

    LEGACY_AUTH_STORAGE_KEYS.forEach((key) => {
        sessionStorage.removeItem(key);
    });
    removeStorageKeysMatchingPrefixes(sessionStorage, USER_SCOPED_STORAGE_PREFIXES);
    clearBrowserAudioDraftDatabase();
}
