export type ApiRequestOptions = RequestInit & {
    signal?: AbortSignal;
    skipSessionExpiredHandling?: boolean;
    timeoutMs?: number;
    timeoutMessage?: string;
};

export type ApiRequest = <T>(endpoint: string, options?: ApiRequestOptions) => Promise<T>;

export type ApiStream = <T>(endpoint: string, options?: ApiRequestOptions) => AsyncIterable<T>;

export type ApiUpload = <T>(
    endpoint: string,
    formData: FormData,
    signal?: AbortSignal,
    options?: {
        skipSessionExpiredHandling?: boolean;
        timeoutMs?: number;
        timeoutMessage?: string;
        headers?: HeadersInit;
    },
) => Promise<T>;

export function buildQueryString(params?: Record<string, string | number | boolean | null | undefined>): string {
    if (!params) {
        return "";
    }
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value === undefined || value === null || value === "") {
            continue;
        }
        searchParams.set(key, String(value));
    }
    const query = searchParams.toString();
    return query ? `?${query}` : "";
}

export function toRecord(value: unknown): Record<string, unknown> {
    return value && typeof value === "object" ? value as Record<string, unknown> : {};
}

export function toStringValue(value: unknown, fallback = ""): string {
    return typeof value === "string" ? value : fallback;
}

export function toNumberValue(value: unknown, fallback = 0): number {
    if (typeof value === "number" && Number.isFinite(value)) {
        return value;
    }
    if (typeof value === "string" && value.trim() !== "") {
        const parsed = Number(value);
        if (Number.isFinite(parsed)) {
            return parsed;
        }
    }
    return fallback;
}

export function toNullableStringValue(value: unknown): string | null {
    return typeof value === "string" && value.trim() !== "" ? value : null;
}
