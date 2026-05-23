"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Copy, Plus } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage, getExaminerAgentErrorDetails } from "@/lib/api/client";
import type { ExaminerAgentGateResult, ExaminerAgentRecord, TemplateReferenceItem } from "@/lib/api/types";
import { debug } from "@/lib/debug";

import {
    assetCardClassName,
    ContentAssetStatusGuide,
} from "../content-asset-status-guide";
import {
    formatDateTime,
    statusLabel,
    statusVariant,
    strategySummary,
} from "./examiner-agent-utils";

const BASE_PATH = "/admin/curriculum-practice/examiner-agents";

type ConfirmTarget =
    | { type: "publish" | "archive"; agent: ExaminerAgentRecord }
    | { type: "unpublish"; agent: ExaminerAgentRecord; references: TemplateReferenceItem[] };

export function ExaminerAgentIndex() {
    const router = useRouter();
    const toast = useToast();
    const [items, setItems] = useState<ExaminerAgentRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [gateResults, setGateResults] = useState<ExaminerAgentGateResult[]>([]);
    const [notice, setNotice] = useState<string | null>(null);
    const [busyAgentId, setBusyAgentId] = useState<string | null>(null);
    const [statusFilter, setStatusFilter] = useState<string>("");
    const [confirmTarget, setConfirmTarget] = useState<ConfirmTarget | null>(null);

    const loadAgents = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.admin.listExaminerAgents(statusFilter || undefined);
            setItems(response.items);
        } catch (err) {
            setError(`ExamAgent 加载失败：${getApiErrorMessage(err)}`);
            debug.warn("[ExaminerAgentIndex] failed to load agents", { error: err });
        } finally {
            setLoading(false);
        }
    }, [statusFilter]);

    useEffect(() => {
        void Promise.resolve().then(loadAgents);
    }, [loadAgents]);

    const duplicateAgent = async (record: ExaminerAgentRecord) => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setBusyAgentId(record.examiner_agent_id);
        try {
            const duplicated = await api.admin.duplicateExaminerAgent(record.examiner_agent_id);
            setItems((current) => [duplicated, ...current.filter((item) => item.examiner_agent_id !== duplicated.examiner_agent_id)]);
            const references = await api.admin.getExaminerAgentTemplateReferences(record.examiner_agent_id);
            const baseMessage = `已复制为新草稿：${duplicated.name}`;
            if (references.items.length > 0) {
                toast.success(`${baseMessage}。以下已发布模板仍绑定旧版本，请在模板草稿中换绑并重发：${references.items.map((ref) => ref.name).join("、")}`);
            } else {
                toast.success(baseMessage);
            }
            router.push(`${BASE_PATH}/${duplicated.examiner_agent_id}/edit`);
        } catch (err) {
            setActionError(`复制失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAgentId(null);
        }
    };

    const requestUnpublish = async (record: ExaminerAgentRecord) => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setBusyAgentId(record.examiner_agent_id);
        try {
            const references = await api.admin.getExaminerAgentTemplateReferences(record.examiner_agent_id);
            setConfirmTarget({ type: "unpublish", agent: record, references: references.items });
        } catch (err) {
            setActionError(`读取模板引用失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAgentId(null);
        }
    };

    const handleUnpublish = async (record: ExaminerAgentRecord, acknowledge: boolean) => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setBusyAgentId(record.examiner_agent_id);
        try {
            const unpublished = await api.admin.unpublishExaminerAgent(record.examiner_agent_id, acknowledge);
            setItems((current) =>
                current.map((item) => (item.examiner_agent_id === unpublished.examiner_agent_id ? unpublished : item)),
            );
            setNotice(`已退回草稿：${unpublished.name}`);
        } catch (err) {
            const details = getExaminerAgentErrorDetails(err);
            if (details?.referencing_templates?.length) {
                setConfirmTarget({
                    type: "unpublish",
                    agent: record,
                    references: details.referencing_templates,
                });
            }
            setActionError(`退回草稿失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAgentId(null);
        }
    };

    const handlePublish = async (record: ExaminerAgentRecord) => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setBusyAgentId(record.examiner_agent_id);
        try {
            const published = await api.admin.publishExaminerAgent(record.examiner_agent_id);
            setItems((current) =>
                current.map((item) => (item.examiner_agent_id === published.examiner_agent_id ? published : item)),
            );
            setNotice(`发布完成：${published.name} v${published.version}`);
        } catch (err) {
            const details = getExaminerAgentErrorDetails(err);
            setGateResults(details?.gate_results ?? []);
            setActionError(`发布失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAgentId(null);
        }
    };

    const handleArchive = async (record: ExaminerAgentRecord) => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setBusyAgentId(record.examiner_agent_id);
        try {
            const archived = await api.admin.archiveExaminerAgent(record.examiner_agent_id);
            setItems((current) =>
                current.map((item) => (item.examiner_agent_id === archived.examiner_agent_id ? archived : item)),
            );
            setNotice(`归档完成：${archived.name}`);
        } catch (err) {
            setActionError(`归档失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyAgentId(null);
        }
    };

    const confirmDescription = confirmTarget
        ? confirmTarget.type === "archive"
            ? `将「${confirmTarget.agent.name}」归档，归档后不能再作为可用 ExamAgent。`
            : confirmTarget.type === "unpublish"
                ? confirmTarget.references.length > 0
                    ? `将「${confirmTarget.agent.name}」退回草稿。以下已发布模板仍引用此 ExamAgent：${confirmTarget.references.map((ref) => ref.name).join("、")}`
                    : `将「${confirmTarget.agent.name}」退回草稿。当前没有已发布模板引用此 ExamAgent。`
                : `将「${confirmTarget.agent.name}」发布为可用 ExamAgent，发布门禁会再次校验题目来源和评分策略。`
        : "确认执行该 ExamAgent 操作。";

    if (loading) {
        return <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-slate-600">正在加载 ExamAgent 列表...</div>;
    }

    if (error) {
        return (
            <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8">
                <h1 className="text-2xl font-black text-slate-900">考试智能体管理</h1>
                <p className="text-sm text-amber-800">{error}</p>
                <Button onClick={loadAgents}>重试加载</Button>
            </GlassCard>
        );
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="考试智能体管理"
                    description="管理 ExaminerAgent 配置。列表页仅展示状态与发布操作；创建、编辑和模拟测试在独立路由完成。"
                    primaryAction={(
                        <Button className="rounded-full" onClick={() => router.push(`${BASE_PATH}/new`)}>
                            <Plus className="mr-2 h-4 w-4" />
                            新建 ExamAgent
                        </Button>
                    )}
                    secondaryActions={(
                        <>
                            <select
                                className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
                                value={statusFilter}
                                onChange={(event) => setStatusFilter(event.target.value)}
                            >
                                <option value="">全部状态</option>
                                <option value="draft">草稿</option>
                                <option value="published">已发布</option>
                                <option value="archived">已归档</option>
                            </select>
                            <Button variant="outline" onClick={loadAgents}>刷新列表</Button>
                        </>
                    )}
                />
            )}
        >
            <ConfirmDialog
                open={!!confirmTarget}
                onOpenChange={(open) => {
                    if (!open) setConfirmTarget(null);
                }}
                title={
                    confirmTarget?.type === "archive"
                        ? "确认归档考试智能体"
                        : confirmTarget?.type === "unpublish"
                            ? "确认退回草稿（慎用）"
                            : "确认发布考试智能体"
                }
                description={confirmDescription}
                confirmText={
                    confirmTarget?.type === "archive"
                        ? "确认归档"
                        : confirmTarget?.type === "unpublish"
                            ? "确认退回草稿"
                            : "确认发布"
                }
                variant={confirmTarget?.type === "publish" ? "danger" : "warning"}
                onConfirm={() => {
                    const target = confirmTarget;
                    setConfirmTarget(null);
                    if (!target) return;
                    if (target.type === "archive") void handleArchive(target.agent);
                    else if (target.type === "unpublish") void handleUnpublish(target.agent, true);
                    else void handlePublish(target.agent);
                }}
                isLoading={busyAgentId !== null}
            />

            {notice && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
            {actionError && (
                <div className="space-y-2 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                    <p>{actionError}</p>
                    {gateResults.length > 0 && (
                        <ul className="list-disc space-y-1 pl-5">
                            {gateResults.map((result) => (
                                <li key={`${result.gate_name}-${result.reason_code}-${result.message}`}>
                                    <span className="font-semibold">{result.reason_code}</span>：{result.message}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}

            <GlassCard className="space-y-4 p-6">
                <div className="flex items-center justify-between">
                    <h2 className="text-xl font-black text-slate-900">ExamAgent 列表</h2>
                    <Badge variant="gray">{items.length} agents</Badge>
                </div>
                <div className="grid gap-3">
                    {items.map((item) => (
                        <div key={item.examiner_agent_id} className={assetCardClassName(item.status)}>
                            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                <div className="flex-1 space-y-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h3 className="font-bold text-slate-900">{item.name}</h3>
                                        <Badge variant={statusVariant(item.status)}>
                                            {statusLabel(item.status)} · v{item.version}
                                        </Badge>
                                    </div>
                                    <ContentAssetStatusGuide status={item.status} compact />
                                    <p className="text-sm text-slate-600">
                                        等级策略：{strategySummary(item.learner_level_strategy)}
                                        {item.scoring_policy_id ? ` · 评分策略：${item.scoring_policy_id}` : ""}
                                    </p>
                                    {item.description ? <p className="text-sm text-slate-500">{item.description}</p> : null}
                                    <p className="text-xs text-slate-500">
                                        题目来源：{item.question_source_ids.join(", ") || "无"}
                                        {" · "}超时：{item.timeout_config.max_seconds}s
                                    </p>
                                    <p className="text-xs text-slate-400">
                                        创建：{formatDateTime(item.created_at)}
                                        {item.published_at ? ` · 发布：${formatDateTime(item.published_at)}` : ""}
                                    </p>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    {item.status === "draft" ? (
                                        <Button variant="outline" asChild>
                                            <Link href={`${BASE_PATH}/${item.examiner_agent_id}/edit`}>编辑</Link>
                                        </Button>
                                    ) : item.status === "published" ? (
                                        <Button
                                            onClick={() => { void duplicateAgent(item); }}
                                            disabled={busyAgentId !== null}
                                        >
                                            <Copy className="mr-2 h-4 w-4" />
                                            {busyAgentId === item.examiner_agent_id ? "复制中..." : "复制为新草稿"}
                                        </Button>
                                    ) : null}
                                    {item.status === "published" ? (
                                        <Button
                                            variant="outline"
                                            onClick={() => { void requestUnpublish(item); }}
                                            disabled={busyAgentId !== null}
                                        >
                                            退回草稿（慎用）
                                        </Button>
                                    ) : null}
                                    <Button variant="outline" asChild>
                                        <Link href={`${BASE_PATH}/${item.examiner_agent_id}/simulate`}>模拟</Link>
                                    </Button>
                                    <Button
                                        onClick={() => setConfirmTarget({ type: "publish", agent: item })}
                                        disabled={item.status === "published" || busyAgentId !== null}
                                    >
                                        {busyAgentId === item.examiner_agent_id ? "处理中..." : "发布"}
                                    </Button>
                                    {item.status !== "archived" && (
                                        <Button
                                            variant="outline"
                                            onClick={() => setConfirmTarget({ type: "archive", agent: item })}
                                            disabled={busyAgentId !== null}
                                        >
                                            {busyAgentId === item.examiner_agent_id ? "处理中..." : "归档"}
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                    {items.length === 0 && <p className="text-sm text-slate-500">暂无 ExamAgent 记录。</p>}
                </div>
            </GlassCard>
        </AdminIndexShell>
    );
}
