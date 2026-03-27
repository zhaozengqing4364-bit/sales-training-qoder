import type { LinkedAssetChangeReference, SupportRuntimeFaultItem } from "@/lib/api/types";

export type LinkedAssetChange = LinkedAssetChangeReference;

export function parseLinkedAssetChanges(
    value: LinkedAssetChange[] | null | undefined,
): LinkedAssetChange[] {
    return Array.isArray(value) ? value : [];
}

export function extractLinkedAssetChanges(
    fault: Pick<SupportRuntimeFaultItem, "diagnostics">,
): LinkedAssetChange[] {
    return parseLinkedAssetChanges(fault.diagnostics.linked_asset_changes);
}

export function formatLinkedAssetImpactLevelLabel(level?: string): string {
    if (level === "high") return "高影响";
    if (level === "medium") return "中影响";
    return "低影响";
}

export function formatLinkedAssetHealthStatusLabel(status?: string): string {
    if (status === "blocking") return "阻塞";
    if (status === "warning") return "告警";
    return "健康";
}

export function formatLinkedAssetLabel(change: Pick<LinkedAssetChange, "asset_label" | "asset_type">): string {
    if (change.asset_label) {
        return change.asset_label;
    }
    if (change.asset_type === "knowledge_base") return "知识库";
    if (change.asset_type === "persona") return "角色";
    if (change.asset_type === "presentation") return "PPT";
    if (change.asset_type === "runtime_profile") return "运行时配置";
    return "资产";
}
