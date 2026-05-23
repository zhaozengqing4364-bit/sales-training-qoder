import { debug } from "@/lib/debug";

export type PracticeWsDiagnosticEvent =
    | "connect_requested"
    | "connect_open"
    | "connect_error"
    | "connect_close"
    | "reconnect_scheduled"
    | "transport_teardown"
    | "connect_disabled"
    | "runtime_key_changed";

export interface PracticeWsDiagnosticContext {
    sessionId: string;
    scenarioType?: string;
    voiceMode?: string;
    connectionState?: string;
    reconnectAttempt?: number;
    closeCode?: number;
    closeReason?: string;
    wasClean?: boolean;
    hasOpenedOnce?: boolean;
    handshakeFailFast?: boolean;
    burstFailure?: boolean;
    shouldRetry?: boolean;
    runtimeConnectKey?: string;
    connectEnabled?: boolean;
    trigger?: string;
    [key: string]: unknown;
}

/** Structured Practice WebSocket diagnostics for local troubleshooting. */
export function logPracticeWsDiagnostic(
    event: PracticeWsDiagnosticEvent,
    context: PracticeWsDiagnosticContext,
): void {
    if (!debug.enabled()) {
        return;
    }

    debug.warn(`[PracticeWS:${event}]`, {
        ...context,
        loggedAt: new Date().toISOString(),
    });
}
