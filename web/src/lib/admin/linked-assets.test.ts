import { describe, expect, it } from "vitest";

import {
    extractLinkedAssetChanges,
    formatLinkedAssetHealthStatusLabel,
    formatLinkedAssetImpactLevelLabel,
    formatLinkedAssetLabel,
} from "./linked-assets";

describe("admin linked-asset helpers", () => {
    it("parses linked asset changes from runtime diagnostics and drops incomplete entries", () => {
        expect(
            extractLinkedAssetChanges({
                source: "session",
                severity: "blocking",
                kind: "kb_lock_blocked_search_failed",
                summary: "runtime failure",
                detected_at: "2026-03-26T09:30:00Z",
                session_id: "session-1",
                scenario_type: "sales",
                session_status: "completed",
                report_status: "completed",
                diagnostics: {
                    linked_asset_changes: [
                        {
                            asset_type: "knowledge_base",
                            asset_id: "kb-1",
                            asset_name: "石犀产品知识库",
                            admin_path: "/admin/knowledge",
                            latest_change_label: "最近文档：竞品对比",
                            change_count_7d: "2",
                            impact_level: "high",
                            health_status: "blocking",
                        },
                        {
                            asset_type: "persona",
                            asset_name: "预算压价角色",
                            latest_change_label: "缺少管理路径，应被过滤",
                        },
                    ],
                },
            }),
        ).toEqual([
            {
                asset_type: "knowledge_base",
                asset_id: "kb-1",
                asset_name: "石犀产品知识库",
                admin_path: "/admin/knowledge",
                latest_change_label: "最近文档：竞品对比",
                change_count_7d: 2,
                impact_level: "high",
                health_status: "blocking",
            },
        ]);
    });

    it("formats linked-asset labels and fallback status copy from the shared helper", () => {
        expect(
            formatLinkedAssetLabel({
                asset_type: "presentation",
                asset_name: "标准 PPT",
            }),
        ).toBe("PPT");
        expect(
            formatLinkedAssetLabel({
                asset_label: "知识库别名",
                asset_name: "石犀产品知识库",
            }),
        ).toBe("知识库别名");
        expect(formatLinkedAssetImpactLevelLabel("medium")).toBe("中影响");
        expect(formatLinkedAssetImpactLevelLabel()).toBe("低影响");
        expect(formatLinkedAssetHealthStatusLabel("warning")).toBe("告警");
        expect(formatLinkedAssetHealthStatusLabel()).toBe("健康");
    });
});
