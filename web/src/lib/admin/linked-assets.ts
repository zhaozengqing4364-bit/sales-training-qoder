import type { SupportRuntimeFaultItem } from "@/lib/api/types";

export type LinkedAssetChange = {
    asset_id?: string;
    asset_type?: string;
    asset_label?: string;
    asset_name?: string;
    admin_path?: string;
    latest_change_label?: string;
    change_count_7d?: number;
    impact_level?: string;
    health_status?: string;
};

function asRecord(value: unknown): Record<string, unknown> {
    return value && typeof value === "object" ? value as Record<string, unknown> : {};
}

function toOptionalString(value: unknown): string | undefined {
    return typeof value === "string" && value.trim() ? value : undefined;
}

function toNumber(value: unknown): number | undefined {
    if (typeof value === "number" && Number.isFinite(value)) {
        return value;
    }
    if (typeof value === "string" && value.trim()) {
        const parsed = Number(value);
        if (Number.isFinite(parsed)) {
            return parsed;
        }
    }
    return undefined;
}

export function parseLinkedAssetChanges(value: unknown): LinkedAssetChange[] {
    if (!Array.isArray(value)) {
        return [];
    }

    return value
        .map((entry) => {
            const raw = asRecord(entry);
            return {
                asset_id: toOptionalString(raw.asset_id),
                asset_type: toOptionalString(raw.asset_type),
                asset_label: toOptionalString(raw.asset_label),
                asset_name: toOptionalString(raw.asset_name),
                admin_path: toOptionalString(raw.admin_path),
                latest_change_label: toOptionalString(raw.latest_change_label),
                change_count_7d: toNumber(raw.change_count_7d),
                impact_level: toOptionalString(raw.impact_level),
                health_status: toOptionalString(raw.health_status),
            };
        })
        .filter((entry) => Boolean(entry.asset_name && entry.admin_path && entry.latest_change_label));
}

export function extractLinkedAssetChanges(
    fault: Pick<SupportRuntimeFaultItem, "diagnostics">,
): LinkedAssetChange[] {
    const diagnostics = asRecord(fault.diagnostics);
    return parseLinkedAssetChanges(diagnostics.linked_asset_changes);
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
