"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { GlassCard } from "@/components/ui/glass-card";
import { JsonEditorWithValidation } from "@/components/ui/json-editor-with-validation";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    BusinessRuleConfigRecord,
    BusinessRuleHistoryResponse,
    BusinessRulePreviewResponse,
} from "@/lib/api/types";
import { debug } from "@/lib/debug";

interface GovernedBusinessRulePageProps {
    configKey: string;
    title: string;
    description: string;
}

function formatConfigStatus(status: string): string {
    switch (status) {
        case "draft": return "草稿";
        case "published": return "已发布";
        case "archived": return "已归档";
        case "disabled": return "已禁用";
        default: return status;
    }
}

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
            return { ok: false, message: "配置值必须是 JSON 对象。" };
        }
        return { ok: true, value: parsed as Record<string, unknown> };
    } catch (error) {
        return {
            ok: false,
            message: error instanceof Error ? error.message : "JSON 格式无效。",
        };
    }
}

function pickInitialConfig(data: BusinessRuleHistoryResponse | null): BusinessRuleConfigRecord | null {
    if (!data) return null;
    return data.items.find((item) => item.status === "draft")
        ?? data.items.find((item) => item.status === "published" || item.status === "disabled")
        ?? null;
}

function previewSummaryText(preview: BusinessRulePreviewResponse | null) {
    if (!preview) return null;
    const summary = Object.entries(preview.summary || {})
        .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
        .join("；");
    return summary || "后端预览通过，未返回额外摘要。";
}

type ConfirmAction =
    | { type: "publish" }
    | { type: "rollback"; target: BusinessRuleConfigRecord }
    | null;

