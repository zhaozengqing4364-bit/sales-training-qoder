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
