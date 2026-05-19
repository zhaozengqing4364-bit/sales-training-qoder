"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { GlassCard } from "@/components/ui/glass-card";
import { JsonEditorWithValidation } from "@/components/ui/json-editor-with-validation";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    ScoringRulesetAuditEntry,
    ScoringRulesetRecord,
    ScoringRulesetScenarioType,
} from "@/lib/api/types";
import { debug } from "@/lib/debug";

const SCENARIO_OPTIONS: Array<{ value: ScoringRulesetScenarioType; label: string }> = [
    { value: "sales", label: "销售训练" },
    { value: "presentation", label: "PPT 演练" },
];

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

function formatJson(value: Record<string, unknown>) {
    return JSON.stringify(value, null, 2);
}

function parseJsonDraft(value: string): { ok: true; value: Record<string, unknown> } | { ok: false; message: string } {
    try {
        const parsed = JSON.parse(value);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            return { ok: false, message: "评分定义必须是 JSON 对象。" };
        }
        return { ok: true, value: parsed as Record<string, unknown> };
    } catch (error) {
        return {
            ok: false,
            message: error instanceof Error ? error.message : "JSON 格式无效。",
        };
    }
}

function rulesetOptionLabel(item: ScoringRulesetRecord) {
    return `${item.status}${item.is_active ? " active" : ""} · ${item.version} · ${item.display_name}`;
}

function isEditableDraft(item: ScoringRulesetRecord | null) {
    return Boolean(item?.ruleset_id && item.status === "draft");
}

type ConfirmAction =
    | { type: "publish"; ruleset: ScoringRulesetRecord; reason: string }
    | { type: "rollback"; ruleset: ScoringRulesetRecord; reason: string }
    | null;

