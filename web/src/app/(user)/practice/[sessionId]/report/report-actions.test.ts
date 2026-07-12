import { beforeEach, describe, expect, it } from "vitest";

import {
    buildPresentationPagePracticePath,
    buildPresentationPageReplayPath,
    buildReplayDeepLink,
    buildRetrySessionPath,
    buildSessionReportPath,
    getRetryFallbackPath,
    persistHighlightReviewItems,
    readHighlightReviewItems,
} from "./report-actions";

describe("report actions", () => {
    beforeEach(() => {
        window.localStorage.clear();
    });

    it("encodes route identifiers and query intent", () => {
        expect(buildSessionReportPath("source/a?b")).toBe(
            "/practice/source%2Fa%3Fb/report",
        );
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

    it("drops corrupt highlight storage and persists only the review limit", () => {
        const storageKey = "qoder.highlightReviewList.v1:source/1";
        window.localStorage.setItem(storageKey, "{broken");

        expect(readHighlightReviewItems("source/1")).toEqual([]);
        expect(window.localStorage.getItem(storageKey)).toBeNull();

        persistHighlightReviewItems(
            "source/1",
            Array.from({ length: 4 }, (_, index) => ({
                id: `highlight-${index}`,
                source_session_id: "source/1",
                turn_number: index + 1,
                content: `content-${index}`,
                reason: null,
                stage_name: null,
                issue_label: null,
                suggested_response: null,
            })),
        );

        expect(readHighlightReviewItems("source/1")).toHaveLength(3);
        expect(readHighlightReviewItems("source/1").map((item) => item.id)).toEqual([
            "highlight-0",
            "highlight-1",
            "highlight-2",
        ]);
    });
});
