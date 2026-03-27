import { describe, expect, expectTypeOf, it } from "vitest";

import type { LinkedAssetChangeReference, SupportRuntimeFaultItem } from "@/lib/api/types";
import {
    extractLinkedAssetChanges,
    formatLinkedAssetHealthStatusLabel,
    formatLinkedAssetImpactLevelLabel,
    formatLinkedAssetLabel,
} from "./linked-assets";

describe("admin linked-asset helpers", () => {
    it("returns the full shared linked-asset contract from runtime diagnostics", () => {
        const fault: Pick<SupportRuntimeFaultItem, "diagnostics"> = {
            diagnostics: {
                linked_asset_changes: [
                    {
                        asset_type: "knowledge_base",
                        asset_label: "知识库",
                        asset_id: "kb-1",
                        asset_name: "石犀产品知识库",
                        admin_path: "/admin/knowledge",
                        latest_change_label: "最近文档：竞品对比",
                        latest_change_type: "document_replace",
                        last_changed_at: "2026-03-25T08:00:00Z",
                        change_count_7d: 2,
                        sessions_since_change: 5,
                        impact_level: "high",
                        health_status: "blocking",
                    },
                ],
            },
        };

        const changes = extractLinkedAssetChanges(fault);

        expect(changes).toEqual<LinkedAssetChangeReference[]>([
            {
                asset_type: "knowledge_base",
                asset_label: "知识库",
                asset_id: "kb-1",
                asset_name: "石犀产品知识库",
                admin_path: "/admin/knowledge",
                latest_change_label: "最近文档：竞品对比",
                latest_change_type: "document_replace",
                last_changed_at: "2026-03-25T08:00:00Z",
                change_count_7d: 2,
                sessions_since_change: 5,
                impact_level: "high",
                health_status: "blocking",
            },
        ]);
    });

    it("exposes the shared linked-asset contract type from the helper", () => {
        expectTypeOf(extractLinkedAssetChanges).returns.toEqualTypeOf<LinkedAssetChangeReference[]>();
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
