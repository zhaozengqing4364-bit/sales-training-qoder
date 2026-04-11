import { debug } from "./debug";
/**
 * Auth Handler - Centralized authentication event management
 * 
 * Provides a pub/sub pattern for auth events (logout, session expired, etc.)
 * so components can react to auth state changes without tight coupling.
 */

type AuthListener = (message: string) => void;
type AuthNavigationMode = "push" | "replace";
type AuthNavigator = (to: string, options?: { mode?: AuthNavigationMode }) => void;

interface LogoutOptions {
    redirectTo?: string | null;
    notify?: boolean;
    navigationMode?: AuthNavigationMode;
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

type InterruptiveUiStatus = "needs-cleanup" | "cleaned-up" | "allowed-exception";

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
        status: "cleaned-up",
        notes: "T02 moved logout redirects onto the authHandler navigator seam so auth toasts still publish centrally without forcing a hard reload.",
    },
    {
        id: "auth-handler-session-expired-timeout",
        file: "web/src/lib/auth-handler.ts",
        primitive: "location-assign",
        category: "auth-redirect",
        currentSurface: "sessionExpired delayed login handoff",
        targetSeam: "auth-handler",
        status: "cleaned-up",
        notes: "T02 keeps the delayed login handoff centralized here, but the final route transition now runs through the registered router navigator seam.",
    },
    {
        id: "dashboard-shell-auth-error",
        file: "web/src/components/layout/dashboard-shell.tsx",
        primitive: "location-assign",
        category: "auth-redirect",
        currentSurface: "learner shell auth error effect",
        targetSeam: "auth-handler",
        status: "cleaned-up",
        notes: "The learner shell now delegates expired-session handling to authHandler so toast timing and redirect policy stay centralized.",
    },
    {
        id: "admin-shell-auth-error",
        file: "web/src/components/layout/admin-shell.tsx",
        primitive: "location-assign",
        category: "auth-redirect",
        currentSurface: "admin shell auth error effect",
        targetSeam: "auth-handler",
        status: "cleaned-up",
        notes: "Admin shell auth expiry now uses the same authHandler seam as learner expiry instead of bypassing it with a direct browser jump.",
    },
    {
        id: "admin-shell-role-guard-home",
        file: "web/src/components/layout/admin-shell.tsx",
        primitive: "location-assign",
        category: "business-navigation",
        currentSurface: "non-admin role guard fallback",
        targetSeam: "router",
        status: "cleaned-up",
        notes: "Role mismatch remains a normal navigation decision and now lands on router replace instead of a hard reload.",
    },
    {
        id: "records-delete-confirm",
        file: "web/src/app/admin/records/page.tsx",
        primitive: "native-confirm",
        category: "delete-confirmation",
        currentSurface: "delete training record",
        targetSeam: "dialog",
        status: "cleaned-up",
        notes: "Delete now uses the shared confirm dialog so the action stays non-blocking and visually consistent with the admin shell.",
    },
    {
        id: "records-delete-failure-alert",
        file: "web/src/app/admin/records/page.tsx",
        primitive: "native-alert",
        category: "mutation-feedback",
        currentSurface: "delete training record failure",
        targetSeam: "toast",
        status: "cleaned-up",
        notes: "Deletion failure now stays on-page and uses toast feedback instead of a blocking browser modal.",
    },
    {
        id: "rag-profile-delete-confirm",
        file: "web/src/app/admin/rag-profiles/page.tsx",
        primitive: "native-confirm",
        category: "delete-confirmation",
        currentSurface: "delete rag profile",
        targetSeam: "dialog",
        status: "cleaned-up",
        notes: "The page now pairs its existing toast wiring with the shared confirm dialog for destructive actions.",
    },
    {
        id: "persona-name-validation-alert",
        file: "web/src/app/admin/personas/[id]/page.tsx",
        primitive: "native-alert",
        category: "validation-feedback",
        currentSurface: "save validation for empty persona name",
        targetSeam: "toast",
        status: "cleaned-up",
        notes: "Missing required fields now surface through toast feedback instead of freezing the edit flow with a blocking browser modal.",
    },
    {
        id: "persona-system-prompt-validation-alert",
        file: "web/src/app/admin/personas/[id]/page.tsx",
        primitive: "native-alert",
        category: "validation-feedback",
        currentSurface: "save validation for empty system prompt",
        targetSeam: "toast",
        status: "cleaned-up",
        notes: "This validation now shares the same non-blocking toast seam as the missing-name case.",
    },
    {
        id: "persona-save-failure-alert",
        file: "web/src/app/admin/personas/[id]/page.tsx",
        primitive: "native-alert",
        category: "mutation-feedback",
        currentSurface: "save persona request failure",
        targetSeam: "toast",
        status: "cleaned-up",
        notes: "Save failure now remains on the page and uses toast messaging while the success path still routes through router.push.",
    },
    {
        id: "persona-tts-preview-playback-alert",
        file: "web/src/app/admin/personas/[id]/page.tsx",
        primitive: "native-alert",
        category: "media-preview-feedback",
        currentSurface: "audio preview playback error",
        targetSeam: "toast",
        status: "cleaned-up",
        notes: "Preview playback failure now uses the same toast seam as other operational feedback instead of blocking the whole form.",
    },
    {
        id: "persona-tts-preview-request-alert",
        file: "web/src/app/admin/personas/[id]/page.tsx",
        primitive: "native-alert",
        category: "media-preview-feedback",
        currentSurface: "audio preview request error",
        targetSeam: "toast",
        status: "cleaned-up",
        notes: "Preview request failures now share the same non-blocking media-preview feedback seam as playback errors.",
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
    private navigator: AuthNavigator | null = null;
    private pendingNavigation: { to: string; mode: AuthNavigationMode } | null = null;
    private sessionExpiredTimer: ReturnType<typeof setTimeout> | null = null;
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
     * Register a router-aware navigation seam for auth redirects.
     */
    setNavigator(navigate: AuthNavigator | null): () => void {
        this.navigator = navigate;
        this.flushPendingNavigation();

        return () => {
            if (this.navigator === navigate) {
                this.navigator = null;
            }
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

    private navigate(to: string, mode: AuthNavigationMode = "replace"): void {
        if (!to) {
            return;
        }

        if (this.navigator) {
            this.navigator(to, { mode });
            return;
        }

        this.pendingNavigation = { to, mode };
    }

    private flushPendingNavigation(): void {
        if (!this.navigator || !this.pendingNavigation) {
            return;
        }

        const pending = this.pendingNavigation;
        this.pendingNavigation = null;
        this.navigator(pending.to, { mode: pending.mode });
    }

    /**
     * Handle logout side effects and redirect.
     */
    logout(message: string = "已退出登录", options: LogoutOptions = {}): void {
        const { redirectTo = null, notify = true, navigationMode = "replace" } = options;

        if (notify) {
            this.notify(message);
        }

        if (redirectTo) {
            this.navigate(redirectTo, navigationMode);
        }
    }

    /**
     * Handle session expired — show a brief toast then redirect to login.
     */
    sessionExpired(): void {
        this.logout("登录已过期，请重新登录", { redirectTo: null });

        if (this.sessionExpiredTimer !== null) {
            return;
        }

        const performRedirect = () => {
            this.sessionExpiredTimer = null;
            this.navigate("/login", "replace");
        };

        if (typeof window !== "undefined") {
            this.sessionExpiredTimer = window.setTimeout(performRedirect, 1500);
            return;
        }

        performRedirect();
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
