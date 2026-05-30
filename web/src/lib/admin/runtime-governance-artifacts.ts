import type {
    AdminAiGovernanceExplainabilityResponse,
    PublishedAssetRefRecord,
} from "@/lib/api/types";

export interface RuntimeGovernanceArtifacts {
    publishedAssetRefs: Record<string, PublishedAssetRefRecord>;
    runtimeDossier: Record<string, unknown> | null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return null;
    }
    return value as Record<string, unknown>;
}

function normalizePublishedAssetRef(value: unknown): PublishedAssetRefRecord | null {
    const record = asRecord(value);
    if (!record) {
        return null;
    }
    const assetType = String(record.asset_type || "").trim();
    if (!assetType) {
        return null;
    }
    return {
        asset_type: assetType,
        asset_id: record.asset_id == null ? null : String(record.asset_id),
        asset_code: record.asset_code == null ? null : String(record.asset_code),
        version: record.version == null ? null : String(record.version),
        content_hash: record.content_hash == null ? null : String(record.content_hash),
        snapshot_label: record.snapshot_label == null ? null : String(record.snapshot_label),
        source_bundle_key: record.source_bundle_key == null ? null : String(record.source_bundle_key),
        source_config_version_id:
            record.source_config_version_id == null ? null : String(record.source_config_version_id),
        source_config_id: record.source_config_id == null ? null : String(record.source_config_id),
        snapshot_selector: record.snapshot_selector == null ? null : String(record.snapshot_selector),
        source_snapshot_hash:
            record.source_snapshot_hash == null ? null : String(record.source_snapshot_hash),
        resolved_at: record.resolved_at == null ? null : String(record.resolved_at),
    };
}

function extractPublishedAssetRefs(source: Record<string, unknown>): Record<string, PublishedAssetRefRecord> {
    const rawRefs = source.published_asset_refs;
    if (!rawRefs || typeof rawRefs !== "object" || Array.isArray(rawRefs)) {
        return {};
    }

    const refs: Record<string, PublishedAssetRefRecord> = {};
    for (const [key, value] of Object.entries(rawRefs as Record<string, unknown>)) {
        const normalized = normalizePublishedAssetRef(value);
        if (normalized) {
            refs[key] = normalized;
        }
    }
    return refs;
}

function extractRuntimeDossier(source: Record<string, unknown>): Record<string, unknown> | null {
    const direct = asRecord(source.runtime_dossier);
    if (direct) {
        return direct;
    }

    const metrics = asRecord(source.runtime_metrics);
    const dossierFromMetrics = metrics ? asRecord(metrics.runtime_dossier) : null;
    if (dossierFromMetrics) {
        return dossierFromMetrics;
    }

    const curriculumRuntime = asRecord(source.curriculum_runtime);
    if (curriculumRuntime) {
        const nested = asRecord(curriculumRuntime.runtime_dossier);
        if (nested) {
            return nested;
        }
    }

    if (
        source.dossier_hash
        || source.asset_refs
        || source.roleplay_contract
        || source.roleplay_contract_hash
    ) {
        return source;
    }

    return null;
}

export function extractRuntimeGovernanceArtifacts(
    data: AdminAiGovernanceExplainabilityResponse,
): RuntimeGovernanceArtifacts {
    const sources = [
        data.report?.lineage?.config_bundle_snapshot,
        data.report?.payload,
        data.evidence?.input_reference,
        data.evidence?.report_evidence ?? undefined,
        data.scoring ?? undefined,
        data.knowledge ?? undefined,
    ];

    let publishedAssetRefs: Record<string, PublishedAssetRefRecord> = {};
    let runtimeDossier: Record<string, unknown> | null = null;

    for (const source of sources) {
        const record = asRecord(source);
        if (!record) {
            continue;
        }
        if (Object.keys(publishedAssetRefs).length === 0) {
            publishedAssetRefs = extractPublishedAssetRefs(record);
        }
        if (!runtimeDossier) {
            runtimeDossier = extractRuntimeDossier(record);
        }
    }

    return { publishedAssetRefs, runtimeDossier };
}

export function formatPublishedAssetRefLabel(refKey: string, ref: PublishedAssetRefRecord): string {
    const identifier = ref.asset_id || ref.asset_code || "unknown";
    return `${refKey} · ${ref.asset_type} · ${identifier}`;
}
