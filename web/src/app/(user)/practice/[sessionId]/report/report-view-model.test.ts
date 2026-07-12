import { describe, expect, it } from "vitest";

import {
    buildSalesDimensionScores,
    formatReplayAnchorHint,
    formatRoleplayStatusLabel,
    formatScoreValue,
    formatTrendDelta,
    formatVoiceModeLabel,
    getRoleplaySummaryTone,
    getScoreLabel,
    hasEnhancedInsights,
} from "./report-view-model";

describe("report view model", () => {
    it("maps scores, trends, and transport enums to user language", () => {
        expect(getScoreLabel(91)).toBe("优秀");
        expect(formatScoreValue(Number.NaN)).toBe("--");
        expect(formatTrendDelta(2.25)).toBe("+2.3 分");
        expect(formatRoleplayStatusLabel("unknown_internal_status")).toBe(
            "未记录",
        );
        expect(formatVoiceModeLabel("internal_provider_v2")).toBe("已选择语音模式");
    });

    it("projects sales dimensions without mutating score semantics", () => {
        expect(
            buildSalesDimensionScores({ logic: 80, accuracy: null, completeness: 60 }),
        ).toEqual([
            expect.objectContaining({ name: "价值表达", score: 80 }),
            expect.objectContaining({ name: "证据与收益", score: 0 }),
            expect.objectContaining({ name: "异议推进", score: 60 }),
        ]);
    });

    it("explains resolved, degraded, and missing replay anchors", () => {
        expect(
            formatReplayAnchorHint({ status: "resolved", message_id: null, turn_number: 3 }),
        ).toContain("第 3 轮");
        expect(
            formatReplayAnchorHint({
                status: "degraded",
                message_id: null,
                turn_number: 4,
                degraded_reason: "missing_marker",
            }),
        ).toContain("高光标记缺失");
        expect(formatReplayAnchorHint({
            status: "missing",
            message_id: null,
            turn_number: null,
        })).toBe(
            "当前暂无可定位的回放片段。",
        );
    });

    it("keeps enhanced insight and compliance tone decisions deterministic", () => {
        expect(
            hasEnhancedInsights({
                key_strengths: [],
                key_improvements: ["补充客户收益证据"],
                recommendations: [],
                detailed_feedback: "",
            } as never),
        ).toBe(true);
        expect(getRoleplaySummaryTone("invalid").card).toContain("amber");
    });
});
