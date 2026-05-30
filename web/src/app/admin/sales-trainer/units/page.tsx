"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerUnit } from "@/lib/api/types";

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

    async function loadUnits() {
        setIsLoading(true);
        setError(null);
        try {
            const result = await api.admin.salesTrainer.listUnits({
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
                await api.admin.salesTrainer.publishUnit(confirmState.unit.unit_id);
                toast.success("训练单元已发布");
            } else {
                await api.admin.salesTrainer.archiveUnit(confirmState.unit.unit_id);
                toast.success("训练单元已归档");
            }
            setConfirmState(null);
            await loadUnits();
        } catch (operateError) {
            toast.error(getApiErrorMessage(operateError));
            setIsOperating(false);
        }
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="销售训练单元"
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
                        ) : units.length === 0 ? (
                            <tr>
                                <td colSpan={6} className="px-6 py-10 text-center text-slate-500">
                                    暂无训练单元
                                </td>
                            </tr>
                        ) : units.map((unit) => (
                            <tr key={unit.unit_id} className="border-b border-slate-100 last:border-b-0">
                                <td className="px-6 py-4">
                                    <div>
                                        <p className="font-medium text-slate-900">{unit.name}</p>
                                        <p className="mt-1 text-xs text-slate-500">{unit.description || "未填写说明"}</p>
                                    </div>
                                </td>
                                <td className="px-6 py-4">{getUnitTypeLabel(unit.unit_type)}</td>
                                <td className="px-6 py-4">
                                    <Badge className="bg-slate-100 text-slate-700">{unit.status}</Badge>
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
                                                发布
                                            </Button>
                                        ) : null}
                                        {unit.status !== "archived" ? (
                                            <Button variant="outline" size="sm" onClick={() => setConfirmState({ type: "archive", unit })}>
                                                归档
                                            </Button>
                                        ) : null}
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </GlassCard>
        </AdminIndexShell>
    );
}
