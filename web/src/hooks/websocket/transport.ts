import type { ConnectionState, WSMessage } from "./types";

type PendingMessageQueueOptions = {
    connectionState: ConnectionState;
};

type PendingMessageQueue = {
    enqueue: (message: WSMessage, options: PendingMessageQueueOptions) => boolean;
    flushTo: (send: (message: WSMessage) => void) => number;
    clear: () => void;
    size: () => number;
    snapshot: () => WSMessage[];
};

export function deriveConnectionFlags(connectionState: ConnectionState): {
    isConnected: boolean;
    isConnecting: boolean;
} {
    return {
        isConnected: connectionState === "connected",
        isConnecting: connectionState === "connecting" || connectionState === "reconnecting",
    };
}

export function maskWsUrlToken(url: string): string {
    return url.replace(/([?&]token=)[^&]+/i, "$1***");
}

export function toCloseReasonMessage(reason: string): string | null {
    const normalized = reason.trim().toLowerCase();
    if (!normalized) {
        return null;
    }
    if (
        normalized.includes("too long without operation")
        || normalized.includes("too long without operatio")
    ) {
        return null;
    }
    return reason.trim();
}

export function nextReconnectDelay(attempt: number): number {
    return Math.min(1000 * Math.pow(2, attempt), 30000);
}

export function buildPracticeWebSocketUrl(input: {
    baseUrl: string;
    scenarioType: string;
    sessionId: string;
    agentId?: string;
    personaId?: string;
    voiceMode?: string;
    traceId: string;
}): string {
    let url = `${input.baseUrl}/ws/${input.scenarioType}?session_id=${input.sessionId}`;
    if (input.agentId) url += `&agent_id=${input.agentId}`;
    if (input.personaId) url += `&persona_id=${input.personaId}`;
    if (input.voiceMode) url += `&voice_mode=${input.voiceMode}`;
    url += `&trace_id=${input.traceId}`;
    return url;
}

function canQueuePendingMessage(message: WSMessage, options: PendingMessageQueueOptions): boolean {
    const canQueueDuringHandshake = options.connectionState === "connecting";
    const isRealtimeAudio = message.type === "audio_chunk" || message.type === "audio_end";
    return canQueueDuringHandshake && !isRealtimeAudio;
}

export function createPendingMessageQueue(maxPendingMessages: number): PendingMessageQueue {
    let queue: WSMessage[] = [];

    return {
        enqueue(message, options) {
            if (!canQueuePendingMessage(message, options)) {
                return false;
            }

            if (message.priority === "high") {
                queue.unshift(message);
                if (queue.length > maxPendingMessages) {
                    queue.pop();
                }
                return true;
            }

            if (queue.length >= maxPendingMessages) {
                queue.shift();
            }
            queue.push(message);
            return true;
        },

        flushTo(send) {
            if (queue.length === 0) {
                return 0;
            }
            const queuedMessages = queue;
            queue = [];
            queuedMessages.forEach(send);
            return queuedMessages.length;
        },

        clear() {
            queue = [];
        },

        size() {
            return queue.length;
        },

        snapshot() {
            return [...queue];
        },
    };
}
