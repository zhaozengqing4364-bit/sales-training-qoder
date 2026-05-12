"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { api, ApiRequestError, getApiErrorMessage } from "@/lib/api/client";
import type {
    AdminAiGovernanceExplainabilityResponse,
    AdminGovernancePermissionsResponse,
    AdminGovernanceSettingsBacklogResponse,
} from "@/lib/api/types";
import { debug } from "@/lib/debug";

type GovernanceTab = "governance" | "explainability";

function formatList(value: string[] | undefined) {
    return (value || []).join("、") || "无";
}

function formatJsonDisplay(value: Record<string, unknown> | null | undefined): string {
    if (!value || Object.keys(value).length === 0) return "暂无数据";
    try {
        return JSON.stringify(value, null, 2);
    } catch {
        return "暂无数据";
    }
}

export default function AdminGovernancePage() {
    const [permissions, setPermissions] = useState<AdminGovernancePermissionsResponse | null>(null);
    const [settingsBacklog, setSettingsBacklog] = useState<AdminGovernanceSettingsBacklogResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [activeTab, setActiveTab] = useState<GovernanceTab>("governance");

    const [sessionIdInput, setSessionIdInput] = useState("");
    const [explainabilityData, setExplainabilityData] = useState<AdminAiGovernanceExplainabilityResponse | null>(null);
    const [explainabilityLoading, setExplainabilityLoading] = useState(false);
    const [explainabilityError, setExplainabilityError] = useState<string | null>(null);
    const [explainabilityIncomplete, setExplainabilityIncomplete] = useState(false);

    const loadGovernance = useCallback(async () => {
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
    }, []);

    useEffect(() => {
        void Promise.resolve().then(loadGovernance);
    }, [loadGovernance]);

    const loadExplainability = useCallback(async () => {
        const trimmed = sessionIdInput.trim();
        if (!trimmed) {
            setExplainabilityError("请输入会话 ID");
            return;
        }
        setExplainabilityLoading(true);
        setExplainabilityError(null);
        setExplainabilityData(null);
        setExplainabilityIncomplete(false);
        try {
            const data = await api.admin.getAiGovernanceExplainability(trimmed);
            setExplainabilityData(data);
        } catch (err) {
            if (err instanceof ApiRequestError && err.errorCode === "[AI_GOVERNANCE_EXPLAINABILITY_INCOMPLETE]") {
                setExplainabilityError(`${err.message}`);
                setExplainabilityIncomplete(true);
            } else {
                setExplainabilityError(`查询失败：${getApiErrorMessage(err)}`);
            }
            debug.warn("[AdminGovernancePage] failed to load explainability", { error: err });
        } finally {
            setExplainabilityLoading(false);
        }
    }, [sessionIdInput]);

    const renderExplainabilityContent = () => {
        const data = explainabilityData;

        if (!data && !explainabilityError && !explainabilityLoading) {
            return (
                <GlassCard className="p-6 text-center text-sm text-slate-500">
                    输入会话 ID 查看 AI 治理可解释性溯源数据。
                </GlassCard>
            );
        }

        if (explainabilityLoading) {
            return (
                <GlassCard className="p-6 text-center text-sm text-slate-600">
                    <p>正在加载可解释性数据...</p>
                </GlassCard>
            );
        }

        if (explainabilityError) {
            return (
                <GlassCard className={`space-y-4 border p-6 ${explainabilityIncomplete ? "border-amber-200 bg-amber-50/80" : "border-red-200 bg-red-50/80"}`}>
                    <div className="flex items-center gap-2">
                        <Badge variant={explainabilityIncomplete ? "orange" : "red"}>
                            {explainabilityIncomplete ? "可解释性数据不完整" : "查询失败"}
                        </Badge>
                    </div>
                    <p className="text-sm text-slate-700">{explainabilityError}</p>
                    <Button variant="outline" onClick={loadExplainability}>重试</Button>
                </GlassCard>
            );
        }

        if (!data) return null;

        return (
            <div className="space-y-6">
                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">会话信息</div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <div>
                            <div className="text-xs text-slate-500">Session ID</div>
                            <div className="mt-1 text-sm font-mono text-slate-900 break-all">{data.session.session_id}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">场景类型</div>
                            <div className="mt-1 text-sm text-slate-900">{data.session.scenario_type ?? "暂无数据"}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">会话状态</div>
                            <div className="mt-1 text-sm text-slate-900">{data.session.status ?? "暂无数据"}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">报告状态</div>
                            <div className="mt-1 text-sm text-slate-900">{data.session.report_status ?? "暂无数据"}</div>
                        </div>
                    </div>
                </GlassCard>

                <div className="grid gap-4 lg:grid-cols-2">
                    <GlassCard className="p-5">
                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500">模型配置</div>
                        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-slate-700">
                            {formatJsonDisplay(data.model)}
                        </pre>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500">提示词配置</div>
                        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-slate-700">
                            {formatJsonDisplay(data.prompt)}
                        </pre>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500">RAG 配置</div>
                        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-slate-700">
                            {formatJsonDisplay(data.rag)}
                        </pre>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500">知识库来源</div>
                        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-slate-700">
                            {formatJsonDisplay(data.knowledge)}
                        </pre>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500">评分配置</div>
                        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-slate-700">
                            {formatJsonDisplay(data.scoring)}
                        </pre>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500">证据来源</div>
                        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-slate-700">
                            {formatJsonDisplay(data.evidence.input_reference)}
                        </pre>
                        <div className="mt-3">
                            <div className="text-xs text-slate-500">完整性</div>
                            <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap text-xs text-slate-700">
                                {formatJsonDisplay(data.evidence.completeness)}
                            </pre>
                        </div>
                    </GlassCard>
                </div>

                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">评估溯源</div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <div>
                            <div className="text-xs text-slate-500">Run ID</div>
                            <div className="mt-1 text-sm font-mono text-slate-900 break-all">{data.evaluation.run_id}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">状态</div>
                            <div className="mt-1">
                                <Badge variant={data.evaluation.status === "succeeded" ? "green" : data.evaluation.status === "failed" ? "red" : "gray"}>
                                    {data.evaluation.status}
                                </Badge>
                            </div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">开始时间</div>
                            <div className="mt-1 text-sm text-slate-900">{data.evaluation.started_at ?? "暂无数据"}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">结束时间</div>
                            <div className="mt-1 text-sm text-slate-900">{data.evaluation.finished_at ?? "暂无数据"}</div>
                        </div>
                    </div>
                    {data.evaluation.result_summary ? (
                        <div className="mt-3">
                            <div className="text-xs text-slate-500">评估摘要</div>
                            <p className="mt-1 text-sm text-slate-700">{data.evaluation.result_summary}</p>
                        </div>
                    ) : null}
                    <div className="mt-3">
                        <div className="text-xs text-slate-500">评估结果</div>
                        <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap text-xs text-slate-700">
                            {formatJsonDisplay(data.evaluation.result_payload)}
                        </pre>
                    </div>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">报告快照溯源</div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <div>
                            <div className="text-xs text-slate-500">Snapshot ID</div>
                            <div className="mt-1 text-sm font-mono text-slate-900 break-all">{data.report.lineage.snapshot_id}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">评分配置来源</div>
                            <div className="mt-1 text-sm text-slate-900">{data.report.lineage.ruleset_source ?? "暂无数据"}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">评分配置版本</div>
                            <div className="mt-1 text-sm text-slate-900">{data.report.lineage.ruleset_version ?? "暂无数据"}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">评分基准</div>
                            <div className="mt-1 text-sm text-slate-900">{data.report.lineage.score_basis ?? "暂无数据"}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">Config Bundle ID</div>
                            <div className="mt-1 text-sm font-mono text-slate-900 break-all">{data.report.lineage.config_bundle_id ?? "暂无数据"}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">Config Version ID</div>
                            <div className="mt-1 text-sm font-mono text-slate-900 break-all">{data.report.lineage.config_version_id ?? "暂无数据"}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">Bundle Key</div>
                            <div className="mt-1 text-sm text-slate-900">{data.report.lineage.bundle_key ?? "暂无数据"}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">生成时间</div>
                            <div className="mt-1 text-sm text-slate-900">{data.report.lineage.generated_at ?? "暂无数据"}</div>
                        </div>
                    </div>
                    <div className="mt-4">
                        <div className="text-xs text-slate-500">Config Bundle Snapshot</div>
                        <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-xs text-slate-700">
                            {formatJsonDisplay(data.report.lineage.config_bundle_snapshot)}
                        </pre>
                    </div>
                    <div className="mt-4">
                        <div className="text-xs text-slate-500">报告内容</div>
                        <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-xs text-slate-700">
                            {formatJsonDisplay(data.report.payload)}
                        </pre>
                    </div>
                </GlassCard>
            </div>
        );
    };

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
                {activeTab === "governance" ? (
                    <Button variant="outline" onClick={loadGovernance}>刷新治理信息</Button>
                ) : null}
            </header>

            <nav className="flex gap-1 rounded-2xl border border-slate-200 bg-slate-100/80 p-1">
                <button
                    type="button"
                    onClick={() => setActiveTab("governance")}
                    className={`flex-1 rounded-xl px-4 py-2 text-sm font-bold transition-colors ${
                        activeTab === "governance"
                            ? "bg-white text-slate-900 shadow-sm"
                            : "text-slate-500 hover:text-slate-700"
                    }`}
                >
                    治理矩阵
                </button>
                <button
                    type="button"
                    onClick={() => setActiveTab("explainability")}
                    className={`flex-1 rounded-xl px-4 py-2 text-sm font-bold transition-colors ${
                        activeTab === "explainability"
                            ? "bg-white text-slate-900 shadow-sm"
                            : "text-slate-500 hover:text-slate-700"
                    }`}
                >
                    AI 可解释性
                </button>
            </nav>

            {activeTab === "governance" && (
                <>
                    {loading ? (
                        <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-slate-600">
                            正在加载治理信息...
                        </div>
                    ) : error ? (
                        <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8">
                            <p className="text-sm text-amber-800">{error}</p>
                            <Button onClick={loadGovernance}>重试加载</Button>
                        </GlassCard>
                    ) : (
                        <>
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
                        </>
                    )}
                </>
            )}

            {activeTab === "explainability" && (
                <div className="space-y-6">
                    <GlassCard className="p-6">
                        <div className="flex flex-col gap-3 sm:flex-row">
                            <Input
                                placeholder="输入会话 ID（例如：ses_abc123）"
                                value={sessionIdInput}
                                onChange={(e) => setSessionIdInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter") void loadExplainability();
                                }}
                                className="flex-1"
                            />
                            <Button onClick={loadExplainability} disabled={explainabilityLoading}>
                                {explainabilityLoading ? "查询中..." : "查询可解释性"}
                            </Button>
                        </div>
                    </GlassCard>

                    {renderExplainabilityContent()}
                </div>
            )}
        </div>
    );
}
