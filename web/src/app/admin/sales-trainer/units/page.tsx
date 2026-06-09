"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { History } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import {
    filterNewcomerAdminUnits,
    formatAdminStatus,
    normalizeNewcomerUnitDisplay,
} from "@/lib/sales-trainer/admin-display";
import type { NewcomerUnitRevision, SalesTrainerUnit } from "@/lib/api/types";

type ConfirmState =
    | { type: "publish"; unit: SalesTrainerUnit }
    | { type: "archive"; unit: SalesTrainerUnit }
    | null;

function getUnitTypeLabel(unitType: SalesTrainerUnit["unit_type"]): string {
    return unitType === "quiz" ? "做题训练" : "录音评分";
}

export default function SalesTrainerUnitsPage() {
    const pathname = usePathname();
    const router = useRouter();
    const toast = useToast();
    const [units, setUnits] = useState<SalesTrainerUnit[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isOperating, setIsOperating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [confirmState, setConfirmState] = useState<ConfirmState>(null);
    const [historyUnit, setHistoryUnit] = useState<SalesTrainerUnit | null>(null);
    const [revisions, setRevisions] = useState<NewcomerUnitRevision[]>([]);
    const [isHistoryLoading, setIsHistoryLoading] = useState(false);
    const [rollbackReasonByRevision, setRollbackReasonByRevision] = useState<Record<string, string>>({});
    const [rollbackRevisionId, setRollbackRevisionId] = useState<string | null>(null);

    async function loadUnits() {
        setIsLoading(true);
        setError(null);
        try {
            const result = await api.admin.newcomerTraining.listUnits({
                include_archived: true,
                limit: 100,
            });
            setUnits(result.items);
        } catch (loadError) {
            setUnits([]);
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }

    useEffect(() => {
        void loadUnits();
    }, []);

    async function handleConfirm() {
        if (!confirmState) {
            return;
        }
        setIsOperating(true);
        try {
            if (confirmState.type === "publish") {
                await api.admin.newcomerTraining.publishUnit(confirmState.unit.unit_id);
                toast.success("训练单元已发布并生效，后续学员将使用当前版本");
            } else {
                await api.admin.newcomerTraining.archiveUnit(confirmState.unit.unit_id);
                toast.success("训练单元已归档");
            }
            setConfirmState(null);
            await loadUnits();
        } catch (operateError) {
            toast.error(getApiErrorMessage(operateError));
            setIsOperating(false);
        }
    }

    async function openRevisionHistory(unit: SalesTrainerUnit) {
        setHistoryUnit(unit);
        setRevisions([]);
        setRollbackReasonByRevision({});
        setIsHistoryLoading(true);
        try {
            const result = await api.admin.newcomerTraining.listUnitRevisions(unit.unit_id);
            setRevisions(result.items);
        } catch (loadError) {
            toast.error(getApiErrorMessage(loadError));
        } finally {
            setIsHistoryLoading(false);
        }
    }

    async function rollbackToRevision(revision: NewcomerUnitRevision) {
        if (!historyUnit) {
            return;
        }
        const reason = rollbackReasonByRevision[revision.revision_id]?.trim() ?? "";
        if (!reason) {
            toast.error("请填写回滚原因。");
            return;
        }
        setRollbackRevisionId(revision.revision_id);
        try {
            await api.admin.newcomerTraining.rollbackUnit(historyUnit.unit_id, {
                target_revision_id: revision.revision_id,
                reason,
            });
            toast.success(`已回滚到第 ${revision.revision_no} 版，后续学员将使用该版本`);
            await loadUnits();
            await openRevisionHistory(historyUnit);
        } catch (rollbackError) {
            toast.error(getApiErrorMessage(rollbackError));
        } finally {
            setRollbackRevisionId(null);
        }
    }

    const scopedUnits = filterNewcomerAdminUnits(units);

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="新人训练路径模块单元"
                    description="列表页只做浏览与流转操作；新增和编辑都在独立页面完成。"
                    primaryAction={(
                        <Button
                            className="rounded-full bg-slate-900 text-white"
                            onClick={() => router.push("/admin/sales-trainer/units/new")}
                        >
                            新建训练单元
                        </Button>
                    )}
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
                />
            )}
        >
            <ConfirmDialog
                open={Boolean(confirmState)}
                onOpenChange={(open) => !open && setConfirmState(null)}
                title={confirmState?.type === "publish" ? "发布训练单元" : "归档训练单元"}
                description={confirmState?.unit.name || ""}
                confirmText={confirmState?.type === "publish" ? "确认发布" : "确认归档"}
                onConfirm={() => void handleConfirm()}
                isLoading={isOperating}
            />

            <div className="space-y-4">
                <GlassCard className="overflow-hidden p-0">
                    {error ? (
                        <div className="border-b border-red-100 bg-red-50 px-6 py-4 text-sm text-red-700">
                            {error}
                        </div>
                    ) : null}
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-100 text-left text-slate-500">
                                <th className="px-6 py-4">名称</th>
                                <th className="px-6 py-4">类型</th>
                                <th className="px-6 py-4">状态</th>
                                <th className="px-6 py-4">题目数</th>
                                <th className="px-6 py-4">更新时间</th>
                                <th className="px-6 py-4">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr>
                                    <td colSpan={6} className="px-6 py-10 text-center text-slate-500">
                                        正在加载训练单元...
                                    </td>
                                </tr>
                            ) : scopedUnits.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="px-6 py-10 text-center text-slate-500">
                                        暂无训练单元
                                    </td>
                                </tr>
                            ) : scopedUnits.map((unit) => {
                                const displayUnit = normalizeNewcomerUnitDisplay(unit);
                                return (
                                    <tr key={unit.unit_id} className="border-b border-slate-100 last:border-b-0">
                                        <td className="px-6 py-4">
                                            <div>
                                                <p className="font-medium text-slate-900">{displayUnit.name}</p>
                                                <p className="mt-1 text-xs text-slate-500">{displayUnit.description || "未填写说明"}</p>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">{getUnitTypeLabel(unit.unit_type)}</td>
                                        <td className="px-6 py-4">
                                            <Badge className="bg-slate-100 text-slate-700">{formatAdminStatus(unit.status)}</Badge>
                                        </td>
                                        <td className="px-6 py-4">{unit.questions.length}</td>
                                        <td className="px-6 py-4">{new Date(unit.updated_at).toLocaleString()}</td>
                                        <td className="px-6 py-4">
                                            <div className="flex flex-wrap gap-2">
                                                <Button variant="outline" size="sm" onClick={() => router.push(`/admin/sales-trainer/units/${unit.unit_id}/edit`)}>
                                                    编辑
                                                </Button>
                                                {unit.status !== "published" ? (
                                                    <Button variant="outline" size="sm" onClick={() => setConfirmState({ type: "publish", unit })}>
                                                        发布并生效
                                                    </Button>
                                                ) : null}
                                                <Button variant="outline" size="sm" onClick={() => void openRevisionHistory(unit)}>
                                                    <History className="mr-1 h-4 w-4" />
                                                    历史版本
                                                </Button>
                                                {unit.status !== "archived" ? (
                                                    <Button variant="outline" size="sm" onClick={() => setConfirmState({ type: "archive", unit })}>
                                                        归档
                                                    </Button>
                                                ) : null}
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </GlassCard>
                {historyUnit ? (
                    <GlassCard className="space-y-4 p-6">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                                <h2 className="text-lg font-bold text-slate-900">历史版本：{normalizeNewcomerUnitDisplay(historyUnit).name}</h2>
                                <p className="mt-1 text-sm text-slate-600">回滚只影响后续学员；已经开始的学习、考试和录音记录继续保留当时快照。</p>
                            </div>
                            <Button variant="outline" size="sm" onClick={() => setHistoryUnit(null)}>关闭</Button>
                        </div>
                        {isHistoryLoading ? (
                            <p className="text-sm text-slate-500">正在加载历史版本...</p>
                        ) : revisions.length === 0 ? (
                            <p className="text-sm text-slate-500">暂无历史版本。</p>
                        ) : (
                            <div className="space-y-3">
                                {revisions.map((revision) => {
                                    const canRollback = revision.status === "published" && !revision.is_active;
                                    const reason = rollbackReasonByRevision[revision.revision_id] ?? "";
                                    return (
                                        <div key={revision.revision_id} className="rounded-lg border border-slate-200 bg-white p-4">
                                            <div className="flex flex-wrap items-center justify-between gap-3">
                                                <div>
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <p className="font-semibold text-slate-900">第 {revision.revision_no} 版</p>
                                                        {revision.is_active ? <Badge className="bg-emerald-100 text-emerald-800">当前生效</Badge> : null}
                                                        {revision.is_working ? <Badge className="bg-amber-100 text-amber-800">待发布修订</Badge> : null}
                                                        {revision.change_class === "scoring_high_risk" ? <Badge className="bg-rose-100 text-rose-800">评分相关变更</Badge> : null}
                                                    </div>
                                                    <p className="mt-1 text-sm text-slate-600">{revision.title ?? "未命名版本"} · {revision.question_count} 题</p>
                                                </div>
                                            </div>
                                            {canRollback ? (
                                                <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
                                                    <label className="sr-only" htmlFor={`unit-rollback-reason-${revision.revision_no}`}>回滚原因（第 {revision.revision_no} 版）</label>
                                                    <Input
                                                        id={`unit-rollback-reason-${revision.revision_no}`}
                                                        placeholder={`回滚原因（第 ${revision.revision_no} 版）`}
                                                        value={reason}
                                                        onChange={(event) => setRollbackReasonByRevision((current) => ({
                                                            ...current,
                                                            [revision.revision_id]: event.target.value,
                                                        }))}
                                                        disabled={rollbackRevisionId === revision.revision_id}
                                                    />
                                                    <Button
                                                        variant="outline"
                                                        onClick={() => void rollbackToRevision(revision)}
                                                        disabled={rollbackRevisionId === revision.revision_id || !reason.trim()}
                                                    >
                                                        回滚到第 {revision.revision_no} 版
                                                    </Button>
                                                </div>
                                            ) : null}
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </GlassCard>
                ) : null}
            </div>
        </AdminIndexShell>
    );
}
