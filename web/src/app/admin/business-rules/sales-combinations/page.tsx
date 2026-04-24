"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    SalesCombinationPreviewResponse,
    SalesCombinationRuleSet,
    SalesCombinationRuleSetListResponse,
    SalesCombinationRuleValidationIssue,
} from "@/lib/api/types";
import { debug } from "@/lib/debug";

const DEFAULT_PERMISSIONS = {
    can_view: true,
    can_mutate: true,
    can_publish: true,
    reason: null,
};

function formatDateTime(value?: string | null) {
    if (!value) return "未记录";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "未记录";
    return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    });
}

function validateSalesCombinationRuleset(ruleset: SalesCombinationRuleSet | null): SalesCombinationRuleValidationIssue[] {
    if (!ruleset) {
        return [{ path: "ruleset", message: "尚未选择可验证的规则集。" }];
    }

    const issues: SalesCombinationRuleValidationIssue[] = [];
    const idSet = new Set<string>();
    const pairSet = new Set<string>();

    if (!ruleset.rule_set_id.trim()) {
        issues.push({ path: "rule_set_id", message: "规则集 ID 必填。" });
    }
    if (!ruleset.version.trim()) {
        issues.push({ path: "version", message: "版本号必填。" });
    }
    if (ruleset.fallback_policy !== "client_default_v1" && ruleset.fallback_policy !== "hide_all") {
        issues.push({ path: "fallback_policy", message: "兜底策略必须是 client_default_v1 或 hide_all。" });
    }
    if (!Array.isArray(ruleset.combinations) || ruleset.combinations.length === 0) {
        issues.push({ path: "combinations", message: "至少需要 1 条组合配置。" });
        return issues;
    }

    let enabledCount = 0;

    ruleset.combinations.forEach((rule, index) => {
        const rowPath = `combinations[${index}]`;
        const id = String(rule.id || "").trim();
        const capability = String(rule.capability || "").trim();
        const role = String(rule.role || "").trim();
        const pairKey = `${capability}::${role}`.toLowerCase();

        if (!id) {
            issues.push({ path: `${rowPath}.id`, message: "组合 ID 必填。" });
        } else if (idSet.has(id)) {
            issues.push({ path: `${rowPath}.id`, message: `组合 ID 重复：${id}` });
        }
        if (!capability) {
            issues.push({ path: `${rowPath}.capability`, message: "能力项必填。" });
        }
        if (!role) {
            issues.push({ path: `${rowPath}.role`, message: "客户角色必填。" });
        }
        if (capability && role && pairSet.has(pairKey)) {
            issues.push({ path: `${rowPath}.role`, message: `能力 × 角色重复：${capability} × ${role}` });
        }
        if (!Number.isFinite(Number(rule.priority)) || Number(rule.priority) < 1) {
            issues.push({ path: `${rowPath}.priority`, message: "优先级必须是正数。" });
        }
        if (rule.enabled) {
            enabledCount += 1;
        }

        idSet.add(id);
        pairSet.add(pairKey);
    });

    if (enabledCount === 0 && ruleset.fallback_policy !== "hide_all") {
        issues.push({ path: "combinations", message: "没有启用组合时必须显式选择 hide_all 兜底策略。" });
    }

    return issues;
}

function selectDefaultRuleset(data: SalesCombinationRuleSetListResponse | null) {
    return data?.drafts[0] ?? data?.active ?? null;
}

