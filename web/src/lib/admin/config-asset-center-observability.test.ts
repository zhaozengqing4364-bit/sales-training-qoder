import { describe, expect, it } from "vitest";

import type { SupportRuntimeOverview } from "@/lib/api/types";

import {
    formatAssetResolutionModeLabel,
    formatConfigAssetCenterHealthLabel,
    formatProjectionSyncStatusLabel,
    normalizeConfigAssetCenterObservability,
} from "./config-asset-center-observability";

const baseOverview = {
    generated_at: "2026-05-27T10:00:00",
    window_hours: 168,
    session_health: {
        active_sessions: 0,
        total_sessions_window: 0,
        completed_sessions_window: 0,
        scoring_sessions: 0,
        stuck_scoring_sessions: 0,
        not_evaluable_completed_sessions_window: 0,
        completion_rate: 0,
    },
    release_health: {
        status: "healthy",
        blocking_count: 0,
        warning_count: 0,
        typed_anomaly_count: 0,
        blocking_sessions_count: 0,
        warning_sessions_count: 0,
        supplemental_warning_log_count: 0,
    },
    anomaly_summary: {
        blocking: [],
        warning: [],
    },
} satisfies SupportRuntimeOverview;

describe("config-asset-center-observability", () => {
    it("returns pending view model when config_asset_center is absent", () => {
        const model = normalizeConfigAssetCenterObservability(baseOverview);

        expect(model.available).toBe(false);
        expect(model.status).toBe("unknown");
        expect(model.dualRead.available).toBe(false);
        expect(model.projectionSync.available).toBe(false);
        expect(model.assetResolution.available).toBe(false);
    });

    it("normalizes dual-read, projection sync, and asset resolution breakdown", () => {
        const model = normalizeConfigAssetCenterObservability({
            ...baseOverview,
            config_asset_center: {
                status: "warning",
                dual_read: {
                    enabled: true,
                    authority: "phase_a",
                    lookup_count: 20,
                    mismatch_count: 2,
                    matched_count: 18,
                    sample_mismatches: [
                        {
                            code: "first_visit",
                            phase_a_hash: "sha256:a",
                            phase_b1_hash: "sha256:b",
                        },
                    ],
                },
                projection_sync: {
                    status: "failed",
                    last_sync_at: "2026-05-27T09:00:00",
                    packs_synced: 3,
                    packs_failed: 1,
                    recent_failures: [{ code: "renewal", reason: "hash mismatch" }],
                },
                asset_resolution: {
                    session_count: 12,
                    legacy_warning_sessions: 4,
                    frozen_ref_sessions: 6,
                    mode_breakdown: [
                        { mode: "template_frozen_refs", count: 6 },
                        { mode: "template_legacy_live", count: 4 },
                        { mode: "direct_practice_live", count: 2 },
                    ],
                },
            },
        });

        expect(model.available).toBe(true);
        expect(model.status).toBe("warning");
        expect(model.dualRead.mismatchCount).toBe(2);
        expect(model.dualRead.mismatchRateLabel).toBe("10.0%");
        expect(model.dualRead.sampleMismatches).toHaveLength(1);
        expect(model.projectionSync.statusLabel).toBe("同步失败");
        expect(model.projectionSync.recentFailures[0]?.code).toBe("renewal");
        expect(model.assetResolution.modeBreakdown).toHaveLength(3);
        expect(model.assetResolution.modeBreakdown[0]?.label).toContain("frozen refs");
    });

    it("infers warning status from mismatch count when status is omitted", () => {
        const model = normalizeConfigAssetCenterObservability({
            ...baseOverview,
            config_asset_center: {
                dual_read: {
                    enabled: true,
                    mismatch_count: 1,
                    matched_count: 9,
                },
            },
        });

        expect(model.status).toBe("warning");
        expect(formatConfigAssetCenterHealthLabel(model.status)).toBe("告警");
    });

    it("formats asset resolution and projection sync labels", () => {
        expect(formatAssetResolutionModeLabel("template_frozen_refs")).toContain("frozen refs");
        expect(formatProjectionSyncStatusLabel("ok")).toBe("同步成功");
    });
});
