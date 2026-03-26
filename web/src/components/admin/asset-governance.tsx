import { Activity, AlertTriangle, Clock3, ShieldAlert, ShieldCheck, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import { cn } from "@/lib/utils";

export interface AssetGovernanceAnomaly {
    source?: string;
    kind?: string;
    severity?: "warning" | "blocking" | string;
    summary?: string;
    detected_at?: string | null;
    session_id?: string | null;
}

export interface AssetGovernanceSummary {
    impact_summary?: {
        impact_level?: "low" | "medium" | "high" | string;
        recent_session_count?: number;
        active_session_count?: number;
        impacted_user_count?: number;
        last_session_at?: string | null;
    } | null;
    recent_change_summary?: {
        last_changed_at?: string | null;
        latest_change_type?: string;
        latest_change_label?: string;
        change_count_7d?: number;
        sessions_since_change?: number;
    } | null;
    health_summary?: {
        status?: "healthy" | "warning" | "blocking" | string;
        anomaly_count?: number;
        blocking_count?: number;
        warning_count?: number;
        sample_anomalies?: AssetGovernanceAnomaly[] | null;
    } | null;
}

function asRecord(value: unknown): Record<string, unknown> {
    return value && typeof value === "object" ? value as Record<string, unknown> : {};
}

function toNumber(value: unknown, fallback = 0): number {
    if (typeof value === "number" && Number.isFinite(value)) {
        return value;
    }
    if (typeof value === "string" && value.trim()) {
        const parsed = Number(value);
        if (Number.isFinite(parsed)) {
            return parsed;
        }
    }
    return fallback;
}

function toOptionalString(value: unknown): string | null {
    return typeof value === "string" && value.trim() ? value : null;
}

function normalizeAnomaly(value: unknown): AssetGovernanceAnomaly {
    const raw = asRecord(value);
    return {
        source: toOptionalString(raw.source) || undefined,
        kind: toOptionalString(raw.kind) || undefined,
        severity: toOptionalString(raw.severity) || undefined,
        summary: toOptionalString(raw.summary) || undefined,
        detected_at: toOptionalString(raw.detected_at),
        session_id: toOptionalString(raw.session_id),
    };
}

export function parseAssetGovernanceSummary(value: unknown): AssetGovernanceSummary | null {
    const raw = asRecord(value);
    if (!Object.keys(raw).length) {
        return null;
    }

    const impact = asRecord(raw.impact_summary);
    const recentChange = asRecord(raw.recent_change_summary);
    const health = asRecord(raw.health_summary);

    return {
        impact_summary: Object.keys(impact).length ? {
            impact_level: toOptionalString(impact.impact_level) || undefined,
            recent_session_count: toNumber(impact.recent_session_count, 0),
            active_session_count: toNumber(impact.active_session_count, 0),
            impacted_user_count: toNumber(impact.impacted_user_count, 0),
            last_session_at: toOptionalString(impact.last_session_at),
        } : null,
        recent_change_summary: Object.keys(recentChange).length ? {
            last_changed_at: toOptionalString(recentChange.last_changed_at),
            latest_change_type: toOptionalString(recentChange.latest_change_type) || undefined,
            latest_change_label: toOptionalString(recentChange.latest_change_label) || undefined,
            change_count_7d: toNumber(recentChange.change_count_7d, 0),
            sessions_since_change: toNumber(recentChange.sessions_since_change, 0),
        } : null,
        health_summary: Object.keys(health).length ? {
            status: toOptionalString(health.status) || undefined,
            anomaly_count: toNumber(health.anomaly_count, 0),
            blocking_count: toNumber(health.blocking_count, 0),
            warning_count: toNumber(health.warning_count, 0),
            sample_anomalies: Array.isArray(health.sample_anomalies)
                ? health.sample_anomalies.map(normalizeAnomaly)
                : [],
        } : null,
    };
}

function formatDateTime(value: string | null | undefined): string {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("zh-CN", { hour12: false });
}

function healthMeta(summary: AssetGovernanceSummary | null) {
    const status = summary?.health_summary?.status;
    const blocking = summary?.health_summary?.blocking_count || 0;
    const warning = summary?.health_summary?.warning_count || 0;

    if (status === "blocking") {
        return {
            badgeVariant: "red" as const,
            label: blocking > 0 ? `阻塞 ${blocking}` : "阻塞",
            description: warning > 0 ? `另有 ${warning} 个 warning` : "需要立即处理",
            icon: <ShieldAlert className="h-3.5 w-3.5" />,
        };
    }
    if (status === "warning") {
        return {
            badgeVariant: "orange" as const,
            label: warning > 0 ? `告警 ${warning}` : "告警",
            description: "当前无 blocking",
            icon: <AlertTriangle className="h-3.5 w-3.5" />,
        };
    }
    return {
        badgeVariant: "green" as const,
        label: "健康",
        description: "当前未发现 blocking / warning",
        icon: <ShieldCheck className="h-3.5 w-3.5" />,
    };
}

function impactMeta(summary: AssetGovernanceSummary | null) {
    const impactLevel = summary?.impact_summary?.impact_level;
    if (impactLevel === "high") {
        return { badgeVariant: "purple" as const, label: "高影响" };
    }
    if (impactLevel === "medium") {
        return { badgeVariant: "blue" as const, label: "中影响" };
    }
    return { badgeVariant: "secondary" as const, label: "低影响" };
}

function summarizeChange(summary: AssetGovernanceSummary | null): string {
    const change = summary?.recent_change_summary;
    if (!change) {
        return "最近变更暂不可用";
    }

    const label = change.latest_change_label || "最近有配置改动";
    const count = change.change_count_7d || 0;
    const sinceChange = change.sessions_since_change || 0;
    const countText = count > 0 ? `近 7 天 ${count} 次变更` : "近 7 天无新增变更";
    const sinceChangeText = sinceChange > 0 ? ` · 变更后 ${sinceChange} 个会话` : "";

    return `${label} · ${countText}${sinceChangeText}`;
}

function summarizeImpact(summary: AssetGovernanceSummary | null): string {
    const impact = summary?.impact_summary;
    if (!impact) {
        return "影响范围暂不可用";
    }

    const impactedUsers = impact.impacted_user_count || 0;
    const recentSessions = impact.recent_session_count || 0;
    const activeSessions = impact.active_session_count || 0;
    const activeText = activeSessions > 0 ? ` · 活跃 ${activeSessions}` : "";

    return `影响 ${impactedUsers} 名操作者 · 最近 ${recentSessions} 个会话${activeText}`;
}

function summarizeHealth(summary: AssetGovernanceSummary | null): string {
    const anomaly = summary?.health_summary?.sample_anomalies?.[0];
    if (anomaly?.summary) {
        return anomaly.summary;
    }
    if (summary?.health_summary?.status === "blocking") {
        return "存在 blocking 异常，建议优先核查。";
    }
    if (summary?.health_summary?.status === "warning") {
        return "存在 warning 异常，建议跟进观察。";
    }
    return "当前未发现 blocking / warning 异常。";
}

export function AssetGovernanceSummaryCard({
    summary,
    className,
}: {
    summary: AssetGovernanceSummary | null | undefined | unknown;
    className?: string;
}) {
    const parsed = parseAssetGovernanceSummary(summary);
    if (!parsed) {
        return (
            <div className={cn("rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-3 text-xs text-slate-500", className)}>
                治理数据暂不可用
            </div>
        );
    }

    const health = healthMeta(parsed);
    const impact = impactMeta(parsed);
    const changeDate = formatDateTime(parsed.recent_change_summary?.last_changed_at);
    const lastSession = formatDateTime(parsed.impact_summary?.last_session_at);

    return (
        <div className={cn("rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3", className)}>
            <div className="flex flex-wrap items-center gap-2">
                <Badge variant={health.badgeVariant} className="gap-1">
                    {health.icon}
                    {health.label}
                </Badge>
                <Badge variant={impact.badgeVariant}>{impact.label}</Badge>
                <Badge variant="secondary">
                    {parsed.recent_change_summary?.change_count_7d
                        ? `近 7 天变更 ${parsed.recent_change_summary.change_count_7d}`
                        : "近 7 天无变更"}
                </Badge>
            </div>

            <div className="mt-3 space-y-2 text-xs text-slate-600">
                <div className="flex items-start gap-2">
                    <Users className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                    <div>
                        <div className="font-medium text-slate-700">影响范围</div>
                        <div>{summarizeImpact(parsed)}</div>
                        <div className="text-slate-400">最近命中会话：{lastSession}</div>
                    </div>
                </div>
                <div className="flex items-start gap-2">
                    <Clock3 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                    <div>
                        <div className="font-medium text-slate-700">最近变更</div>
                        <div>{summarizeChange(parsed)}</div>
                        <div className="text-slate-400">最后变更：{changeDate}</div>
                    </div>
                </div>
                <div className="flex items-start gap-2">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                    <div>
                        <div className="font-medium text-slate-700">健康状况</div>
                        <div>{summarizeHealth(parsed)}</div>
                        <div className="text-slate-400">{health.description}</div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export function AssetGovernanceOverview({
    assetLabel,
    items,
    className,
}: {
    assetLabel: string;
    items: Array<{ governance_summary?: unknown | null }>;
    className?: string;
}) {
    const summaries = items
        .map((item) => parseAssetGovernanceSummary(item.governance_summary))
        .filter((item): item is AssetGovernanceSummary => Boolean(item));

    const highImpactCount = summaries.filter((item) => item.impact_summary?.impact_level === "high").length;
    const blockingCount = summaries.filter((item) => item.health_summary?.status === "blocking").length;
    const warningCount = summaries.filter((item) => item.health_summary?.status === "warning").length;
    const changedCount = summaries.filter((item) => (item.recent_change_summary?.change_count_7d || 0) > 0).length;

    const overviewCards = [
        {
            title: "高影响资产",
            value: String(highImpactCount),
            detail: `${assetLabel}中当前最可能影响范围较大的项`,
            tone: highImpactCount > 0 ? "border-purple-200 bg-purple-50/70" : "border-slate-200 bg-white",
            icon: <Users className="h-4 w-4" />,
        },
        {
            title: "阻塞异常",
            value: String(blockingCount),
            detail: "需要立即处理的 blocking 资产",
            tone: blockingCount > 0 ? "border-red-200 bg-red-50/70" : "border-slate-200 bg-white",
            icon: <ShieldAlert className="h-4 w-4" />,
        },
        {
            title: "告警资产",
            value: String(warningCount),
            detail: "存在 warning、但尚未阻塞的项",
            tone: warningCount > 0 ? "border-amber-200 bg-amber-50/70" : "border-slate-200 bg-white",
            icon: <AlertTriangle className="h-4 w-4" />,
        },
        {
            title: "近 7 天有变更",
            value: String(changedCount),
            detail: "已发生变更，建议结合会话命中回看",
            tone: changedCount > 0 ? "border-blue-200 bg-blue-50/70" : "border-slate-200 bg-white",
            icon: <Activity className="h-4 w-4" />,
        },
    ];

    return (
        <GlassCard className={cn("p-5", className)}>
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-sm font-bold text-slate-900">治理视图</h2>
                    <p className="text-xs text-slate-500">
                        在当前资产页直接看最近变更、异常健康和可能影响范围，不再来回切到 support/runtime 才知道发生了什么。
                    </p>
                </div>
                <Badge variant="secondary">已覆盖 {summaries.length}/{items.length || 0} 个{assetLabel}</Badge>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                {overviewCards.map((card) => (
                    <article key={card.title} className={cn("rounded-2xl border p-4 shadow-sm", card.tone)}>
                        <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
                            {card.icon}
                            <span>{card.title}</span>
                        </div>
                        <div className="mt-3 text-2xl font-black text-slate-900 tabular-nums">{card.value}</div>
                        <p className="mt-2 text-xs text-slate-500 text-pretty">{card.detail}</p>
                    </article>
                ))}
            </div>
        </GlassCard>
    );
}
