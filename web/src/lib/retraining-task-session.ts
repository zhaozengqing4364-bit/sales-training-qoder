export const RETRAINING_TASK_SESSION_LINK_VERSION = "retraining_task_session_link_v1";

export interface RetrainingTaskSessionLink {
    schema_version: typeof RETRAINING_TASK_SESSION_LINK_VERSION;
    task_id: string;
    source_session_id: string;
    source_review_id: string;
    started_at: string;
}

function getStorage(): Storage | null {
    if (typeof window === "undefined") {
        return null;
    }
    return window.localStorage;
}

export function getRetrainingTaskSessionStorageKey(sessionId: string): string {
    return `qoder.retrainingTaskSession.v1:${sessionId}`;
}

function isRetrainingTaskSessionLink(value: unknown): value is RetrainingTaskSessionLink {
    const record = value && typeof value === "object"
        ? value as Partial<RetrainingTaskSessionLink>
        : null;

    return Boolean(
        record
        && record.schema_version === RETRAINING_TASK_SESSION_LINK_VERSION
        && typeof record.task_id === "string"
        && typeof record.source_session_id === "string"
        && typeof record.source_review_id === "string"
        && typeof record.started_at === "string",
    );
}

export function persistRetrainingTaskSessionLink(
    sessionId: string,
    link: Omit<RetrainingTaskSessionLink, "schema_version" | "started_at"> & {
        started_at?: string;
    },
): void {
    const storage = getStorage();
    if (!storage) {
        return;
    }

    storage.setItem(
        getRetrainingTaskSessionStorageKey(sessionId),
        JSON.stringify({
            schema_version: RETRAINING_TASK_SESSION_LINK_VERSION,
            started_at: link.started_at ?? new Date().toISOString(),
            task_id: link.task_id,
            source_session_id: link.source_session_id,
            source_review_id: link.source_review_id,
        } satisfies RetrainingTaskSessionLink),
    );
}

export function readRetrainingTaskSessionLink(sessionId: string): RetrainingTaskSessionLink | null {
    const storage = getStorage();
    if (!storage) {
        return null;
    }

    const raw = storage.getItem(getRetrainingTaskSessionStorageKey(sessionId));
    if (!raw) {
        return null;
    }

    try {
        const parsed = JSON.parse(raw);
        if (isRetrainingTaskSessionLink(parsed)) {
            return parsed;
        }
    } catch {
        // Invalid client cache is cleared below.
    }

    storage.removeItem(getRetrainingTaskSessionStorageKey(sessionId));
    return null;
}

export function clearRetrainingTaskSessionLink(sessionId: string): void {
    const storage = getStorage();
    if (!storage) {
        return;
    }
    storage.removeItem(getRetrainingTaskSessionStorageKey(sessionId));
}
