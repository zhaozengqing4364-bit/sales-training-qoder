import { cache } from "react";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { normalizeCurrentUser, hasRequiredRole, type CurrentUser, type CurrentUserRole } from "@/lib/auth/current-user";
import { buildTraceHeaders } from "@/lib/observability/trace-context";

const DEFAULT_API_BASE_URL = "http://localhost:3444/api/v1";
const SERVER_API_BASE_URL = (
    process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_BASE_URL
).replace(/\/+$/, "");
const SERVER_SESSION_TIMEOUT_MS = 8_000;

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

function isFetchNetworkFailure(error: unknown): boolean {
    return error instanceof TypeError && error.message === "fetch failed";
}

function isAbortError(error: unknown): boolean {
    return (
        error instanceof Error ||
        (typeof DOMException !== "undefined" && error instanceof DOMException)
    ) && error.name === "AbortError";
}

async function getServerSessionUserUncached(): Promise<CurrentUser | null> {
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

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), SERVER_SESSION_TIMEOUT_MS);

    try {
        const response = await fetch(`${SERVER_API_BASE_URL}/users/me`, {
            method: "GET",
            cache: "no-store",
            credentials: "include",
            signal: controller.signal,
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
    } catch (error) {
        if (isFetchNetworkFailure(error) || isAbortError(error)) {
            return null;
        }
        throw error;
    } finally {
        clearTimeout(timeoutId);
    }
}

export const getServerSessionUser = cache(getServerSessionUserUncached);

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
