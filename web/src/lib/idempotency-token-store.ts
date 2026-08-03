import { generateClientId } from "./client-id";

export interface IdempotencyTokenStore {
    tokenFor(inputKey: string): string;
    complete(inputKey: string): void;
}

export function createIdempotencyTokenStore(): IdempotencyTokenStore {
    const tokens = new Map<string, string>();

    return {
        tokenFor(inputKey) {
            const existing = tokens.get(inputKey);
            if (existing) {
                return existing;
            }
            const persisted = readPersistedToken(inputKey);
            if (persisted) {
                tokens.set(inputKey, persisted);
                return persisted;
            }
            const token = generateClientId();
            tokens.set(inputKey, token);
            persistToken(inputKey, token);
            return token;
        },
        complete(inputKey) {
            tokens.delete(inputKey);
            removePersistedToken(inputKey);
        },
    };
}

function storageKey(inputKey: string): string {
    let hash = 2_166_136_261;
    for (let index = 0; index < inputKey.length; index += 1) {
        hash ^= inputKey.charCodeAt(index);
        hash = Math.imul(hash, 16_777_619);
    }
    return `newcomer-training:idempotency:${(hash >>> 0).toString(16)}`;
}

function readPersistedToken(inputKey: string): string | null {
    try {
        return globalThis.sessionStorage?.getItem(storageKey(inputKey)) ?? null;
    } catch {
        return null;
    }
}

function persistToken(inputKey: string, token: string): void {
    try {
        globalThis.sessionStorage?.setItem(storageKey(inputKey), token);
    } catch {
        // The in-memory token still protects retries in this page lifecycle.
    }
}

function removePersistedToken(inputKey: string): void {
    try {
        globalThis.sessionStorage?.removeItem(storageKey(inputKey));
    } catch {
        // Storage can be disabled; there is nothing else to clean up.
    }
}
