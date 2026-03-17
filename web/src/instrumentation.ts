import { createTraceContext, getSharedTraceId } from "@/lib/observability/trace-context";

export async function register() {
    if (process.env.NEXT_RUNTIME === "nodejs" && process.env.NODE_ENV !== "test") {
        const context = createTraceContext({ traceId: getSharedTraceId() });
        console.info("[instrumentation] server instrumentation initialized", {
            traceId: context.traceId,
            traceparent: context.traceparent,
        });
    }
}

export async function onRequestError(
    error: Error,
    request: { path?: string; method?: string },
) {
    console.error("[instrumentation] request error", {
        traceId: getSharedTraceId(),
        message: error.message,
        path: request.path,
        method: request.method,
    });
}
