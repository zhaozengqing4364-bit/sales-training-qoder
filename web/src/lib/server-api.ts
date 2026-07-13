import "server-only";

import { headers } from "next/headers";

import { buildTraceHeaders } from "@/lib/observability/trace-context";

const DEFAULT_API_BASE_URL = "http://localhost:3444/api/v1";
const SERVER_API_BASE_URL = (
    process.env.SERVER_API_URL
    || process.env.NEXT_PUBLIC_API_URL
    || DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

function unwrapApiPayload<T>(payload: unknown): T {
    if (payload && typeof payload === "object" && "data" in payload) {
        return (payload as { data: T }).data;
    }
    return payload as T;
}

export async function serverApiGet<T>(path: string): Promise<T> {
    const requestHeaders = await headers();
    const cookie = requestHeaders.get("cookie");
    const response = await fetch(`${SERVER_API_BASE_URL}${path}`, {
        method: "GET",
        cache: "no-store",
        headers: {
            Accept: "application/json",
            ...(cookie ? { cookie } : {}),
            ...buildTraceHeaders({
                traceId: requestHeaders.get("x-trace-id"),
                traceparent: requestHeaders.get("traceparent"),
                tracestate: requestHeaders.get("tracestate"),
            }),
        },
    });
    if (!response.ok) {
        throw new Error(`Server API request failed: HTTP ${response.status}`);
    }
    return unwrapApiPayload<T>(await response.json());
}
