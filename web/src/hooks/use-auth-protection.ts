"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { hasRequiredRole, type CurrentUserRole } from "@/lib/auth/current-user";
import { useCurrentUser } from "@/hooks/use-current-user";
import { isAuthenticationError } from "@/lib/api/client";

interface AuthProtectionOptions {
    requiredRole?: CurrentUserRole;
    requiredRoles?: CurrentUserRole[];
}

export function useAuthProtection(options?: AuthProtectionOptions) {
    const router = useRouter();
    const pathname = usePathname();
    const { data: user, error, isLoading, isError } = useCurrentUser();

    const requiredRoles = options?.requiredRoles || (options?.requiredRole ? [options.requiredRole] : undefined);
    const isLoginPath = pathname === "/login";
    const roleMismatch = Boolean(user && !hasRequiredRole(user, requiredRoles));
    const authError = isAuthenticationError(error);
    const isAuthorized = isLoginPath || (!isLoading && !authError && Boolean(user) && !roleMismatch);

    useEffect(() => {
        if (isLoading) {
            return;
        }

        if (isLoginPath) {
            return;
        }

        if (authError || (!isError && !user)) {
            router.replace("/login");
            return;
        }

        if (roleMismatch) {
            router.replace("/");
        }
    }, [authError, isError, isLoading, isLoginPath, roleMismatch, router, user]);

    return { isLoading, user, isAuthorized };
}
