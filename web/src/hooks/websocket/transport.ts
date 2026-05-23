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

const FATAL_WS_CLOSE_CODES = new Set([
    4000,
    4001,
    4003,
    4400,
    4409,
    4410,
    4411,
    4412,
    4413,
]);

const FATAL_WS_CLOSE_USER_MESSAGES: Record<number, string> = {
    4000: "未配置或无效的 StepFun 语音密钥，无法使用实时语音模式。",
    4001: "登录状态无效，请重新登录后再进入练习。",
    4003: "无权访问该演练会话。",
    4400: "会话 ID 无效，请返回训练入口重新进入。",
    4409: "会话类型不匹配，请从正确入口进入练习。",
    4410: "知识库未绑定，请联系管理员配置后再练。",
    4411: "会话缺少智能体或客户画像，请返回入口重新创建会话。",
    4412: "旧版语音模式已停用，请使用实时语音模式。",
    4413: "考核运行配置不完整，请联系管理员检查考官与题库。",
};

export function isFatalWebSocketCloseCode(code: number): boolean {
    return FATAL_WS_CLOSE_CODES.has(code);
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

export function resolveWebSocketCloseUserMessage(
    reason: string,
    code?: number,
): string | null {
    if (typeof code === "number" && FATAL_WS_CLOSE_USER_MESSAGES[code]) {
        return FATAL_WS_CLOSE_USER_MESSAGES[code];
    }
    return toCloseReasonMessage(reason);
}

export function nextReconnectDelay(attempt: number): number {
    return Math.min(1000 * Math.pow(2, attempt), 30000);
}

export const PRACTICE_SESSION_COOKIE_NAME = "app_session";

const ABNORMAL_CLOSE_BURST_WINDOW_MS = 15_000;
const ABNORMAL_CLOSE_BURST_LIMIT = 4;

function readBrowserCookie(name: string): string | null {
    if (typeof document === "undefined") {
        return null;
    }

    const encodedName = `${encodeURIComponent(name)}=`;
    const cookieEntry = document.cookie
        .split(";")
        .map((item) => item.trim())
        .find((item) => item.startsWith(encodedName));

    if (!cookieEntry) {
        return null;
    }

    const cookieValue = cookieEntry.slice(encodedName.length);
    if (!cookieValue) {
        return null;
    }

    try {
        return decodeURIComponent(cookieValue);
    } catch {
        return cookieValue;
    }
}

/** Prefer session cookie; fall back to legacy localStorage token for dev compatibility. */
export function resolvePracticeWebSocketAuthToken(): string | null {
    const sessionCookie = readBrowserCookie(PRACTICE_SESSION_COOKIE_NAME);
    if (sessionCookie) {
        return sessionCookie;
    }

    if (typeof localStorage === "undefined") {
        return null;
    }

    const legacyToken = localStorage.getItem("token")?.trim();
    return legacyToken || null;
}

/** First handshake never completed — retrying usually means backend down or uvicorn --reload. */
export function shouldFailFastOnHandshake1006(
    closeCode: number,
    hasOpenedOnce: boolean,
    reconnectAttempt: number,
): boolean {
    return closeCode === 1006 && !hasOpenedOnce && reconnectAttempt === 0;
}

export function shouldTreatAsAbnormalCloseBurst(
    closeCode: number,
    recentCloseTimestampsMs: number[],
    nowMs: number = Date.now(),
): boolean {
    if (closeCode !== 1006) {
        return false;
    }

    const recent = recentCloseTimestampsMs.filter(
        (timestamp) => nowMs - timestamp < ABNORMAL_CLOSE_BURST_WINDOW_MS,
    );
    recent.push(nowMs);
    recentCloseTimestampsMs.length = 0;
    recentCloseTimestampsMs.push(...recent);
    return recent.length >= ABNORMAL_CLOSE_BURST_LIMIT;
}

export function buildPracticeWebSocketUrl(input: {
    baseUrl: string;
    scenarioType: string;
    sessionId: string;
    agentId?: string;
    personaId?: string;
    voiceMode?: string;
    traceId: string;
    authToken?: string | null;
}): string {
    let url = `${input.baseUrl}/ws/${input.scenarioType}?session_id=${input.sessionId}`;
    if (input.agentId) url += `&agent_id=${input.agentId}`;
    if (input.personaId) url += `&persona_id=${input.personaId}`;
    if (input.voiceMode) url += `&voice_mode=${input.voiceMode}`;
    if (input.authToken) {
        url += `&token=${encodeURIComponent(input.authToken)}`;
    }
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
