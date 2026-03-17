import { getSharedTraceId } from "@/lib/observability/trace-context";

if (typeof window !== "undefined" && process.env.NODE_ENV !== "test") {
    window.addEventListener("error", (event) => {
        console.error("[instrumentation-client] unhandled error", {
            traceId: getSharedTraceId(),
            message: event.message,
            filename: event.filename,
            lineno: event.lineno,
            colno: event.colno,
        });
    });

    window.addEventListener("unhandledrejection", (event) => {
        const reason = event.reason instanceof Error ? event.reason.message : String(event.reason);
        console.error("[instrumentation-client] unhandled rejection", {
            traceId: getSharedTraceId(),
            reason,
        });
    });
}
