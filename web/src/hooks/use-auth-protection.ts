"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { authHandler } from "@/lib/auth-handler";

interface AuthProtectionOptions {
    requiredRole?: "admin" | "user" | "support";
    requiredRoles?: Array<"admin" | "user" | "support">;
}

interface UserInfo {
    id: string;
    name?: string;
    display_name?: string;
    email?: string;
    role: string;
}

interface AuthRuntimeState {
    hydrated: boolean;
    token: string | null;
    user: UserInfo | null;
}

const INITIAL_AUTH_RUNTIME_STATE: AuthRuntimeState = {
    hydrated: false,
    token: null,
    user: null,
};

function readAuthRuntimeState(): AuthRuntimeState {
    if (typeof window === "undefined") {
        return {
            hydrated: false,
            token: null,
            user: null,
        };
    }

    const nextToken = localStorage.getItem("token");
    const storedUser = localStorage.getItem("user");
    let nextUser: UserInfo | null = null;

    if (storedUser) {
        try {
            nextUser = JSON.parse(storedUser) as UserInfo;
        } catch {
            nextUser = null;
        }
    }

    return {
        hydrated: true,
        token: nextToken,
        user: nextUser,
    };
}

export function useAuthProtection(options?: AuthProtectionOptions) {
    const router = useRouter();
    const pathname = usePathname();
    const [authState, setAuthState] = useState<AuthRuntimeState>(INITIAL_AUTH_RUNTIME_STATE);

    const requiredRoles = options?.requiredRoles || (options?.requiredRole ? [options.requiredRole] : undefined);
    const isLoginPath = pathname === "/login";
    const token = authState.token;
    const user = authState.user;
    const isLoading = !authState.hydrated;
    const hasRoleAccess = !requiredRoles || requiredRoles.includes((user?.role || "user") as "admin" | "user" | "support");
    const isDevBypass = process.env.NODE_ENV === "development" && Boolean(token) && Boolean(user) && hasRoleAccess;
    const roleMismatch = Boolean(
        requiredRoles &&
        !requiredRoles.includes((user?.role || "user") as "admin" | "user" | "support")
    );

    const isAuthorized = isLoginPath || (!isLoading && (isDevBypass || (!!token && !roleMismatch)));

    const syncAuthState = useCallback(() => {
        setAuthState(readAuthRuntimeState());
    }, []);

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }

        const syncTimer = window.setTimeout(() => {
            syncAuthState();
        }, 0);

        const handleStorage = () => syncAuthState();
        const unsubscribe = authHandler.subscribe(() => syncAuthState());

        window.addEventListener("storage", handleStorage);
        return () => {
            window.clearTimeout(syncTimer);
            window.removeEventListener("storage", handleStorage);
            unsubscribe();
        };
    }, [syncAuthState]);

    useEffect(() => {
        if (isLoading) {
            return;
        }

        if (isLoginPath) {
            return;
        }

        if (!token) {
            router.replace("/login");
            return;
        }

        if (roleMismatch) {
            router.replace("/");
        }
    }, [isLoading, isLoginPath, roleMismatch, router, token]);

    return { isLoading, user, isAuthorized };
}
