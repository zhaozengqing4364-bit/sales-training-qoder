import { describe, expect, it } from "vitest";

import {
    buildPracticeWebSocketUrl,
    createPendingMessageQueue,
    nextReconnectDelay,
    toCloseReasonMessage,
} from "./transport";

describe("websocket transport helpers", () => {
    it("builds the runtime websocket url from transport inputs without auth token query params", () => {
        const url = buildPracticeWebSocketUrl({
            baseUrl: "ws://localhost:3444/api/v1",
            scenarioType: "presentation",
            sessionId: "session-1",
            agentId: "agent-1",
            personaId: "persona-1",
            voiceMode: "stepfun_realtime",
            traceId: "trace-1",
        });

        expect(url).toBe(
            "ws://localhost:3444/api/v1/ws/presentation?session_id=session-1&agent_id=agent-1&persona_id=persona-1&voice_mode=stepfun_realtime&trace_id=trace-1",
        );
        expect(url).not.toContain("token=");
    });

    it("only queues handshake-safe outbound messages and keeps high priority at the front", () => {
        const queue = createPendingMessageQueue(3);

        queue.enqueue(
            { type: "text", timestamp: "2026-04-13T00:00:00Z", data: { text: "hello" } },
            { connectionState: "connecting" },
        );
        queue.enqueue(
            { type: "interrupt", timestamp: "2026-04-13T00:00:01Z", data: { reason: "user_speaking" }, priority: "high" },
            { connectionState: "connecting" },
        );
        queue.enqueue(
            { type: "audio_chunk", timestamp: "2026-04-13T00:00:02Z", data: { audio: "..." } },
            { connectionState: "connecting" },
        );
        queue.enqueue(
            { type: "text", timestamp: "2026-04-13T00:00:03Z", data: { text: "ignored" } },
            { connectionState: "reconnecting" },
        );

        expect(queue.snapshot()).toEqual([
            expect.objectContaining({ type: "interrupt", priority: "high" }),
            expect.objectContaining({ type: "text", data: { text: "hello" } }),
        ]);
    });

    it("hides raw upstream idle-timeout reasons from the learner-facing reconnect copy", () => {
        expect(toCloseReasonMessage("too long without operation")).toBeNull();
        expect(toCloseReasonMessage("Too Long Without Operatio")).toBeNull();
    });

    it("caps reconnect delay with the shared backoff policy", () => {
        expect(nextReconnectDelay(0)).toBe(1000);
        expect(nextReconnectDelay(4)).toBe(16000);
        expect(nextReconnectDelay(8)).toBe(30000);
    });
});
