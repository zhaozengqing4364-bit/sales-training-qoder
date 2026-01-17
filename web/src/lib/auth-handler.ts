/**
 * Auth Handler - Centralized authentication event management
 * 
 * Provides a pub/sub pattern for auth events (logout, session expired, etc.)
 * so components can react to auth state changes without tight coupling.
 */

type AuthListener = (message: string) => void;

class AuthHandler {
    private listeners: Set<AuthListener> = new Set();

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
        this.listeners.forEach(listener => {
            try {
                listener(message);
            } catch (error) {
                console.error("Auth listener error:", error);
            }
        });
    }

    /**
     * Handle logout - clear storage and redirect
     */
    logout(message: string = "已退出登录"): void {
        if (typeof window !== "undefined") {
            localStorage.removeItem("token");
            localStorage.removeItem("user");
            this.notify(message);
            
            // Redirect to login after a short delay
            setTimeout(() => {
                window.location.href = "/login";
            }, 500);
        }
    }

    /**
     * Handle session expired
     */
    sessionExpired(): void {
        this.logout("登录已过期，请重新登录");
    }

    /**
     * Handle unauthorized access
     */
    unauthorized(): void {
        this.notify("权限不足，请重新登录");
        this.logout("权限不足");
    }
}

// Singleton instance
export const authHandler = new AuthHandler();
