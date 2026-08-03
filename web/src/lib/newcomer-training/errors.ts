import { getApiErrorMessage } from "@/lib/api/client";

const TRACE_SUFFIX = /\s*\((?:trace[_-]?id|traceId)\s*:\s*[^)]+\)\s*$/i;

/** Keeps request correlation in diagnostics while removing it from learner copy. */
export function getFoundationUserErrorMessage(error: unknown): string {
    return getApiErrorMessage(error).replace(TRACE_SUFFIX, "").trim();
}