export default function AdminSalesCombinationsPage() {
    const [data, setData] = useState<SalesCombinationRuleSetListResponse | null>(null);
    const [selectedRulesetId, setSelectedRulesetId] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [reason, setReason] = useState("");
    const [preview, setPreview] = useState<SalesCombinationPreviewResponse | null>(null);
    const [actionNotice, setActionNotice] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [isPreviewing, setIsPreviewing] = useState(false);
    const [isPublishing, setIsPublishing] = useState(false);
    const [isRollingBack, setIsRollingBack] = useState(false);

    const permissions = data?.permissions ?? DEFAULT_PERMISSIONS;
    const selectedRuleset = useMemo(() => {
        if (!data) return null;
        const allRuleSets = [
            ...(data.drafts || []),
            ...(data.active ? [data.active] : []),
            ...(data.history || []),
        ];
        return allRuleSets.find((item) => item.rule_set_id === selectedRulesetId)
            ?? selectDefaultRuleset(data);
    }, [data, selectedRulesetId]);
    const validationIssues = useMemo(
        () => validateSalesCombinationRuleset(selectedRuleset),
        [selectedRuleset],
    );
    const activeVersion = data?.active?.version ?? "未发布";

    const loadRuleSets = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.admin.getSalesCombinationRuleSets();
            setData(response);
            setSelectedRulesetId((current) => current ?? selectDefaultRuleset(response)?.rule_set_id ?? null);
        } catch (err) {
            setError(`销售训练组合规则加载失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminSalesCombinations] failed to load rule sets", { error: err });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadRuleSets();
    }, [loadRuleSets]);

    const handlePreview = async () => {
        if (!selectedRuleset) return;
        setActionNotice(null);
        setActionError(null);
        setPreview(null);

        if (validationIssues.length > 0) {
            setActionError("本地校验未通过，预览不会修改 active 版本。");
            return;
        }

        setIsPreviewing(true);
        try {
            const result = await api.admin.previewSalesCombinationRuleSet(selectedRuleset);
            setPreview(result);
            setActionNotice(`预览完成；当前 active 仍为 ${activeVersion}，不会被预览修改。`);
        } catch (err) {
            setActionError(`预览失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminSalesCombinations] preview failed", { error: err });
        } finally {
            setIsPreviewing(false);
        }
    };

    const handlePublish = async () => {
        if (!selectedRuleset) return;
        setActionNotice(null);
        setActionError(null);

        if (!permissions.can_publish) {
            setActionError(permissions.reason || "当前账号没有发布销售训练组合规则的权限。");
            return;
        }
        if (validationIssues.length > 0) {
            setActionError("本地校验未通过，不能发布。");
            return;
        }
        const trimmedReason = reason.trim();
        if (!trimmedReason) {
            setActionError("发布或回滚前必须填写原因。");
            return;
        }

        setIsPublishing(true);
        try {
            const result = await api.admin.publishSalesCombinationRuleSet(selectedRuleset.rule_set_id, trimmedReason);
            setData((current) => current
                ? {
                    ...current,
                    active: result.ruleset,
                    drafts: current.drafts.filter((draft) => draft.rule_set_id !== result.ruleset.rule_set_id),
                    history: [result.ruleset, ...current.history.filter((item) => item.rule_set_id !== result.ruleset.rule_set_id)],
                    audit_log: [result.audit, ...(current.audit_log || [])],
                }
                : current);
            setSelectedRulesetId(result.ruleset.rule_set_id);
            setActionNotice(`发布完成：${result.audit.actor || "unknown"} ${result.audit.before_version || "无"} → ${result.audit.after_version || result.ruleset.version}，原因：${result.audit.reason || trimmedReason}，trace：${result.audit.trace_id || "未返回"}`);
        } catch (err) {
            setActionError(`发布失败：${getApiErrorMessage(err)}`);
        } finally {
            setIsPublishing(false);
        }
    };

    const handleRollback = async (target: SalesCombinationRuleSet) => {
        setActionNotice(null);
        setActionError(null);

        if (!permissions.can_publish) {
            setActionError(permissions.reason || "当前账号没有回滚销售训练组合规则的权限。");
            return;
        }
        const trimmedReason = reason.trim();
        if (!trimmedReason) {
            setActionError("发布或回滚前必须填写原因。");
            return;
        }

        setIsRollingBack(true);
        try {
            const result = await api.admin.rollbackSalesCombinationRuleSet(target.rule_set_id, trimmedReason);
            setData((current) => current
                ? {
                    ...current,
                    active: result.ruleset,
                    history: [result.ruleset, ...current.history.filter((item) => item.rule_set_id !== result.ruleset.rule_set_id)],
                    audit_log: [result.audit, ...(current.audit_log || [])],
                }
                : current);
            setSelectedRulesetId(result.ruleset.rule_set_id);
            setActionNotice(`回滚完成：${result.audit.actor || "unknown"} ${result.audit.before_version || "无"} → ${result.audit.after_version || result.ruleset.version}，原因：${result.audit.reason || trimmedReason}，trace：${result.audit.trace_id || "未返回"}`);
        } catch (err) {
            setActionError(`回滚失败：${getApiErrorMessage(err)}`);
        } finally {
            setIsRollingBack(false);
        }
    };

    if (loading) {
        return (
            <div className="rounded-3xl border border-slate-100 bg-white/80 p-8 text-slate-600">
                正在加载销售训练组合规则...
            </div>
        );
    }

    if (error) {
        return (
            <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8">
                <h1 className="text-2xl font-black text-slate-900">销售训练组合规则</h1>
                <p className="text-sm text-amber-800">{error}</p>
                <p className="text-sm text-slate-600">
                    当前不会在管理端保存任何本地草稿；请等待业务规则 API 恢复后再预览、发布或回滚。
                </p>
                <Button onClick={loadRuleSets}>重试加载</Button>
            </GlassCard>
        );
    }

    return (
        <div className="space-y-8 pb-20">
            <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                    <div className="flex flex-wrap items-center gap-2">
                        <h1 className="text-3xl font-black tracking-tight text-slate-900">销售训练组合规则</h1>
                        <Badge variant={permissions.can_publish ? "green" : permissions.can_mutate ? "orange" : "secondary"}>
                            {permissions.can_publish ? "可发布/回滚" : permissions.can_mutate ? "仅草稿/预览" : "只读"}
                        </Badge>
                    </div>
                    <p className="mt-2 max-w-3xl text-sm text-slate-600">
                        管理核心销售训练组合的草稿、预览、发布、回滚与审计。预览只读，不会改变当前 active 版本。
                    </p>
                    {!permissions.can_mutate && (
                        <p className="mt-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
                            {permissions.reason || "当前账号只能查看业务规则，不能修改。"}
                        </p>
                    )}
                </div>
                <Button variant="outline" onClick={loadRuleSets}>刷新规则</Button>
            </header>

            <div className="grid gap-4 lg:grid-cols-3">
                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Active version</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{activeVersion}</div>
                    <p className="mt-2 text-sm text-slate-600">
                        发布时间：{formatDateTime(data?.active?.audit_summary?.published_at ?? data?.active?.effective_at)}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">
                        发布人：{data?.active?.audit_summary?.published_by || "未记录"}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">
                        原因：{data?.active?.audit_summary?.reason || "未记录"}
                    </p>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Drafts</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{data?.drafts.length ?? 0}</div>
                    <p className="mt-2 text-sm text-slate-600">当前可选择草稿并进行本地校验和后台预览。</p>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">History</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{data?.history.length ?? 0}</div>
                    <p className="mt-2 text-sm text-slate-600">回滚必须选择历史发布版本并填写原因。</p>
                </GlassCard>
            </div>

            <GlassCard className="space-y-5 p-6">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <h2 className="text-xl font-black text-slate-900">规则集预览与发布</h2>
                        <p className="mt-1 text-sm text-slate-600">
                            选中版本：{selectedRuleset?.version || "未选择"} · 兜底：{selectedRuleset?.fallback_policy || "未选择"}
                        </p>
                    </div>
                    <select
                        aria-label="选择销售训练组合规则集"
                        value={selectedRuleset?.rule_set_id ?? ""}
                        onChange={(event) => {
                            setSelectedRulesetId(event.target.value);
                            setPreview(null);
                            setActionNotice(null);
                            setActionError(null);
                        }}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700"
                    >
                        {[...(data?.drafts || []), ...(data?.active ? [data.active] : []), ...(data?.history || [])].map((ruleset) => (
                            <option key={`${ruleset.status}-${ruleset.rule_set_id}`} value={ruleset.rule_set_id}>
                                {ruleset.status} · {ruleset.version}
                            </option>
                        ))}
                    </select>
                </div>

                {validationIssues.length > 0 ? (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                        <div className="text-sm font-bold text-amber-900">本地校验未通过</div>
                        <ul className="mt-2 space-y-1 text-sm text-amber-800">
                            {validationIssues.map((issue) => (
                                <li key={`${issue.path}-${issue.message}`}>{issue.path}：{issue.message}</li>
                            ))}
                        </ul>
                    </div>
                ) : (
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-medium text-emerald-800">
                        本地校验通过；仍需后台 validate/preview/publish API 确认后才能生效。
                    </div>
                )}

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[760px] text-left text-sm">
                        <thead className="text-xs uppercase tracking-widest text-slate-500">
                            <tr>
                                <th className="py-2 pr-3">优先级</th>
                                <th className="py-2 pr-3">组合 ID</th>
                                <th className="py-2 pr-3">能力</th>
                                <th className="py-2 pr-3">客户角色</th>
                                <th className="py-2 pr-3">启用</th>
                                <th className="py-2 pr-3">匹配提示</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(selectedRuleset?.combinations || []).map((rule) => (
                                <tr key={rule.id} className="border-t border-slate-100">
                                    <td className="py-3 pr-3 font-bold text-slate-900">{rule.priority}</td>
                                    <td className="py-3 pr-3 font-mono text-xs text-slate-600">{rule.id}</td>
                                    <td className="py-3 pr-3 font-semibold text-slate-900">{rule.capability || "未填写"}</td>
                                    <td className="py-3 pr-3 text-slate-700">{rule.role || "未填写"}</td>
                                    <td className="py-3 pr-3">
                                        <Badge variant={rule.enabled ? "green" : "secondary"}>{rule.enabled ? "启用" : "停用"}</Badge>
                                    </td>
                                    <td className="py-3 pr-3 text-xs text-slate-500">
                                        Agent: {(rule.required_agent_match || []).join("、") || "自动"} / Persona: {(rule.required_persona_match || []).join("、") || "自动"}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                <div className="grid gap-3 md:grid-cols-[1fr_auto_auto] md:items-center">
                    <input
                        value={reason}
                        onChange={(event) => setReason(event.target.value)}
                        placeholder="发布/回滚原因（必填，将进入审计记录）"
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                    />
                    <Button
                        variant="outline"
                        onClick={handlePreview}
                        disabled={!permissions.can_view || isPreviewing}
                    >
                        {isPreviewing ? "预览中..." : "预览覆盖率"}
                    </Button>
                    <Button
                        onClick={handlePublish}
                        disabled={!permissions.can_publish || validationIssues.length > 0 || isPublishing}
                    >
                        {isPublishing ? "发布中..." : "发布当前草稿"}
                    </Button>
                </div>

                {actionNotice && (
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{actionNotice}</div>
                )}
                {actionError && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{actionError}</div>
                )}

                {preview && (
                    <div className="rounded-2xl border border-blue-100 bg-blue-50/80 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                            <h3 className="text-sm font-black text-slate-900">预览覆盖率 · {preview.ruleset_version}</h3>
                            <span className="text-xs text-slate-500">预览时间：{formatDateTime(preview.previewed_at)}</span>
                        </div>
                        <div className="mt-3 grid gap-2 text-sm md:grid-cols-5">
                            <div>总数：{preview.coverage.total}</div>
                            <div>匹配：{preview.coverage.matched}</div>
                            <div>缺 Agent：{preview.coverage.missing_agent}</div>
                            <div>缺 Persona：{preview.coverage.missing_persona}</div>
                            <div>停用：{preview.coverage.disabled}</div>
                        </div>
                    </div>
                )}
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-xl font-black text-slate-900">发布历史与审计</h2>
                <div className="grid gap-3">
                    {(data?.history || []).map((item) => (
                        <div key={item.rule_set_id} className="flex flex-col gap-3 rounded-2xl border border-slate-100 bg-white/80 p-4 md:flex-row md:items-center md:justify-between">
                            <div>
                                <div className="font-bold text-slate-900">{item.version}</div>
                                <div className="mt-1 text-sm text-slate-600">
                                    {item.audit_summary?.published_by || "unknown"} · {formatDateTime(item.audit_summary?.published_at ?? item.effective_at)} · {item.audit_summary?.reason || "未记录原因"}
                                </div>
                                <div className="mt-1 text-xs text-slate-500">trace: {item.audit_summary?.trace_id || "未返回"}</div>
                            </div>
                            <Button
                                variant="outline"
                                onClick={() => {
                                    void handleRollback(item);
                                }}
                                disabled={!permissions.can_publish || isRollingBack}
                            >
                                回滚到此版本
                            </Button>
                        </div>
                    ))}
                    {(data?.history || []).length === 0 && (
                        <p className="text-sm text-slate-500">暂无可回滚历史。</p>
                    )}
                </div>

                {(data?.audit_log || []).length > 0 && (
                    <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4">
                        <h3 className="text-sm font-bold text-slate-900">最近审计记录</h3>
                        <ul className="mt-3 space-y-2 text-sm text-slate-600">
                            {(data?.audit_log || []).slice(0, 5).map((entry, index) => (
                                <li key={entry.id || `${entry.action}-${index}`}>
                                    {entry.action} · {entry.actor || "unknown"} · {entry.before_version || "无"} → {entry.after_version || "无"} · {entry.reason || "未记录原因"} · trace {entry.trace_id || "未返回"}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </GlassCard>
        </div>
    );
}
