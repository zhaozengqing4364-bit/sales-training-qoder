import type {
    ConfigAssetCenterHealthStatus,
    ConfigAssetCenterDualReadMismatchSample,
    SupportRuntimeConfigAssetCenter,
    SupportRuntimeOverview,
} from "@/lib/api/types";

export interface ConfigAssetCenterObservabilityViewModel {
    available: boolean;
    status: ConfigAssetCenterHealthStatus;
    statusLabel: string;
    dualRead: {
        available: boolean;
        enabled: boolean;
        mismatchCount: number;
        matchedCount: number;
        lookupCount: number;
        mismatchRateLabel: string;
        authorityLabel: string;
        sampleMismatches: ConfigAssetCenterDualReadMismatchSample[];
    };
    projectionSync: {
        available: boolean;
        statusLabel: string;
        lastSyncAtLabel: string;
        packsSynced: number;
        packsFailed: number;
        recentFailures: Array<{ code: string; reason: string }>;
    };
    assetResolution: {
        available: boolean;
        sessionCount: number;
        modeBreakdown: Array<{ mode: string; label: string; count: number }>;
        legacyWarningSessions: number;
        frozenRefSessions: number;
    };
}

const ASSET_RESOLUTION_MODE_LABELS: Record<string, string> = {
    direct_practice_live: "Direct practice（实时资产）",
    template_legacy_live: "Template legacy live（未冻结 refs）",
    template_frozen_refs: "Template frozen refs（发布期冻结）",
};

const PROJECTION_SYNC_STATUS_LABELS: Record<string, string> = {
    ok: "同步成功",
    failed: "同步失败",
    unknown: "状态未知",
};

const HEALTH_STATUS_LABELS: Record<ConfigAssetCenterHealthStatus, string> = {
    healthy: "健康",
    warning: "告警",
    blocking: "阻塞",
    unknown: "待观测",
};

function asRecord(value: unknown): Record<string, unknown> | null {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return null;
    }
    return value as Record<string, unknown>;
}

function readNumber(value: unknown): number {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
}

function readOptionalString(value: unknown): string | null {
    if (value == null) {
        return null;
    }
    const text = String(value).trim();
    return text || null;
}

