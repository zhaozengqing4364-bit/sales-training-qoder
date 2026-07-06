export interface RealtimeProviderReadinessDiagnostic {
    readonly moduleKey: string;
    readonly ready: boolean;
    readonly runtimeDescriptorId: string;
    readonly detail: string;
    readonly failureReason: string;
}

export function readRealtimeProviderReadinessDiagnostics(
    diagnostics: object | null | undefined,
): RealtimeProviderReadinessDiagnostic[] | null {
    const diagnosticsRecord = diagnostics as { realtime_provider_readiness?: unknown } | null | undefined;
    const records = diagnosticsRecord?.realtime_provider_readiness;
    if (!Array.isArray(records)) {
        return null;
    }
    return records
        .map(realtimeProviderDiagnosticFromRecord)
        .filter((item): item is RealtimeProviderReadinessDiagnostic => Boolean(item));
}

function realtimeProviderDiagnosticFromRecord(
    value: unknown,
): RealtimeProviderReadinessDiagnostic | null {
    if (!value || typeof value !== "object") {
        return null;
    }
    const record = value as Record<string, unknown>;
    const moduleKey = typeof record.module_key === "string" ? record.module_key : null;
    if (!moduleKey) {
        return null;
    }
    const snapshot = record.provider_readiness_snapshot;
    const snapshotRecord = snapshot && typeof snapshot === "object"
        ? snapshot as Record<string, unknown>
        : {};
    const ready = record.ready === true || snapshotRecord.ready === true;
    const provider = typeof snapshotRecord.provider === "string" ? snapshotRecord.provider : "unknown";
    const runtimeDescriptorId = typeof record.runtime_descriptor_id === "string"
        ? record.runtime_descriptor_id
        : "runtime 未知";
    const failureMessage = typeof snapshotRecord.failure_message === "string"
        ? snapshotRecord.failure_message
        : null;
    const failureCode = typeof snapshotRecord.failure_code === "string"
        ? snapshotRecord.failure_code
        : null;
    const failureReason = failureMessage ?? failureCode ?? "provider 未就绪";
    return {
        moduleKey,
        ready,
        runtimeDescriptorId,
        detail: ready ? `${provider} / ${runtimeDescriptorId}` : failureReason,
        failureReason,
    };
}
