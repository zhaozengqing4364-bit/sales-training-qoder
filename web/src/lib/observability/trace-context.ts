type TraceContext = {
    traceId: string;
    spanId: string;
    traceparent: string;
    tracestate?: string;
};

type TraceHeaderInput = {
    traceId?: string | null;
    traceparent?: string | null;
    tracestate?: string | null;
};

let sharedTraceId: string | undefined;

function isValidHex(value: string, length: number): boolean {
    return value.length === length && /^[a-f0-9]+$/.test(value) && !/^0+$/.test(value);
}

function normalizeTraceId(value?: string | null): string | undefined {
    if (!value) {
        return undefined;
    }

    const normalized = value.trim().toLowerCase().replace(/-/g, "");
    return isValidHex(normalized, 32) ? normalized : undefined;
}

function normalizeSpanId(value?: string | null): string | undefined {
    if (!value) {
        return undefined;
    }

    const normalized = value.trim().toLowerCase();
    return isValidHex(normalized, 16) ? normalized : undefined;
}

function randomHex(bytes: number): string {
    if (typeof globalThis.crypto?.getRandomValues === "function") {
        const buffer = new Uint8Array(bytes);
        globalThis.crypto.getRandomValues(buffer);
        return Array.from(
            buffer,
            (value) => value.toString(16).padStart(2, "0"),
        ).join("");
    }

    return Array.from({ length: bytes }, () => Math.floor(Math.random() * 256)
        .toString(16)
        .padStart(2, "0"))
        .join("");
}

export function extractTraceIdFromTraceparent(
    traceparent?: string | null,
): string | undefined {
    if (!traceparent) {
        return undefined;
    }

    const parts = traceparent.trim().toLowerCase().split("-");
    if (parts.length !== 4) {
        return undefined;
    }

    const [, traceId, spanId, flags] = parts;
    if (!isValidHex(traceId, 32) || !normalizeSpanId(spanId) || !/^[a-f0-9]{2}$/.test(flags)) {
        return undefined;
    }

    return traceId;
}

export function createTraceContext(
    input: Pick<TraceHeaderInput, "traceId" | "tracestate"> = {},
): TraceContext {
    const traceId = normalizeTraceId(input.traceId) ?? getSharedTraceId();
    const spanId = randomHex(8);

    return {
        traceId,
        spanId,
        traceparent: `00-${traceId}-${spanId}-01`,
        tracestate: input.tracestate?.trim() || undefined,
    };
}

export function getSharedTraceId(): string {
    if (typeof window === "undefined") {
        return randomHex(16);
    }

    if (!sharedTraceId) {
        sharedTraceId = randomHex(16);
    }
    return sharedTraceId;
}

export function buildTraceHeaders(
    input: TraceHeaderInput = {},
): Record<string, string> {
    const traceId =
        extractTraceIdFromTraceparent(input.traceparent) ?? normalizeTraceId(input.traceId);
    const context = createTraceContext({
        traceId,
        tracestate: input.tracestate,
    });

    return {
        "X-Trace-ID": context.traceId,
        traceparent: context.traceparent,
        ...(context.tracestate ? { tracestate: context.tracestate } : {}),
    };
}
