"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

interface AuthProtectionOptions {
    requiredRole?: "admin" | "user";
}

interface UserInfo {
    id: string;
    name?: string;
    display_name?: string;
    email?: string;
    role: string;
}

export function useAuthProtection(options?: AuthProtectionOptions) {
    const router = useRouter();
    const pathname = usePathname();
    const [isLoading, setIsLoading] = useState(true);
    const [user, setUser] = useState<UserInfo | null>(null);
    const [isAuthorized, setIsAuthorized] = useState(false);

    useEffect(() => {
        // Skip check for login page
        if (pathname === "/login") {
            setIsLoading(false);
            setIsAuthorized(true);
            return;
        }

        // DEV MODE: Allow bypassing auth for testing
        if (process.env.NODE_ENV === "development") {
            const devToken = localStorage.getItem("token");
            const devUser = localStorage.getItem("user");
            if (devToken && devUser) {
                try {
                    const userInfo = JSON.parse(devUser);
                    setUser(userInfo);
                    setIsAuthorized(true);
                    setIsLoading(false);
                    return;
                } catch {
                    // Fall through to normal auth
                }
            }
        }

        const token = localStorage.getItem("token");
        if (!token) {
            router.push("/login");
            return;
        }

        // Get user info from localStorage
        const storedUser = localStorage.getItem("user");
        let userInfo: UserInfo | null = null;

        if (storedUser) {
            try {
                userInfo = JSON.parse(storedUser);
                setUser(userInfo);
            } catch {
                // Ignore parse errors
            }
        }

        // Check role if required
        if (options?.requiredRole) {
            const userRole = userInfo?.role || "user";

            if (options.requiredRole === "admin" && userRole !== "admin") {
                // Redirect non-admin users to home page
                router.push("/");
                return;
            }
        }

        setIsAuthorized(true);
        setIsLoading(false);
    }, [router, pathname, options?.requiredRole]);

    return { isLoading, user, isAuthorized };
}