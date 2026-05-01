import { describe, expect, it } from "vitest";

import { normalizeInternalRecommendationPath } from "./recommendation-routing";

describe("normalizeInternalRecommendationPath", () => {
    it.each([
        ["/training", "/training"],
        ["/training/sales?focus=product_knowledge", "/training/sales?focus=product_knowledge"],
        ["/agents/agent-1?persona_id=persona-1", "/agents/agent-1?persona_id=persona-1"],
        ["/practice/session-1/report?focus=presentation_page&page=5", "/practice/session-1/report?focus=presentation_page&page=5"],
        ["/history", "/history"],
    ])("allows known internal recommendation route %s", (targetPath, expected) => {
        expect(normalizeInternalRecommendationPath(targetPath)).toEqual({
            href: expected,
            downgraded: false,
            reason: null,
        });
    });

    it.each([
        ["https://evil.example/phish", "absolute_or_protocol_url"],
        ["//evil.example/phish", "absolute_or_protocol_url"],
        ["javascript:alert(1)", "absolute_or_protocol_url"],
        ["/%2F%2Fevil.example", "unsafe_encoded_path"],
        ["/%68%74%74%70%73%3A%2F%2Fevil.example", "unsafe_encoded_path"],
        ["/training/../admin", "path_traversal"],
        ["/training/%2e%2e/admin", "path_traversal"],
        ["/admin/settings", "unsupported_route"],
        ["", "empty"],
    ])("downgrades unsafe recommendation route %s", (targetPath, reason) => {
        expect(normalizeInternalRecommendationPath(targetPath)).toEqual({
            href: "/training",
            downgraded: true,
            reason,
        });
    });
});
