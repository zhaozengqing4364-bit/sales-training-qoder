import { debug } from "./debug";
/**
 * Auth Handler - Centralized authentication event management
 * 
 * Provides a pub/sub pattern for auth events (logout, session expired, etc.)
 * so components can react to auth state changes without tight coupling.
 */

type AuthListener = (message: string) => void;

interface LogoutOptions {
    redirectTo?: string | null;
    notify?: boolean;
}

type InterruptiveUiCategory =
    | "delete-confirmation"
    | "auth-redirect"
    | "business-navigation"
    | "validation-feedback"
    | "mutation-feedback"
    | "media-preview-feedback"
    | "observability-read";

type InterruptiveUiPrimitive =
    | "native-alert"
    | "native-confirm"
    | "location-assign"
    | "location-href-read"
    | "location-href-write";

type InterruptiveUiTargetSeam =
    | "dialog"
    | "toast"
    | "router"
    | "auth-handler"
    | "allowed-exception";

type InterruptiveUiStatus = "needs-cleanup" | "allowed-exception";

interface InterruptiveUiInventoryItem {
    id: string;
    file: string;
    primitive: InterruptiveUiPrimitive;
    category: InterruptiveUiCategory;
    currentSurface: string;
    targetSeam: InterruptiveUiTargetSeam;
    status: InterruptiveUiStatus;
    notes: string;
}

/**
 * M015/S02/T01 inventory for native dialog / hard-navigation cleanup.
 *
 * This list is intentionally append-first and scanner-backed: when the grep gate
 * changes, update the inventory in the same task so downstream cleanup work can
 * distinguish "needs migration" from "explained exception" without re-research.
 */
export const interruptiveUiInventory: readonly InterruptiveUiInventoryItem[] = [
    {
        id: "auth-handler-logout-redirect",
        file: "web/src/lib/auth-handler.ts",
        primitive: "location-assign",
        category: "auth-redirect",
        currentSurface: "logout redirectTo branch",
        targetSeam: "auth-handler",
        status: "needs-cleanup",
        notes: "Keep auth toast publication here, but let router-aware callers own the actual navigation instead of forcing a hard reload.",
    },
    {
        id: "auth-handler-session-expired-timeout",
        file: "web/src/lib/auth-handler.ts",
        primitive: "location-assign",
        category: "auth-redirect",
        currentSurface: "sessionExpired delayed login handoff",
        targetSeam: "auth-handler",
        status: "needs-cleanup",
        notes: "Session-expired redirects should stay on the centralized auth seam, but the final route transition should stop depending on a bare browser-location jump.",
    },
    {
        id: "dashboard-shell-auth-error",
        file: "web/src/components/layout/dashboard-shell.tsx",
        primitive: "location-assign",
        category: "auth-redirect",
        currentSurface: "learner shell auth error effect",
        targetSeam: "auth-handler",
        status: "needs-cleanup",
        notes: "The learner shell should delegate expired-session handling to authHandler so toast timing and redirect policy stay centralized.",
    },
    {
        id: "admin-shell-auth-error",
        file: "web/src/components/layout/admin-shell.tsx",
        primitive: "location-assign",
        category: "auth-redirect",
        currentSurface: "admin shell auth error effect",
        targetSeam: "auth-handler",
        status: "needs-cleanup",
        notes: "Admin shell auth expiry is the same seam as learner expiry; it should not bypass authHandler with a direct browser jump.",
    },
    {
        id: "admin-shell-role-guard-home",
        file: "web/src/components/layout/admin-shell.tsx",
        primitive: "location-assign",
        category: "business-navigation",
        currentSurface: "non-admin role guard fallback",
        targetSeam: "router",
        status: "needs-cleanup",
        notes: "Role mismatch is a normal navigation decision, not an auth event, so it should land on router replace/push rather than authHandler.",
    },
    {
        id: "records-delete-confirm",
        file: "web/src/app/admin/records/page.tsx",
        primitive: "native-confirm",
        category: "delete-confirmation",
        currentSurface: "delete training record",
        targetSeam: "dialog",
        status: "needs-cleanup",
        notes: "Use the shared confirm dialog so delete stays non-blocking and visually consistent with the admin shell.",
    },
    {
        id: "records-delete-failure-alert",
        file: "web/src/app/admin/records/page.tsx",
        primitive: "native-alert",
        category: "mutation-feedback",
        currentSurface: "delete training record failure",
        targetSeam: "toast",
        status: "needs-cleanup",
        notes: "Deletion failure is feedback, not a blocking browser modal; it should become toast/error copy.",
    },
    {
        id: "rag-profile-delete-confirm",
        file: "web/src/app/admin/rag-profiles/page.tsx",
        primitive: "native-confirm",
        category: "delete-confirmation",
        currentSurface: "delete rag profile",
        targetSeam: "dialog",
        status: "needs-cleanup",
        notes: "The page already has toast wiring, so the missing seam is only the shared confirm dialog for destructive actions.",
    },
    {
        id: "persona-name-validation-alert",
        file: "web/src/app/admin/personas/[id]/page.tsx",
        primitive: "native-alert",
        category: "validation-feedback",
        currentSurface: "save validation for empty persona name",
        targetSeam: "toast",
        status: "needs-cleanup",
        notes: "Missing required fields should surface as inline/non-blocking feedback rather than freezing the edit flow with a blocking browser modal.",
    },
    {
        id: "persona-system-prompt-validation-alert",
        file: "web/src/app/admin/personas/[id]/page.tsx",
        primitive: "native-alert",
        category: "validation-feedback",
        currentSurface: "save validation for empty system prompt",
        targetSeam: "toast",
        status: "needs-cleanup",
        notes: "This is the same validation seam as missing name and should share the same toast/error affordance.",
    },
    {
        id: "persona-save-failure-alert",
        file: "web/src/app/admin/personas/[id]/page.tsx",
        primitive: "native-alert",
        category: "mutation-feedback",
        currentSurface: "save persona request failure",
        targetSeam: "toast",
        status: "needs-cleanup",
        notes: "Save failure should remain on the page and use toast messaging; the success path already routes through router.push.",
    },
    {
        id: "persona-tts-preview-playback-alert",
        file: "web/src/app/admin/personas/[id]/page.tsx",
        primitive: "native-alert",
        category: "media-preview-feedback",
        currentSurface: "audio preview playback error",
        targetSeam: "toast",
        status: "needs-cleanup",
        notes: "Preview playback failure is operational feedback and should not block the entire form with a blocking browser modal.",
    },
    {
        id: "persona-tts-preview-request-alert",
        file: "web/src/app/admin/personas/[id]/page.tsx",
        primitive: "native-alert",
        category: "media-preview-feedback",
        currentSurface: "audio preview request error",
        targetSeam: "toast",
        status: "needs-cleanup",
        notes: "Request failures share the same non-blocking media-preview feedback seam as playback errors.",
    },
    {
        id: "admin-error-home-fallback",
        file: "web/src/app/admin/error.tsx",
        primitive: "location-href-write",
        category: "business-navigation",
        currentSurface: "route-error fallback home button",
        targetSeam: "allowed-exception",
        status: "allowed-exception",
        notes: "This slice explicitly keeps route-error hard reload/home fallbacks as explained exceptions instead of sweeping them into routine business navigation cleanup.",
    },
    {
        id: "error-boundary-url-capture",
        file: "web/src/components/ErrorBoundary.tsx",
        primitive: "location-href-read",
        category: "observability-read",
        currentSurface: "durable error context capture",
        targetSeam: "allowed-exception",
        status: "allowed-exception",
        notes: "The grep gate matches this because it reads the current URL for diagnostics; it is not a navigation side effect and should remain exempt.",
    },
    {
        id: "performance-url-capture-navigation-start",
        file: "web/src/lib/performance.ts",
        primitive: "location-href-read",
        category: "observability-read",
        currentSurface: "performance navigation start context",
        targetSeam: "allowed-exception",
        status: "allowed-exception",
        notes: "Read-only URL capture for performance telemetry is an explained grep exception, not a redirect.",
    },
    {
        id: "performance-url-capture-navigation-complete",
        file: "web/src/lib/performance.ts",
        primitive: "location-href-read",
        category: "observability-read",
        currentSurface: "performance navigation completion context",
        targetSeam: "allowed-exception",
        status: "allowed-exception",
        notes: "Same as the navigation-start entry: this is read-only observability, not browser-controlled navigation.",
    },
] as const;

