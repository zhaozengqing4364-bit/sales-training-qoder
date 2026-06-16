import { getSharedTraceId } from "@/lib/observability/trace-context";

type ClientInstrumentationConsoleMethod = "error" | "warn";

type ClientInstrumentationListeners = {
    readonly error: (event: ErrorEvent) => void;
    readonly unhandledRejection: (event: PromiseRejectionEvent) => void;
};

type InstrumentedWindow = Window & {
    __qoderClientInstrumentationListeners?: ClientInstrumentationListeners;
};

export function resolveClientInstrumentationConsoleMethod(
    nodeEnv: string | undefined = process.env.NODE_ENV,
): ClientInstrumentationConsoleMethod {
    return nodeEnv === "production" ? "error" : "warn";
}

function stringifyUnknown(value: unknown): string {
    if (value instanceof Error) {
        return value.message || value.name;
    }
    if (typeof value === "string") {
        return value;
    }
    try {
        const serialized = JSON.stringify(value);
        return serialized && serialized !== "null" ? serialized : String(value);
    } catch {
        return String(value);
    }
}

function emitClientInstrumentationEvent(
    label: string,
    payload: Record<string, unknown>,
): void {
    const method = resolveClientInstrumentationConsoleMethod();
    console[method](label, payload);
}

export function installClientInstrumentation(target: InstrumentedWindow): void {
    const existing = target.__qoderClientInstrumentationListeners;
    if (existing) {
        target.removeEventListener("error", existing.error);
        target.removeEventListener("unhandledrejection", existing.unhandledRejection);
    }

    const listeners: ClientInstrumentationListeners = {
        error: (event) => {
            emitClientInstrumentationEvent("[instrumentation-client] unhandled error", {
                traceId: getSharedTraceId(),
                message: event.message || "Unknown browser error",
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
            });
        },
        unhandledRejection: (event) => {
            emitClientInstrumentationEvent(
                "[instrumentation-client] unhandled rejection",
                {
                    traceId: getSharedTraceId(),
                    reason: stringifyUnknown(event.reason),
                },
            );
        },
    };

    target.addEventListener("error", listeners.error);
    target.addEventListener("unhandledrejection", listeners.unhandledRejection);
    target.__qoderClientInstrumentationListeners = listeners;
}

if (typeof window !== "undefined" && process.env.NODE_ENV !== "test") {
    installClientInstrumentation(window);
}
