const HOTKEY_ALLOWLIST = new Set(["Space"]);

const DEFAULT_RECORDING_HOTKEY_CODE = "Space";
const DEFAULT_AUTOSCROLL_BOTTOM_THRESHOLD_PX = 100;
const DEFAULT_SESSION_END_REDIRECT_DELAY_SECONDS = 5;
const DEFAULT_MESSAGE_DEDUPE_WINDOW_SECONDS = 300;
const DEFAULT_MESSAGE_DEDUPE_MAX_ENTRIES = 200;

function readEnvValue(name: string): string | undefined {
    const value = process.env[name];
    return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function parseBoundedInteger(
    rawValue: string | undefined,
    fallback: number,
    min: number,
    max: number,
): number {
    if (rawValue === undefined) {
        return fallback;
    }

    const parsed = Number(rawValue);
    if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
        return fallback;
    }

    return parsed;
}

function parseRecordingHotkeyCode(rawValue: string | undefined): string | null {
    if (rawValue === undefined) {
        return DEFAULT_RECORDING_HOTKEY_CODE;
    }

    return HOTKEY_ALLOWLIST.has(rawValue) ? rawValue : null;
}

export const PRACTICE_RECORDING_HOTKEY_SCOPE_ATTRIBUTE = "data-practice-recording-hotkey-scope";

export const practiceUxConfig = {
    recordingHotkeyCode: parseRecordingHotkeyCode(
        readEnvValue("NEXT_PUBLIC_PRACTICE_RECORDING_HOTKEY_CODE"),
    ),
    autoscrollBottomThresholdPx: parseBoundedInteger(
        readEnvValue("NEXT_PUBLIC_PRACTICE_AUTOSCROLL_BOTTOM_THRESHOLD_PX"),
        DEFAULT_AUTOSCROLL_BOTTOM_THRESHOLD_PX,
        0,
        500,
    ),
    sessionEndRedirectDelaySeconds: parseBoundedInteger(
        readEnvValue("NEXT_PUBLIC_PRACTICE_SESSION_END_REDIRECT_DELAY_SECONDS"),
        DEFAULT_SESSION_END_REDIRECT_DELAY_SECONDS,
        0,
        60,
    ),
    messageDedupeWindowMs: parseBoundedInteger(
        readEnvValue("NEXT_PUBLIC_PRACTICE_MESSAGE_DEDUPE_WINDOW_SECONDS"),
        DEFAULT_MESSAGE_DEDUPE_WINDOW_SECONDS,
        30,
        3600,
    ) * 1000,
    messageDedupeMaxEntries: parseBoundedInteger(
        readEnvValue("NEXT_PUBLIC_PRACTICE_MESSAGE_DEDUPE_MAX_ENTRIES"),
        DEFAULT_MESSAGE_DEDUPE_MAX_ENTRIES,
        20,
        1000,
    ),
} as const;
