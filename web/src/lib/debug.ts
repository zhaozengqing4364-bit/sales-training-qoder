const BUILD_DEBUG_ENABLED = process.env.NEXT_PUBLIC_DEBUG === "true"
    || process.env.NODE_ENV === "development";

function runtimeDebugEnabled(): boolean {
    if (typeof window === "undefined") {
        return false;
    }

    try {
        const localFlag = window.localStorage.getItem("QODER_DEBUG");
        if (localFlag === "1" || localFlag === "true") {
            return true;
        }

        const queryFlag = new URLSearchParams(window.location.search).get("debug");
        return queryFlag === "1" || queryFlag === "true";
    } catch {
        return false;
    }
}

function isDebugEnabled(): boolean {
    return BUILD_DEBUG_ENABLED || runtimeDebugEnabled();
}

export const debug = {
    log: (...args: unknown[]) => {
        if (isDebugEnabled()) {
            console.log(...args);
        }
    },
    warn: (...args: unknown[]) => {
        if (isDebugEnabled()) {
            console.warn(...args);
        }
    },
    error: (...args: unknown[]) => {
        console.error(...args);
    },
    enabled: () => isDebugEnabled(),
};
