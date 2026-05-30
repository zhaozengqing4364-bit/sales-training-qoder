import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import type { ConfigAssetCenterObservabilityViewModel } from "@/lib/admin/config-asset-center-observability";

function healthBadgeVariant(
    status: ConfigAssetCenterObservabilityViewModel["status"],
): "green" | "orange" | "red" | "gray" {
    if (status === "healthy") {
        return "green";
    }
    if (status === "warning") {
        return "orange";
    }
    if (status === "blocking") {
        return "red";
    }
    return "gray";
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
    return (
        <div className="rounded-2xl border border-slate-100 bg-white/80 p-4">
            <div className="text-xs font-bold uppercase tracking-widest text-slate-500">{label}</div>
            <div className="mt-2 text-2xl font-black text-slate-900">{value}</div>
        </div>
    );
}

export function ConfigAssetCenterObservabilityPanel({
    model,
    windowHours,
}: {
    model: ConfigAssetCenterObservabilityViewModel;
    windowHours: number;
}) {
    return (
        <GlassCard className="space-y-4 p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 className="text-xl font-black text-slate-900">Config Asset Center 运行时健康</h2>
                    <p className="mt-2 text-sm text-slate-600">
                        聚合最近 {windowHours} 小时的双读对账、projection sync 与 asset resolution 模式分布。
                        后端 #95 观测字段未返回时，本节会显示待观测状态而非阻塞页面。
                    </p>
                </div>
                <Badge variant={healthBadgeVariant(model.status)}>{model.statusLabel}</Badge>
            </div>

            {!model.available ? (
                <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4 text-sm text-slate-600">
                    当前 runtime overview 尚未返回 <code className="font-mono text-xs">config_asset_center</code> 字段。
                    双读 mismatch、projection sync 与 asset resolution breakdown 将在 #95 后端观测上线后自动展示。
                </div>
            ) : null}

            <div className="grid gap-4 xl:grid-cols-3">
                <div className="space-y-3 rounded-2xl border border-slate-100 bg-white/80 p-4">
                    <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-bold text-slate-900">Dual-read 对账</div>
                        <Badge variant={model.dualRead.enabled ? "blue" : "gray"}>
                            {model.dualRead.enabled ? "已启用" : "未启用"}
                        </Badge>
                    </div>
                    {model.dualRead.available ? (
                        <>
                            <div className="grid gap-3 sm:grid-cols-2">
                                <MetricCard label="Mismatch" value={model.dualRead.mismatchCount} />
                                <MetricCard label="Matched" value={model.dualRead.matchedCount} />
                                <MetricCard label="Lookup" value={model.dualRead.lookupCount} />
                                <MetricCard label="Mismatch rate" value={model.dualRead.mismatchRateLabel} />
                            </div>
                            <div className="text-xs text-slate-600">
                                权威读源：<span className="font-mono text-slate-800">{model.dualRead.authorityLabel}</span>
                            </div>
                            {model.dualRead.sampleMismatches.length > 0 ? (
                                <div className="space-y-2">
                                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">
                                        Sample mismatches
                                    </div>
                                    {model.dualRead.sampleMismatches.slice(0, 6).map((item) => (
                                        <div
                                            key={item.code}
                                            className="rounded-xl border border-amber-100 bg-amber-50/70 p-3 text-xs text-slate-700"
                                        >
                                            <div className="font-semibold text-slate-900">{item.code}</div>
                                            <div className="mt-1 font-mono">phase_a: {item.phase_a_hash || "—"}</div>
                                            <div className="font-mono">phase_b1: {item.phase_b1_hash || "—"}</div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-slate-500">当前窗口内暂无 mismatch 样本。</p>
                            )}
                        </>
                    ) : (
                        <p className="text-sm text-slate-500">dual_read 摘要暂不可用。</p>
                    )}
                </div>

                <div className="space-y-3 rounded-2xl border border-slate-100 bg-white/80 p-4">
                    <div className="text-sm font-bold text-slate-900">Projection sync</div>
                    {model.projectionSync.available ? (
                        <>
                            <div className="grid gap-3 sm:grid-cols-2">
                                <MetricCard label="Status" value={model.projectionSync.statusLabel} />
                                <MetricCard label="Packs synced" value={model.projectionSync.packsSynced} />
                                <MetricCard label="Packs failed" value={model.projectionSync.packsFailed} />
                                <MetricCard label="Last sync" value={model.projectionSync.lastSyncAtLabel} />
                            </div>
                            {model.projectionSync.recentFailures.length > 0 ? (
                                <div className="space-y-2">
                                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">
                                        Recent failures
                                    </div>
                                    {model.projectionSync.recentFailures.slice(0, 4).map((item) => (
                                        <div
                                            key={`${item.code}-${item.reason}`}
                                            className="rounded-xl border border-red-100 bg-red-50/70 p-3 text-xs text-slate-700"
                                        >
                                            <div className="font-semibold text-slate-900">{item.code}</div>
                                            <div className="mt-1">{item.reason}</div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-slate-500">最近无 projection sync 失败记录。</p>
                            )}
                        </>
                    ) : (
                        <p className="text-sm text-slate-500">projection_sync 摘要暂不可用。</p>
                    )}
                </div>

                <div className="space-y-3 rounded-2xl border border-slate-100 bg-white/80 p-4">
                    <div className="text-sm font-bold text-slate-900">Asset resolution 模式</div>
                    {model.assetResolution.available ? (
                        <>
                            <div className="grid gap-3 sm:grid-cols-2">
                                <MetricCard label="Sessions" value={model.assetResolution.sessionCount} />
                                <MetricCard
                                    label="Legacy warnings"
                                    value={model.assetResolution.legacyWarningSessions}
                                />
                                <MetricCard
                                    label="Frozen ref sessions"
                                    value={model.assetResolution.frozenRefSessions}
                                />
                            </div>
                            {model.assetResolution.modeBreakdown.length > 0 ? (
                                <div className="space-y-2">
                                    {model.assetResolution.modeBreakdown.map((item) => (
                                        <div
                                            key={item.mode}
                                            className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/80 px-3 py-2 text-sm"
                                        >
                                            <span className="text-slate-700">{item.label}</span>
                                            <Badge variant={item.count > 0 ? "blue" : "gray"}>{item.count}</Badge>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-slate-500">暂无 asset resolution 模式分布。</p>
                            )}
                        </>
                    ) : (
                        <p className="text-sm text-slate-500">asset_resolution 摘要暂不可用。</p>
                    )}
                </div>
            </div>
        </GlassCard>
    );
}