class AuthHandler {
    private listeners: Set<AuthListener> = new Set();
    private lastNotifyMessage: string | null = null;
    private lastNotifyTime = 0;
    private readonly notifyCooldownMs = 1200;

    /**
     * Subscribe to auth events
     * @returns Unsubscribe function
     */
    subscribe(listener: AuthListener): () => void {
        this.listeners.add(listener);
        return () => {
            this.listeners.delete(listener);
        };
    }

    /**
     * Notify all listeners of an auth event
     */
    notify(message: string): void {
        const now = Date.now();
        if (
            this.lastNotifyMessage === message
            && now - this.lastNotifyTime < this.notifyCooldownMs
        ) {
            return;
        }
        this.lastNotifyMessage = message;
        this.lastNotifyTime = now;

        this.listeners.forEach(listener => {
            try {
                listener(message);
            } catch (error) {
                debug.error("Auth listener error:", error);
            }
        });
    }

    /**
     * Handle logout side effects and redirect.
     */
    logout(message: string = "已退出登录", options: LogoutOptions = {}): void {
        const { redirectTo = null, notify = true } = options;

        if (typeof window !== "undefined") {
            if (notify) {
                this.notify(message);
            }

            if (redirectTo) {
                window.location.assign(redirectTo);
            }
        }
    }

    /**
     * Handle session expired — show a brief toast then redirect to login.
     */
    sessionExpired(): void {
        this.logout("登录已过期，请重新登录", { redirectTo: null });

        if (typeof window !== "undefined") {
            setTimeout(() => {
                window.location.assign("/login");
            }, 1500);
        }
    }

    /**
     * Handle unauthorized access
     */
    unauthorized(): void {
        this.logout("权限不足，请重新登录", { redirectTo: null });
    }
}

// Singleton instance
export const authHandler = new AuthHandler();
