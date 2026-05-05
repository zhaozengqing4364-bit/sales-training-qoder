"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    AdminGovernancePermissionsResponse,
    AdminGovernanceSettingsBacklogResponse,
} from "@/lib/api/types";
import { debug } from "@/lib/debug";

function formatList(value: string[] | undefined) {
    return (value || []).join("、") || "无";
}

export default function AdminGovernancePage() {
    const [permissions, setPermissions] = useState<AdminGovernancePermissionsResponse | null>(null);
    const [settingsBacklog, setSettingsBacklog] = useState<AdminGovernanceSettingsBacklogResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadGovernance = async () => {
        setLoading(true);
        setError(null);
        try {
            const [permissionsResponse, backlogResponse] = await Promise.all([
                api.admin.getGovernancePermissionsMatrix(),
                api.admin.getGovernanceSettingsBacklog(),
            ]);
            setPermissions(permissionsResponse);
            setSettingsBacklog(backlogResponse);
        } catch (err) {
            setError(`治理信息加载失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminGovernancePage] failed to load governance inventory", { error: err });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void Promise.resolve().then(loadGovernance);
    }, []);

    if (loading) {
        return (
            <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-slate-600">
                正在加载治理信息...
            </div>
        );
    }

    if (error) {
        return (
            <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8">
                <h1 className="text-2xl font-black text-slate-900">治理矩阵</h1>
                <p className="text-sm text-amber-800">{error}</p>
                <Button onClick={loadGovernance}>重试加载</Button>
            </GlassCard>
        );
    }

    return (
        <div className="space-y-8 pb-20">
            <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">治理矩阵</h1>
                    <p className="mt-2 max-w-3xl text-sm text-slate-600">
                        查看 admin route 权限矩阵、support redaction boundary 和系统设置 backlog。
                        这里是治理态势面，不是设置编辑面。
                    </p>
                </div>
                <Button variant="outline" onClick={loadGovernance}>刷新治理信息</Button>
            </header>

            <div className="grid gap-4 lg:grid-cols-3">
                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Route families</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{permissions?.total ?? 0}</div>
                    <p className="mt-2 text-sm text-slate-600">现有 admin 路由家族的权限边界。</p>
                </GlassCard>
                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Fix first</div>
                    <div className="mt-2 text-sm font-bold text-slate-900">{formatList(permissions?.fix_first_route_families)}</div>
                    <p className="mt-2 text-sm text-slate-600">当前没有 fix-first 家族，说明 RBAC 已进入 watch / baseline 结构化治理。</p>
                </GlassCard>
                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Settings backlog</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{settingsBacklog?.total ?? 0}</div>
                    <p className="mt-2 text-sm text-slate-600">非模型设置仍需后端配置存储、审计和回滚能力。</p>
                </GlassCard>
            </div>

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-xl font-black text-slate-900">权限矩阵</h2>
                <div className="grid gap-3">
                    {(permissions?.items || []).map((item) => (
                        <div key={item.route_family} className="rounded-2xl border border-slate-100 bg-white/80 p-4">
                            <div className="flex flex-wrap items-center gap-2">
                                <div className="font-bold text-slate-900">{item.route_family}</div>
                                <Badge variant={item.priority === "fix-first" ? "red" : item.priority === "watch" ? "orange" : "green"}>
                                    {item.priority}
                                </Badge>
                                <Badge variant="gray">{item.risk}</Badge>
                            </div>
                            <div className="mt-2 text-sm text-slate-600">Auth: {item.auth_surface}</div>
                            <div className="mt-1 text-sm text-slate-600">Deny: {item.non_admin_deny_path}</div>
                            <div className="mt-2 text-xs text-slate-500">Routes: {formatList(item.routes)}</div>
                            <div className="mt-1 text-xs text-slate-500">Allowed roles: {formatList(item.allowed_roles)}</div>
                            <div className="mt-1 text-xs text-slate-500">Evidence: {formatList(item.current_evidence)}</div>
                            <p className="mt-2 text-sm text-slate-700">{item.rationale}</p>
                        </div>
                    ))}
                </div>
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-xl font-black text-slate-900">Support / redaction boundary</h2>
                <p className="text-sm text-slate-600">{permissions?.support_log_redaction.guidance}</p>
                <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4">
                        <div className="text-sm font-bold text-slate-900">Visible fields</div>
                        <div className="mt-2 text-sm text-slate-600">{formatList(permissions?.support_log_redaction.visible_fields)}</div>
                    </div>
                    <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4">
                        <div className="text-sm font-bold text-slate-900">Diagnostics allowlist</div>
                        <div className="mt-2 text-sm text-slate-600">{formatList(permissions?.support_log_redaction.diagnostic_allowlist)}</div>
                    </div>
                    <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4 md:col-span-2">
                        <div className="text-sm font-bold text-slate-900">Backend-only fields</div>
                        <div className="mt-2 text-sm text-slate-600">{formatList(permissions?.support_log_redaction.backend_only_fields)}</div>
                    </div>
                </div>
                <p className="text-sm text-slate-600">{permissions?.support_log_redaction.quality_event_prerequisite}</p>
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-xl font-black text-slate-900">系统设置 backlog</h2>
                <p className="text-sm text-slate-600">{settingsBacklog?.policy}</p>
                <div className="grid gap-3">
                    {(settingsBacklog?.items || []).map((item) => (
                        <div key={item.surface} className="rounded-2xl border border-slate-100 bg-white/80 p-4">
                            <div className="flex flex-wrap items-center gap-2">
                                <div className="font-bold text-slate-900">{item.label}</div>
                                <Badge variant={item.status === "persisted" ? "green" : "orange"}>{item.status}</Badge>
                            </div>
                            <div className="mt-1 text-sm text-slate-600">Surface: {item.surface}</div>
                            <div className="mt-2 text-xs text-slate-500">Missing: {formatList(item.missing_capabilities)}</div>
                            <div className="mt-1 text-xs text-slate-500">Fallback: {item.fallback_policy}</div>
                        </div>
                    ))}
                </div>
            </GlassCard>
        </div>
    );
}
