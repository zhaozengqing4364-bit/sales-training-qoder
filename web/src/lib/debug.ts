const BUILD_DEBUG_ENABLED = process.env.NEXT_PUBLIC_DEBUG === "true"
    || process.env.NODE_ENV === "development";

export type FrontendConsoleCategory = "debug-only" | "durable-error" | "instrumentation" | "tests";
export type FrontendConsoleAction = "migrate-to-debug-seam" | "allowed-console-exception";

export interface FrontendConsoleInventoryEntry {
    scope: string;
    category: FrontendConsoleCategory;
    action: FrontendConsoleAction;
    fileGlobs: readonly string[];
    notes: string;
}

export interface DebugContext {
    [key: string]: unknown;
}

/**
 * Canonical inventory for M015/S01.
 *
 * Downstream tasks should migrate every `migrate-to-debug-seam` entry onto the
 * shared helper below instead of re-running a repo-wide classification pass.
 */
export const frontendConsoleInventory: readonly FrontendConsoleInventoryEntry[] = [
    {
        scope: "shared debug seam",
        category: "debug-only",
        action: "allowed-console-exception",
        fileGlobs: ["web/src/lib/debug.ts"],
        notes: "The seam itself is the only shared place where debug.log/debug.warn/debug.error may reach raw console directly.",
    },
    {
        scope: "runtime instrumentation bootstrap",
        category: "instrumentation",
        action: "allowed-console-exception",
        fileGlobs: [
            "web/src/instrumentation.ts",
            "web/src/instrumentation-client.ts",
        ],
        notes: "Bootstrap and global unhandled-error listeners stay raw-console so faults remain visible before React state/helpers are available.",
    },
    {
        scope: "route error surfaces",
        category: "durable-error",
        action: "migrate-to-debug-seam",
        fileGlobs: [
            "web/src/components/ErrorBoundary.tsx",
            "web/src/components/learner/learner-route-error-state.tsx",
            "web/src/app/(dashboard)/error.tsx",
            "web/src/app/admin/error.tsx",
        ],
        notes: "These surfaces already own user-facing fallback UI and should keep that role, but their durable reporting should converge on the shared debug seam.",
    },
    {
        scope: "business pages and hooks",
        category: "durable-error",
        action: "migrate-to-debug-seam",
        fileGlobs: [
            "web/src/app/(dashboard)/**/page.tsx",
            "web/src/app/admin/**/page.tsx",
            "web/src/app/(user)/practice/[sessionId]/page.tsx",
            "web/src/components/admin/knowledge-answer/tabs/intent-rules-tab.tsx",
            "web/src/components/highlights/*.tsx",
            "web/src/components/training/ScenarioList.tsx",
            "web/src/components/ui/audio-visualizer.tsx",
            "web/src/hooks/**/*.ts",
            "web/src/lib/auth-handler.ts",
        ],
        notes: "Fetch, auth, websocket, media, and runtime failures are durable product errors today even when they also show inline UI; they are not allowed raw-console exceptions.",
    },
    {
        scope: "developer/support diagnostics",
        category: "debug-only",
        action: "migrate-to-debug-seam",
        fileGlobs: [
            "web/src/app/test-mic/page.tsx",
            "web/src/hooks/use-debounce-request.ts",
            "web/src/lib/performance.ts",
        ],
        notes: "These calls are intentionally non-learner-facing, but they should still flow through debug.log/debug.warn instead of bypassing the seam.",
    },
    {
        scope: "tests",
        category: "tests",
        action: "allowed-console-exception",
        fileGlobs: [
            "web/src/**/*.test.ts",
            "web/src/**/*.test.tsx",
        ],
        notes: "Focused tests may keep explicit console assertions/intercepts when needed. The current T01 inventory scan found no matching test-side console calls.",
    },
] as const;

export const frontendConsoleRouteErrorPolicy = {
    routeErrorSurfaces: [
        "web/src/components/ErrorBoundary.tsx",
        "web/src/components/learner/learner-route-error-state.tsx",
        "web/src/app/(dashboard)/error.tsx",
        "web/src/app/admin/error.tsx",
    ] as const,
    businessSurfaceDifference: "Route error surfaces already render fallback UI and own retry messaging, while business pages/hooks mostly use raw console as an implementation-side escape hatch. Both should report through the same durable debug seam, but only route errors should remain responsible for boundary-level fallback UX.",
} as const;

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

function emitDurableError(scope: string, error: unknown, context: DebugContext = {}) {
    console.error(`[${scope}]`, error, {
        reporting: "durable-error",
        ...context,
    });
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
    durableError: (scope: string, error: unknown, context?: DebugContext) => {
        emitDurableError(scope, error, context);
    },
    enabled: () => isDebugEnabled(),
};
