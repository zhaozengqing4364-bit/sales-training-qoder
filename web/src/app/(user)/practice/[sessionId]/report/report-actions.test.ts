import { describe, expect, it } from "vitest";

import {
    buildPresentationPagePracticePath,
    buildPresentationPageReplayPath,
    buildReplayDeepLink,
    buildRetrySessionPath,
    getRetryFallbackPath,
} from "./report-actions";

describe("report actions", () => {
    it("encodes route identifiers and query intent", () => {
        expect(buildPresentationPageReplayPath("session/a?b", 3)).toBe(
            "/practice/session%2Fa%3Fb/replay?focus=presentation_page&page=3&page_anchor_status=resolved",
        );
        expect(
            buildPresentationPagePracticePath({
                sessionId: "retry/a",
                presentationId: "deck&1",
                pageNumber: 2,
                sourceSessionId: "source?1",
            }),
        ).toContain(
            "/practice/retry%2Fa?scenario_type=presentation&presentation_id=deck%261",
        );
    });

    it("builds replay anchor descriptors with reserved values safely encoded", () => {
        const path = buildReplayDeepLink("session/1", {
            focus: "main_issue",
            anchor: {
                status: "degraded",
                message_id: "message&1",
                turn_number: 4,
                degraded_reason: "missing marker",
            },
        });

        expect(path).toContain("/practice/session%2F1/replay?");
        expect(path).toContain("message_id=message%261");
        expect(path).toContain("anchor_reason=missing+marker");
    });

    it("keeps retry fallbacks in user task routes", () => {
        expect(getRetryFallbackPath({ scenario_type: "presentation" } as never)).toBe(
            "/training/presentation",
        );
        expect(getRetryFallbackPath(null)).toBe("/training/sales");
        expect(
            buildRetrySessionPath("created/1", {
                scenario_type: "sales",
                agent_id: "agent&1",
                persona_id: "persona?1",
            } as never),
        ).toContain("/practice/created%2F1?scenario_type=sales&agent_id=agent%261");
    });
});