function formatDateTime(value: string | null | undefined): string {
    if (!value) {
        return "暂无记录";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString("zh-CN", { hour12: false });
}

function formatMismatchRate(mismatchCount: number, lookupCount: number): string {
    if (lookupCount <= 0) {
        return "—";
    }
    return `${((mismatchCount / lookupCount) * 100).toFixed(1)}%`;
}

export function formatAssetResolutionModeLabel(mode: string): string {
    const normalized = mode.trim();
    if (!normalized) {
        return "未知模式";
    }
    return ASSET_RESOLUTION_MODE_LABELS[normalized] || normalized;
}

export function formatProjectionSyncStatusLabel(status: string | null | undefined): string {
    const normalized = String(status || "unknown").trim().toLowerCase();
    return PROJECTION_SYNC_STATUS_LABELS[normalized] || status || "状态未知";
}

export function formatConfigAssetCenterHealthLabel(
    status: ConfigAssetCenterHealthStatus,
): string {
    return HEALTH_STATUS_LABELS[status] || HEALTH_STATUS_LABELS.unknown;
}

function normalizeDualReadMismatchSample(
    value: unknown,
): ConfigAssetCenterDualReadMismatchSample | null {
    const record = asRecord(value);
    if (!record) {
        return null;
    }
    const code = readOptionalString(record.code);
    if (!code) {
        return null;
    }
    return {
        code,
        phase_a_hash: readOptionalString(record.phase_a_hash),
        phase_b1_hash: readOptionalString(record.phase_b1_hash),
    };
}

function normalizeConfigAssetCenterBlock(
    value: unknown,
): SupportRuntimeConfigAssetCenter | null {
    const record = asRecord(value);
    if (!record) {
        return null;
    }

    const dualReadRecord = asRecord(record.dual_read);
    const projectionSyncRecord = asRecord(record.projection_sync);
    const assetResolutionRecord = asRecord(record.asset_resolution);

    const dualRead = dualReadRecord
        ? {
            enabled: Boolean(dualReadRecord.enabled),
            authority: readOptionalString(dualReadRecord.authority),
            lookup_count: readNumber(dualReadRecord.lookup_count),
            mismatch_count: readNumber(dualReadRecord.mismatch_count),
            matched_count: readNumber(dualReadRecord.matched_count),
            mismatch_rate:
                dualReadRecord.mismatch_rate == null
                    ? null
                    : Number(dualReadRecord.mismatch_rate),
            sample_mismatches: Array.isArray(dualReadRecord.sample_mismatches)
                ? dualReadRecord.sample_mismatches
                    .map(normalizeDualReadMismatchSample)
                    .filter((item): item is ConfigAssetCenterDualReadMismatchSample => Boolean(item))
                : [],
        }
        : undefined;

    const projectionSync = projectionSyncRecord
        ? {
            status: readOptionalString(projectionSyncRecord.status),
            last_sync_at: readOptionalString(projectionSyncRecord.last_sync_at),
            packs_synced: readNumber(projectionSyncRecord.packs_synced),
            packs_failed: readNumber(projectionSyncRecord.packs_failed),
            recent_failures: Array.isArray(projectionSyncRecord.recent_failures)
                ? projectionSyncRecord.recent_failures
                    .map((entry) => {
                        const failure = asRecord(entry);
                        if (!failure) {
                            return null;
                        }
                        return {
                            code: readOptionalString(failure.code),
                            reason: readOptionalString(failure.reason),
                        };
                    })
                    .filter((entry): entry is { code: string | null; reason: string | null } => Boolean(entry))
                : [],
        }
        : undefined;

    const assetResolution = assetResolutionRecord
        ? {
            session_count: readNumber(assetResolutionRecord.session_count),
            mode_breakdown: Array.isArray(assetResolutionRecord.mode_breakdown)
                ? assetResolutionRecord.mode_breakdown
                    .map((entry) => {
                        const item = asRecord(entry);
                        if (!item) {
                            return null;
                        }
                        const mode = readOptionalString(item.mode);
                        if (!mode) {
                            return null;
                        }
                        return {
                            mode,
                            count: readNumber(item.count),
                        };
                    })
                    .filter((entry): entry is { mode: string; count: number } => Boolean(entry))
                : [],
            legacy_warning_sessions: readNumber(assetResolutionRecord.legacy_warning_sessions),
            frozen_ref_sessions: readNumber(assetResolutionRecord.frozen_ref_sessions),
        }
        : undefined;

    const status = readOptionalString(record.status);
    const normalizedStatus = status === "healthy"
        || status === "warning"
        || status === "blocking"
        || status === "unknown"
        ? status
        : undefined;

    if (!dualRead && !projectionSync && !assetResolution && !normalizedStatus) {
        return null;
    }

    return {
        status: normalizedStatus,
        dual_read: dualRead,
        projection_sync: projectionSync,
        asset_resolution: assetResolution,
    };
}

function inferHealthStatus(
    block: SupportRuntimeConfigAssetCenter,
): ConfigAssetCenterHealthStatus {
    if (
        block.status === "healthy"
        || block.status === "warning"
        || block.status === "blocking"
        || block.status === "unknown"
    ) {
        return block.status;
    }

    const mismatchCount = block.dual_read?.mismatch_count ?? 0;
    const projectionFailed = String(block.projection_sync?.status || "").toLowerCase() === "failed";
    const legacySessions = block.asset_resolution?.legacy_warning_sessions ?? 0;

    if (projectionFailed || mismatchCount > 0 || legacySessions > 0) {
        return "warning";
    }

    if (block.dual_read || block.projection_sync || block.asset_resolution) {
        return "healthy";
    }

    return "unknown";
}

export function normalizeConfigAssetCenterObservability(
    overview: SupportRuntimeOverview | null | undefined,
): ConfigAssetCenterObservabilityViewModel {
    const block = normalizeConfigAssetCenterBlock(overview?.config_asset_center);
    const available = Boolean(block);

    if (!block) {
        return {
            available: false,
            status: "unknown",
            statusLabel: formatConfigAssetCenterHealthLabel("unknown"),
            dualRead: {
                available: false,
                enabled: false,
                mismatchCount: 0,
                matchedCount: 0,
                lookupCount: 0,
                mismatchRateLabel: "—",
                authorityLabel: "暂无数据",
                sampleMismatches: [],
            },
            projectionSync: {
                available: false,
                statusLabel: "暂无数据",
                lastSyncAtLabel: "暂无记录",
                packsSynced: 0,
                packsFailed: 0,
                recentFailures: [],
            },
            assetResolution: {
                available: false,
                sessionCount: 0,
                modeBreakdown: [],
                legacyWarningSessions: 0,
                frozenRefSessions: 0,
            },
        };
    }

    const status = inferHealthStatus(block);
    const dualRead = block.dual_read;
    const projectionSync = block.projection_sync;
    const assetResolution = block.asset_resolution;

    const mismatchCount = dualRead?.mismatch_count ?? 0;
    const matchedCount = dualRead?.matched_count ?? 0;
    const lookupCount = dualRead?.lookup_count ?? (mismatchCount + matchedCount);

    return {
        available,
        status,
        statusLabel: formatConfigAssetCenterHealthLabel(status),
        dualRead: {
            available: Boolean(dualRead),
            enabled: Boolean(dualRead?.enabled),
            mismatchCount,
            matchedCount,
            lookupCount,
            mismatchRateLabel: formatMismatchRate(mismatchCount, lookupCount),
            authorityLabel: dualRead?.authority || (dualRead?.enabled ? "phase_a" : "disabled"),
            sampleMismatches: dualRead?.sample_mismatches || [],
        },
        projectionSync: {
            available: Boolean(projectionSync),
            statusLabel: formatProjectionSyncStatusLabel(projectionSync?.status),
            lastSyncAtLabel: formatDateTime(projectionSync?.last_sync_at),
            packsSynced: projectionSync?.packs_synced ?? 0,
            packsFailed: projectionSync?.packs_failed ?? 0,
            recentFailures: (projectionSync?.recent_failures || [])
                .map((entry) => ({
                    code: entry.code || "unknown",
                    reason: entry.reason || "未记录原因",
                })),
        },
        assetResolution: {
            available: Boolean(assetResolution),
            sessionCount: assetResolution?.session_count ?? 0,
            modeBreakdown: (assetResolution?.mode_breakdown || []).map((entry) => ({
                mode: entry.mode,
                label: formatAssetResolutionModeLabel(entry.mode),
                count: entry.count,
            })),
            legacyWarningSessions: assetResolution?.legacy_warning_sessions ?? 0,
            frozenRefSessions: assetResolution?.frozen_ref_sessions ?? 0,
        },
    };
}