export default function AdminScoringRulesetsPage() {
    const [scenarioType, setScenarioType] = useState<ScoringRulesetScenarioType>("sales");
    const [items, setItems] = useState<ScoringRulesetRecord[]>([]);
    const [auditLogs, setAuditLogs] = useState<ScoringRulesetAuditEntry[]>([]);
    const [active, setActive] = useState<ScoringRulesetRecord | null>(null);
    const [selectedRulesetId, setSelectedRulesetId] = useState<string>("");
    const [version, setVersion] = useState("");
    const [displayName, setDisplayName] = useState("");
    const [description, setDescription] = useState("");
    const [definitionJson, setDefinitionJson] = useState("");
    const [reason, setReason] = useState("");
    const [dryRunSessionId, setDryRunSessionId] = useState("");
    const [dryRunDelta, setDryRunDelta] = useState<Record<string, unknown> | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [busyAction, setBusyAction] = useState<"load" | "save" | "publish" | "rollback" | "dry-run" | null>(null);
    const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);

    const selectedRuleset = useMemo(
        () => items.find((item) => item.ruleset_id === selectedRulesetId) ?? null,
        [items, selectedRulesetId],
    );
    const parsedDefinition = useMemo(() => parseJsonDraft(definitionJson), [definitionJson]);
    const historyItems = useMemo(
        () => items.filter((item) => item.status === "published" || item.status === "archived"),
        [items],
    );

    const applyEditorValue = useCallback((ruleset: ScoringRulesetRecord | null) => {
        setSelectedRulesetId(ruleset?.ruleset_id ?? "");
        setVersion(ruleset?.version ?? "");
        setDisplayName(ruleset?.display_name ?? "");
        setDescription(ruleset?.description ?? "");
        setDefinitionJson(formatJson(ruleset?.definition ?? {}));
        setDryRunDelta(null);
    }, []);

    const loadRulesets = useCallback(async (nextScenario: ScoringRulesetScenarioType = scenarioType) => {
        setLoading(true);
        setBusyAction("load");
        setError(null);
        try {
            const [listResponse, activeResponse] = await Promise.all([
                api.admin.listScoringRulesets(nextScenario),
                api.admin.getActiveScoringRuleset(nextScenario),
            ]);
            const auditResponse = await api.admin.listScoringRulesetAuditLogs();
            setItems(listResponse.items);
            setAuditLogs(auditResponse.items);
            setActive(activeResponse);
            const nextSelected = listResponse.items.find((item) => item.status === "draft")
                ?? listResponse.items.find((item) => item.is_active)
                ?? activeResponse;
            applyEditorValue(nextSelected);
            setNotice(null);
            setActionError(null);
        } catch (err) {
            setError(`评分规则集加载失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminScoringRulesetsPage] failed to load rulesets", { scenarioType: nextScenario, error: err });
        } finally {
            setBusyAction(null);
            setLoading(false);
        }
    }, [applyEditorValue, scenarioType]);

    useEffect(() => {
        void Promise.resolve().then(() => loadRulesets(scenarioType));
    }, [loadRulesets, scenarioType]);

    const requireReason = () => {
        const trimmed = reason.trim();
        if (!trimmed) {
            setActionError("发布、回滚或更新前必须填写原因，原因会进入后端审计日志。");
            return null;
        }
        return trimmed;
    };

    const handleCreateOrUpdateDraft = async () => {
        setNotice(null);
        setActionError(null);
        setDryRunDelta(null);
        const parsed = parseJsonDraft(definitionJson);
        if (!parsed.ok) {
            setActionError(`JSON 校验未通过：${parsed.message}`);
            return;
        }
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        if (!version.trim() || !displayName.trim()) {
            setActionError("版本号和展示名称必填。");
            return;
        }

        setBusyAction("save");
        try {
            const editableDraftId = isEditableDraft(selectedRuleset) ? selectedRuleset?.ruleset_id : null;
            const saved = editableDraftId
                ? await api.admin.updateScoringRuleset(editableDraftId, {
                    display_name: displayName.trim(),
                    description: description.trim() || null,
                    definition: parsed.value,
                })
                : await api.admin.createScoringRuleset({
                    scenario_type: scenarioType,
                    version: version.trim(),
                    display_name: displayName.trim(),
                    description: description.trim() || null,
                    definition: parsed.value,
                });
            await loadRulesets(scenarioType);
            applyEditorValue(saved);
            setNotice(editableDraftId ? `草稿已更新：${saved.version}。` : `草稿已创建：${saved.version}。`);
        } catch (err) {
            setActionError(`保存评分规则草稿失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const handlePublish = async () => {
        setNotice(null);
        setActionError(null);
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        if (!selectedRuleset?.ruleset_id) {
            setActionError("需要选择可发布的评分规则集。");
            return;
        }

        setBusyAction("publish");
        try {
            const published = await api.admin.publishScoringRuleset(selectedRuleset.ruleset_id, trimmedReason);
            await loadRulesets(scenarioType);
            applyEditorValue(published);
            setNotice(`发布完成：${published.version} 已成为 ${published.scenario_type} active ruleset。`);
        } catch (err) {
            setActionError(`发布失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const requestPublish = () => {
        setNotice(null);
        setActionError(null);
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        if (!selectedRuleset?.ruleset_id) {
            setActionError("需要选择可发布的评分规则集。");
            return;
        }
        setConfirmAction({ type: "publish", ruleset: selectedRuleset, reason: trimmedReason });
    };

    const handleRollback = async (target: ScoringRulesetRecord) => {
        setNotice(null);
        setActionError(null);
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        if (!target.ruleset_id) {
            setActionError("默认兜底规则集不能作为回滚目标。");
            return;
        }

        setBusyAction("rollback");
        try {
            const rolledBack = await api.admin.rollbackScoringRuleset(target.ruleset_id, trimmedReason);
            await loadRulesets(scenarioType);
            applyEditorValue(rolledBack);
            setNotice(`回滚完成：${rolledBack.version} 已恢复为 active。`);
        } catch (err) {
            setActionError(`回滚失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const requestRollback = (target: ScoringRulesetRecord) => {
        setNotice(null);
        setActionError(null);
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        if (!target.ruleset_id) {
            setActionError("默认兜底规则集不能作为回滚目标。");
            return;
        }
        setConfirmAction({ type: "rollback", ruleset: target, reason: trimmedReason });
    };

    const handleConfirmAction = () => {
        const action = confirmAction;
        setConfirmAction(null);
        if (!action) return;
        if (action.type === "publish") {
            void handlePublish();
            return;
        }
        void handleRollback(action.ruleset);
    };

    const handleDryRun = async () => {
        setNotice(null);
        setActionError(null);
        setDryRunDelta(null);
        const parsed = parseJsonDraft(definitionJson);
        if (!parsed.ok) {
            setActionError(`JSON 校验未通过：${parsed.message}`);
            return;
        }
        const sessionId = dryRunSessionId.trim();
        if (!sessionId) {
            setActionError("试运行需要填写已完成训练 session_id。");
            return;
        }

        setBusyAction("dry-run");
        try {
            const result = await api.admin.dryRunScoringRuleset({
                session_id: sessionId,
                candidate_ruleset_id: selectedRuleset?.ruleset_id || undefined,
                candidate_definition: selectedRuleset?.ruleset_id ? undefined : parsed.value,
            });
            setDryRunDelta(result.delta);
            setNotice(
              result.mutates_history
                ? "试运行完成；请查看差异。"
                : "试运行完成；不会修改历史记录。",
            );
        } catch (err) {
            setActionError(`试运行失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    if (loading) {
        return (
            <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-slate-600">
                正在加载评分规则集...
            </div>
        );
    }

    if (error) {
        return (
            <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8">
                <h1 className="text-2xl font-black text-slate-900">评分规则集</h1>
                <p className="text-sm text-amber-800">{error}</p>
                <p className="text-sm text-slate-600">
                    当前不会保存本地草稿；请等待评分规则集 API 恢复后再试运行、发布或回滚。
                </p>
                <Button onClick={() => loadRulesets(scenarioType)}>重试加载</Button>
            </GlassCard>
        );
    }

    return (
        <div className="space-y-8 pb-20">
            <ConfirmDialog
                open={!!confirmAction}
                onOpenChange={(open) => {
                    if (!open) setConfirmAction(null);
                }}
                title={confirmAction?.type === "rollback" ? "确认回滚评分规则" : "确认发布评分规则"}
                description={confirmAction
                    ? confirmAction.type === "rollback"
                        ? `将 ${confirmAction.ruleset.version} 恢复为当前 active ruleset。原因：${confirmAction.reason}`
                        : `将 ${confirmAction.ruleset.version} 发布为 ${confirmAction.ruleset.scenario_type} 当前 active ruleset。原因：${confirmAction.reason}`
                    : "确认执行该评分规则操作。"}
                confirmText={confirmAction?.type === "rollback" ? "确认回滚" : "确认发布"}
                variant={confirmAction?.type === "rollback" ? "warning" : "danger"}
                onConfirm={handleConfirmAction}
                isLoading={busyAction === "publish" || busyAction === "rollback"}
            />

            <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                    <div className="flex flex-wrap items-center gap-2">
                        <h1 className="text-3xl font-black tracking-tight text-slate-900">评分规则集</h1>
                        <Badge variant={active?.source === "default" ? "orange" : "green"}>
                            {active?.source === "default" ? "default fallback" : "admin active"}
                        </Badge>
                    </div>
                    <p className="mt-2 max-w-3xl text-sm text-slate-600">
                        管理训练评分 ruleset 的草稿、试运行、发布和回滚。评分权重、证据门槛和不可评估原因都保存在后端 ruleset definition 中。
                    </p>
                    <p className="mt-2 text-xs text-slate-500">
                        API: /api/v1/evaluation/admin/scoring-rulesets · 权限：admin only · 发布/回滚写入 SystemLog 审计。
                    </p>
                </div>
                <Button variant="outline" onClick={() => loadRulesets(scenarioType)}>刷新规则集</Button>
            </header>

            <div className="grid gap-4 lg:grid-cols-3">
                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Scenario</div>
                    <select
                        aria-label="选择评分场景"
                        value={scenarioType}
                        onChange={(event) => {
                            const next = event.target.value as ScoringRulesetScenarioType;
                            setScenarioType(next);
                            void loadRulesets(next);
                        }}
                        className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700"
                    >
                        {SCENARIO_OPTIONS.map((item) => (
                            <option key={item.value} value={item.value}>{item.label}</option>
                        ))}
                    </select>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Active version</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{active?.version || "未返回"}</div>
                    <p className="mt-2 text-sm text-slate-600">{active?.display_name || "未返回 active ruleset"}</p>
                    <p className="mt-1 text-sm text-slate-600">来源：{active?.source || "unknown"}</p>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Managed rulesets</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{items.length}</div>
                    <p className="mt-2 text-sm text-slate-600">没有数据库规则集时，运行时使用后端安全默认 ruleset。</p>
                </GlassCard>
            </div>

            <GlassCard className="space-y-5 p-6">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <h2 className="text-xl font-black text-slate-900">草稿与试运行</h2>
                        <p className="mt-1 text-sm text-slate-600">
                            选中：{selectedRuleset ? rulesetOptionLabel(selectedRuleset) : "默认兜底定义"}。
                            已 active 的 published ruleset 不可直接更新，请另建草稿。
                        </p>
                    </div>
                    <select
                        aria-label="选择评分规则集"
                        value={selectedRuleset?.ruleset_id ?? ""}
                        onChange={(event) => {
                            const next = items.find((item) => item.ruleset_id === event.target.value) ?? active;
                            applyEditorValue(next);
                            setNotice(null);
                            setActionError(null);
                        }}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700"
                    >
                        {items.map((item) => (
                            <option key={item.ruleset_id || `${item.source}-${item.version}`} value={item.ruleset_id ?? ""}>
                                {rulesetOptionLabel(item)}
                            </option>
                        ))}
                        {items.length === 0 && <option value="">默认兜底定义</option>}
                    </select>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                    <input
                        aria-label="评分规则版本"
                        value={version}
                        onChange={(event) => setVersion(event.target.value)}
                        placeholder="版本号，例如 sales-v3"
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                    />
                    <input
                        aria-label="评分规则展示名称"
                        value={displayName}
                        onChange={(event) => setDisplayName(event.target.value)}
                        placeholder="展示名称"
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                    />
                    <input
                        aria-label="评分规则描述"
                        value={description}
                        onChange={(event) => setDescription(event.target.value)}
                        placeholder="描述（可选）"
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                    />
                </div>

                <JsonEditorWithValidation
                    label="评分规则 JSON 定义"
                    value={definitionJson}
                    onChange={(value) => {
                        setDefinitionJson(value);
                        setDryRunDelta(null);
                    }}
                    rows={22}
                    isValid={parsedDefinition.ok}
                    validationMessage={parsedDefinition.ok
                        ? "JSON 对象格式有效；后端规则校验会在保存、发布和试运行时再次校验。"
                        : `JSON 格式错误：${parsedDefinition.message}`}
                    helpText="必须是 JSON 对象，不支持数组；保存、发布和试运行前会再次校验。"
                />

                <div className="grid gap-3 xl:grid-cols-[1fr_1fr_auto_auto_auto] xl:items-center">
                    <input
                        value={reason}
                        onChange={(event) => setReason(event.target.value)}
                        placeholder="发布/回滚/更新原因（必填，将进入审计日志）"
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                    />
                    <input
                        value={dryRunSessionId}
                        onChange={(event) => setDryRunSessionId(event.target.value)}
                        placeholder="试运行 session_id"
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                    />
                    <Button variant="outline" onClick={handleDryRun} disabled={!parsedDefinition.ok || busyAction !== null}>
                        {busyAction === "dry-run" ? "试运行中..." : "试运行"}
                    </Button>
                    <Button variant="outline" onClick={handleCreateOrUpdateDraft} disabled={!parsedDefinition.ok || busyAction !== null}>
                        {busyAction === "save" ? "保存中..." : isEditableDraft(selectedRuleset) ? "更新草稿" : "创建草稿"}
                    </Button>
                    <Button onClick={requestPublish} disabled={!selectedRuleset?.ruleset_id || busyAction !== null}>
                        {busyAction === "publish" ? "发布中..." : "发布选中规则"}
                    </Button>
                </div>

                {notice && (
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>
                )}
                {actionError && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{actionError}</div>
                )}
                {dryRunDelta && (
                    <div className="rounded-2xl border border-blue-100 bg-blue-50/80 p-4">
                        <h3 className="text-sm font-black text-slate-900">试运行差异</h3>
                        <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-blue-950">
                            {JSON.stringify(dryRunDelta, null, 2)}
                        </pre>
                    </div>
                )}
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-xl font-black text-slate-900">发布历史与回滚</h2>
                <div className="grid gap-3">
                    {historyItems.map((item) => (
                        <div key={item.ruleset_id || `${item.status}-${item.version}`} className="flex flex-col gap-3 rounded-2xl border border-slate-100 bg-white/80 p-4 md:flex-row md:items-center md:justify-between">
                            <div>
                                <div className="font-bold text-slate-900">
                                    {item.version} · {item.status}{item.is_active ? " · active" : ""}
                                </div>
                                <div className="mt-1 text-sm text-slate-600">
                                    {item.display_name} · 发布：{formatDateTime(item.published_at)}
                                </div>
                                <div className="mt-1 text-xs text-slate-500">ruleset: {item.ruleset_id || "default"}</div>
                            </div>
                            <Button
                                variant="outline"
                                onClick={() => {
                                    requestRollback(item);
                                }}
                                disabled={!item.ruleset_id || item.is_active || item.status !== "published" || busyAction !== null}
                            >
                                回滚到此版本
                            </Button>
                        </div>
                    ))}
                    {historyItems.length === 0 && (
                        <p className="text-sm text-slate-500">暂无已发布历史；当前使用后端默认 ruleset 兜底。</p>
                    )}
                </div>
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <div>
                    <h2 className="text-xl font-black text-slate-900">审计日志</h2>
                    <p className="mt-1 text-sm text-slate-600">
                        显示评分规则集发布和回滚操作的 SystemLog 记录，包含操作人、原因、trace id 和版本快照。
                    </p>
                </div>
                <div className="grid gap-3">
                    {auditLogs.map((item) => (
                        <div key={item.id} className="rounded-2xl border border-slate-100 bg-white/80 p-4">
                            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                <div className="font-bold text-slate-900">{item.action}</div>
                                <div className="text-xs text-slate-500">{formatDateTime(item.created_at)}</div>
                            </div>
                            <div className="mt-2 grid gap-1 text-xs text-slate-600 md:grid-cols-2">
                                <div>actor: {item.actor_id || "未记录"} · {item.actor_role || "unknown"}</div>
                                <div>trace: {item.trace_id || "未记录"}</div>
                                <div className="md:col-span-2">reason: {item.reason || "未记录"}</div>
                            </div>
                            <pre className="mt-3 max-h-40 overflow-auto rounded-xl bg-slate-950 p-3 text-xs text-slate-100">
                                {JSON.stringify({ before: item.before, after: item.after }, null, 2)}
                            </pre>
                        </div>
                    ))}
                    {auditLogs.length === 0 && (
                        <p className="text-sm text-slate-500">暂无评分规则集发布或回滚审计记录。</p>
                    )}
                </div>
            </GlassCard>
        </div>
    );
}
