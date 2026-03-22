import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { normalizeCurrentUser, hasRequiredRole, type CurrentUser, type CurrentUserRole } from "@/lib/auth/current-user";
import { buildTraceHeaders } from "@/lib/observability/trace-context";

const DEFAULT_API_BASE_URL = "http://localhost:3444/api/v1";
const SERVER_API_BASE_URL = (
    process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

type RequireServerSessionOptions = {
    requiredRoles?: CurrentUserRole[];
    loginRedirectTo?: string;
    unauthorizedRedirectTo?: string;
};

function unwrapApiPayload(payload: unknown): unknown {
    if (payload && typeof payload === "object" && "data" in payload) {
        return (payload as { data?: unknown }).data;
    }
    return payload;
}

export async function getServerSessionUser(): Promise<CurrentUser | null> {
    const requestHeaders = await headers();
    const cookieHeader = requestHeaders.get("cookie");
    const traceHeaders = buildTraceHeaders({
        traceId: requestHeaders.get("x-trace-id"),
        traceparent: requestHeaders.get("traceparent"),
        tracestate: requestHeaders.get("tracestate"),
    });

    if (!cookieHeader) {
        return null;
    }

    const response = await fetch(`${SERVER_API_BASE_URL}/users/me`, {
        method: "GET",
        cache: "no-store",
        credentials: "include",
        headers: {
            cookie: cookieHeader,
            Accept: "application/json",
            ...traceHeaders,
        },
    });

    if (response.status === 401 || response.status === 403) {
        return null;
    }

    if (!response.ok) {
        throw new Error(`Failed to resolve server session: HTTP ${response.status}`);
    }

    const payload = unwrapApiPayload(await response.json().catch(() => null));

    if (!payload) {
        return null;
    }

    return normalizeCurrentUser(payload);
}

export async function requireServerSession(
    options: RequireServerSessionOptions = {},
): Promise<CurrentUser> {
    const {
        requiredRoles,
        loginRedirectTo = "/login",
        unauthorizedRedirectTo = "/",
    } = options;

    const user = await getServerSessionUser();

    if (!user) {
        redirect(loginRedirectTo);
    }

    if (!hasRequiredRole(user, requiredRoles)) {
        redirect(unauthorizedRedirectTo);
    }

    return user;
}
