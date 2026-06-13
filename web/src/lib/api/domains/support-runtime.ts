import type {
    LinkedAssetChangeReference,
    SupportRuntimeFaultDiagnostics,
    SupportRuntimeFaultsResponse,
    SupportRuntimeOverview,
} from "../types";
import type { ApiRequest } from "./shared";
import {
    buildQueryString,
    toNullableStringValue,
    toNumberValue,
    toRecord,
    toStringValue,
} from "./shared";

type SupportRuntimeDomainDependencies = {
    request: ApiRequest;
};

function normalizeLinkedAssetChangeReference(value: unknown): LinkedAssetChangeReference | null {
    const raw = toRecord(value);
    const assetName = toStringValue(raw.asset_name).trim();
    const adminPath = toStringValue(raw.admin_path).trim();
    const latestChangeLabel = toStringValue(raw.latest_change_label).trim();

    if (!assetName || !adminPath || !latestChangeLabel) {
        return null;
    }

    return {
        asset_type: toStringValue(raw.asset_type),
        asset_label: toStringValue(raw.asset_label),
        asset_id: toStringValue(raw.asset_id),
        asset_name: assetName,
        admin_path: adminPath,
        latest_change_label: latestChangeLabel,
        latest_change_type: toStringValue(raw.latest_change_type),
        last_changed_at: toNullableStringValue(raw.last_changed_at),
        change_count_7d: toNumberValue(raw.change_count_7d, 0),
        sessions_since_change: toNumberValue(raw.sessions_since_change, 0),
        impact_level: toStringValue(raw.impact_level, "low"),
        health_status: toStringValue(raw.health_status, "healthy"),
    };
}

function normalizeSupportRuntimeFaultDiagnostics(value: unknown): SupportRuntimeFaultDiagnostics {
    const raw = toRecord(value);
    const linkedAssetChanges = Array.isArray(raw.linked_asset_changes)
        ? raw.linked_asset_changes
            .map(normalizeLinkedAssetChangeReference)
            .filter((item): item is LinkedAssetChangeReference => Boolean(item))
        : [];

    return {
        ...raw,
        linked_asset_changes: linkedAssetChanges,
    };
}

function normalizeSupportRuntimeFaultItem(
    input: unknown,
): SupportRuntimeFaultsResponse["items"][number] {
    const raw = toRecord(input);
    return {
        source: toStringValue(raw.source),
        severity: raw.severity === "warning" ? "warning" : "blocking",
        kind: toStringValue(raw.kind),
        summary: toStringValue(raw.summary),
        detected_at: toNullableStringValue(raw.detected_at),
        session_id: toNullableStringValue(raw.session_id),
        scenario_type: toNullableStringValue(raw.scenario_type),
        session_status: toNullableStringValue(raw.session_status),
        report_status: toNullableStringValue(raw.report_status),
        diagnostics: normalizeSupportRuntimeFaultDiagnostics(raw.diagnostics),
    };
}

function normalizeSupportRuntimeFaultsResponse(input: unknown): SupportRuntimeFaultsResponse {
    const raw = toRecord(input);
    return {
        generated_at: toStringValue(raw.generated_at),
        items: Array.isArray(raw.items) ? raw.items.map(normalizeSupportRuntimeFaultItem) : [],
        count: toNumberValue(raw.count, 0),
        limit: toNumberValue(raw.limit, 0),
        severity: raw.severity === "warning" || raw.severity === "blocking"
            ? raw.severity
            : null,
    };
}

export function createSupportRuntimeDomain({
    request,
}: SupportRuntimeDomainDependencies) {
    return {
        getOverview: async (params?: { window_hours?: number }) => {
            const query = buildQueryString({
                window_hours: params?.window_hours,
            });
            return request<SupportRuntimeOverview>(`/support/runtime/overview${query}`);
        },

        getFaults: async (params?: { limit?: number; severity?: "blocking" | "warning" }) => {
            const query = buildQueryString({
                limit: params?.limit,
                severity: params?.severity,
            });
            const result = await request<SupportRuntimeFaultsResponse>(
                `/support/runtime/faults${query}`,
            );
            return normalizeSupportRuntimeFaultsResponse(result);
        },
    };
}