export function GovernedBusinessRulePage({
    configKey,
    title,
    description,
}: GovernedBusinessRulePageProps) {
    const [data, setData] = useState<BusinessRuleHistoryResponse | null>(null);
    const [selectedConfigId, setSelectedConfigId] = useState<string | null>(null);
    const [draftJson, setDraftJson] = useState("");
    const [reason, setReason] = useState("");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [preview, setPreview] = useState<BusinessRulePreviewResponse | null>(null);
    const [busyAction, setBusyAction] = useState<"save" | "validate" | "preview" | "publish" | "rollback" | null>(null);
    const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);

    const selectedConfig = useMemo(() => {
        if (!data) return null;
        return data.items.find((item) => item.id === selectedConfigId) ?? pickInitialConfig(data);
    }, [data, selectedConfigId]);

    const activeConfig = useMemo(
        () => data?.items.find((item) => item.status === "published" || item.status === "disabled") ?? null,
        [data],
    );
    const draftConfig = useMemo(
        () => data?.items.find((item) => item.status === "draft") ?? null,
        [data],
    );
    const historyItems = useMemo(
        () => (data?.items || []).filter((item) => item.status === "published" || item.status === "archived" || item.status === "disabled"),
        [data],
    );

    const parsedDraft = useMemo(() => parseJsonDraft(draftJson), [draftJson]);
    const previewText = previewSummaryText(preview);

    const loadRule = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.admin.getBusinessRuleHistory(configKey);
            setData(response);
            const initial = pickInitialConfig(response);
            setSelectedConfigId(initial?.id ?? null);
            setDraftJson(formatJson(initial?.value ?? response.definition.default_value));
            setPreview(null);
            setNotice(null);
            setActionError(null);
        } catch (err) {
            setError(`${title}加载失败：${getApiErrorMessage(err)}`);
            debug.warn("[GovernedBusinessRulePage] failed to load business rule", { configKey, error: err });
        } finally {
            setLoading(false);
        }
    }, [configKey, title]);

    useEffect(() => {
        void Promise.resolve().then(loadRule);
    }, [loadRule]);

    const requireReason = () => {
        const trimmed = reason.trim();
        if (!trimmed) {
            setActionError("保存、发布或回滚前必须填写原因，原因会进入审计记录。");
            return null;
        }
        return trimmed;
    };

    const handleSaveDraft = async () => {
        setNotice(null);
        setActionError(null);
        setPreview(null);
        const parsed = parseJsonDraft(draftJson);
        if (!parsed.ok) {
            setActionError(`JSON 校验未通过：${parsed.message}`);
            return;
        }
        const trimmedReason = requireReason();
        if (!trimmedReason) return;

        setBusyAction("save");
        try {
            const saved = await api.admin.saveBusinessRuleDraft(configKey, parsed.value, trimmedReason);
            await loadRule();
            setSelectedConfigId(saved.id);
            setDraftJson(formatJson(saved.value));
            setNotice(`草稿已保存：v${saved.version}，状态 ${saved.status}。`);
        } catch (err) {
            setActionError(`保存草稿失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const handleValidate = async () => {
        setNotice(null);
        setActionError(null);
        setPreview(null);
        const parsed = parseJsonDraft(draftJson);
        if (!parsed.ok) {
            setActionError(`JSON 校验未通过：${parsed.message}`);
            return;
        }

        setBusyAction("validate");
        try {
            const result = await api.admin.validateBusinessRule(configKey, parsed.value, reason.trim() || undefined);
            setDraftJson(formatJson(result.normalized_value));
            setNotice("后端配置校验通过，编辑区已更新为规范化配置。");
        } catch (err) {
            setActionError(`后端校验失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const handlePreview = async () => {
        setNotice(null);
        setActionError(null);
        setPreview(null);
        const parsed = parseJsonDraft(draftJson);
        if (!parsed.ok) {
            setActionError(`JSON 校验未通过：${parsed.message}`);
            return;
        }

        setBusyAction("preview");
        try {
            const result = await api.admin.previewBusinessRule(configKey, parsed.value, reason.trim() || undefined);
            setPreview(result);
            setNotice(`预览完成；当前生效版本仍为 ${result.active_version ?? activeConfig?.version ?? "默认配置"}。`);
        } catch (err) {
            setActionError(`预览失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const handlePublish = async () => {
        setNotice(null);
        setActionError(null);
        setPreview(null);
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        const target = draftConfig ?? selectedConfig;
        if (!target || target.status !== "draft") {
            setActionError("需要先保存草稿，才能发布。");
            return;
        }

        setBusyAction("publish");
        try {
            const published = await api.admin.publishBusinessRule(configKey, target.id, trimmedReason);
            await loadRule();
            setSelectedConfigId(published.id);
            setDraftJson(formatJson(published.value));
            setNotice(`发布完成：v${published.version}，状态 ${published.status}。`);
        } catch (err) {
            setActionError(`发布失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const handleRollback = async (target: BusinessRuleConfigRecord) => {
        setNotice(null);
        setActionError(null);
        setPreview(null);
        const trimmedReason = requireReason();
        if (!trimmedReason) return;

        setBusyAction("rollback");
        try {
            const rolledBack = await api.admin.rollbackBusinessRule(configKey, target.id, trimmedReason);
            await loadRule();
            setSelectedConfigId(rolledBack.id);
            setDraftJson(formatJson(rolledBack.value));
            setNotice(`回滚完成：v${rolledBack.version}，状态 ${rolledBack.status}。`);
        } catch (err) {
            setActionError(`回滚失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAction(null);
        }
    };

    const requestPublish = () => {
        setNotice(null);
        setActionError(null);
        setPreview(null);
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        const target = draftConfig ?? selectedConfig;
        if (!target || target.status !== "draft") {
            setActionError("需要先保存草稿，才能发布。");
            return;
        }
        setConfirmAction({ type: "publish" });
    };

    const requestRollback = (target: BusinessRuleConfigRecord) => {
        setNotice(null);
        setActionError(null);
        setPreview(null);
        const trimmedReason = requireReason();
        if (!trimmedReason) return;
        setConfirmAction({ type: "rollback", target });
    };

    const handleConfirmAction = () => {
        const action = confirmAction;
        setConfirmAction(null);
        if (!action) return;
        if (action.type === "publish") {
            void handlePublish();
            return;
        }
        void handleRollback(action.target);
    };

    if (loading) {
        return (
            <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-slate-600">
                正在加载{title}...
            </div>
        );
    }

    if (error) {
        return (
            <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8">
                <h1 className="text-2xl font-black text-slate-900">{title}</h1>
                <p className="text-sm text-amber-800">{error}</p>
                <p className="text-sm text-slate-600">
                    当前不会保存本地草稿；请等待业务规则 API 恢复后再预览、发布或回滚。
                </p>
                <Button onClick={loadRule}>重试加载</Button>
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
                title={confirmAction?.type === "rollback" ? "确认回滚业务规则" : "确认发布业务规则"}
                description={confirmAction?.type === "rollback"
                    ? `将 ${title} 回滚到 v${confirmAction.target.version}。原因：${reason.trim()}`
                    : `将 ${title} 当前草稿发布为生效配置。原因：${reason.trim()}`}
                confirmText={confirmAction?.type === "rollback" ? "确认回滚" : "确认发布"}
                variant={confirmAction?.type === "rollback" ? "warning" : "danger"}
                onConfirm={handleConfirmAction}
                isLoading={busyAction === "publish" || busyAction === "rollback"}
            />

            <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                    <div className="flex flex-wrap items-center gap-2">
                        <h1 className="text-3xl font-black tracking-tight text-slate-900">{title}</h1>
                        <Badge variant={activeConfig?.enabled === false ? "orange" : "green"}>
                            {activeConfig?.enabled === false ? "已禁用" : "已治理"}
                        </Badge>
                    </div>
                    <p className="mt-2 max-w-3xl text-sm text-slate-600">{description}</p>
                    <p className="mt-2 max-w-3xl text-xs text-slate-500">
                        配置标识：{configKey} · 读取位置：{data?.definition.read_path || "未返回"} · 权限：{data?.definition.permission || "未返回"}
                    </p>
                </div>
                <Button variant="outline" onClick={loadRule}>刷新配置</Button>
            </header>

            <div className="grid gap-4 lg:grid-cols-3">
                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">生效配置</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">
                        {activeConfig ? `v${activeConfig.version}` : "默认兜底"}
                    </div>
                    <p className="mt-2 text-sm text-slate-600">状态：{activeConfig?.status ? formatConfigStatus(activeConfig.status) : "数据库配置缺失"}</p>
                    <p className="mt-1 text-sm text-slate-600">更新：{formatDateTime(activeConfig?.updated_at)}</p>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">兜底策略</div>
                    <div className="mt-2 text-sm font-bold text-slate-900">{data?.definition.fallback_policy}</div>
                    <p className="mt-2 text-sm text-slate-600">配置缺失或非法时由后端规则服务统一兜底。</p>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">审计</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{data?.audit_logs?.length ?? 0}</div>
                    <p className="mt-2 text-sm text-slate-600">发布、回滚、预览和校验均写入审计记录。</p>
                </GlassCard>
            </div>

            <GlassCard className="space-y-5 p-6">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <h2 className="text-xl font-black text-slate-900">配置草稿</h2>
                        <p className="mt-1 text-sm text-slate-600">
                            选中：{selectedConfig ? `${formatConfigStatus(selectedConfig.status)} · v${selectedConfig.version}` : "默认值"}。
                            编辑区只保存为后台草稿，发布后才会成为生效配置。
                        </p>
                    </div>
                    <select
                        aria-label={`选择${title}配置版本`}
                        value={selectedConfig?.id ?? ""}
                        onChange={(event) => {
                            const next = data?.items.find((item) => item.id === event.target.value) ?? null;
                            setSelectedConfigId(next?.id ?? null);
                            setDraftJson(formatJson(next?.value ?? data?.definition.default_value ?? {}));
                            setPreview(null);
                            setNotice(null);
                            setActionError(null);
                        }}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700"
                    >
                        {data?.items.map((item) => (
                            <option key={item.id} value={item.id}>
                                {formatConfigStatus(item.status)} · v{item.version}
                            </option>
                        ))}
                        {(data?.items.length ?? 0) === 0 && <option value="">默认配置</option>}
                    </select>
                </div>

                <JsonEditorWithValidation
                    label={`${title} JSON 配置`}
                    value={draftJson}
                    onChange={(value) => {
                        setDraftJson(value);
                        setPreview(null);
                    }}
                    rows={22}
                    isValid={parsedDraft.ok}
                    validationMessage={parsedDraft.ok
                        ? "JSON 对象格式有效；仍需后端规则校验后才能发布。"
                        : `JSON 格式错误：${parsedDraft.message}`}
                    helpText="必须是 JSON 对象；后端会在校验、预览、发布时执行规则约束。"
                />

                <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto_auto_auto] lg:items-center">
                    <input
                        value={reason}
                        onChange={(event) => setReason(event.target.value)}
                        placeholder="操作原因（保存、发布、回滚必填，将进入审计记录）"
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                    />
                    <Button variant="outline" onClick={handleValidate} disabled={!parsedDraft.ok || busyAction !== null}>
                        {busyAction === "validate" ? "校验中..." : "后端校验"}
                    </Button>
                    <Button variant="outline" onClick={handlePreview} disabled={!parsedDraft.ok || busyAction !== null}>
                        {busyAction === "preview" ? "预览中..." : "预览影响"}
                    </Button>
                    <Button variant="outline" onClick={handleSaveDraft} disabled={!parsedDraft.ok || busyAction !== null}>
                        {busyAction === "save" ? "保存中..." : "保存草稿"}
                    </Button>
                    <Button onClick={requestPublish} disabled={!draftConfig || busyAction !== null}>
                        {busyAction === "publish" ? "发布中..." : "发布草稿"}
                    </Button>
                </div>

                {notice && (
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>
                )}
                {actionError && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{actionError}</div>
                )}
                {previewText && (
                    <div className="rounded-2xl border border-blue-100 bg-blue-50/80 p-4 text-sm text-blue-900">
                        预览摘要：{previewText}
                    </div>
                )}
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-xl font-black text-slate-900">发布历史与审计</h2>
                <div className="grid gap-3">
                    {historyItems.map((item) => (
                        <div key={item.id} className="flex flex-col gap-3 rounded-2xl border border-slate-100 bg-white/80 p-4 md:flex-row md:items-center md:justify-between">
                            <div>
                                <div className="font-bold text-slate-900">v{item.version} · {formatConfigStatus(item.status)}</div>
                                <div className="mt-1 text-sm text-slate-600">
                                    更新人：{item.updated_by || "未记录"} · {formatDateTime(item.updated_at)}
                                </div>
                                <div className="mt-1 text-xs text-slate-500">
                                    config: {item.id}
                                </div>
                            </div>
                            <Button
                                variant="outline"
                                onClick={() => requestRollback(item)}
                                disabled={busyAction !== null || item.id === activeConfig?.id}
                            >
                                回滚到此版本
                            </Button>
                        </div>
                    ))}
                    {historyItems.length === 0 && (
                        <p className="text-sm text-slate-500">暂无数据库历史；当前使用后端默认配置兜底。</p>
                    )}
                </div>

                {(data?.audit_logs || []).length > 0 && (
                    <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4">
                        <h3 className="text-sm font-bold text-slate-900">最近审计记录</h3>
                        <ul className="mt-3 space-y-2 text-sm text-slate-600">
                            {(data?.audit_logs || []).slice(0, 6).map((entry, index) => (
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
