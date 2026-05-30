"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Milestone, RefreshCw } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerUnit } from "@/lib/api/types";

type PathUnit = {
    unit: SalesTrainerUnit;
    pathKey: string;
    pathTitle: string;
    goalTitle: string | null;
    levelTitle: string;
    orderIndex: number;
    completionRule: string;
    unlockAfterUnitIds: string[];
};

function getUnitTypeLabel(unitType: SalesTrainerUnit["unit_type"]): string {
    return unitType === "quiz" ? "做题训练" : "录音评分";
}

function pathUnitFrom(unit: SalesTrainerUnit): PathUnit | null {
    const path = unit.config.path;
    if (!path?.enabled || !path.path_key) {
        return null;
    }
    return {
        unit,
        pathKey: path.path_key,
        pathTitle: path.path_title || "销售训练闯关",
        goalTitle: path.goal_title || null,
        levelTitle: path.level_title || unit.name,
        orderIndex: path.order_index || 1,
        completionRule: path.completion_rule || "passed",
        unlockAfterUnitIds: path.unlock_after_unit_ids || [],
    };
}

function groupPathUnits(units: SalesTrainerUnit[]): PathUnit[][] {
    const grouped = new Map<string, PathUnit[]>();
    units.forEach((unit) => {
        const pathUnit = pathUnitFrom(unit);
        if (!pathUnit) {
            return;
        }
        grouped.set(pathUnit.pathKey, [...(grouped.get(pathUnit.pathKey) || []), pathUnit]);
    });
    return Array.from(grouped.values())
        .map((items) => items.sort((left, right) => left.orderIndex - right.orderIndex))
        .sort((left, right) => left[0].pathKey.localeCompare(right[0].pathKey));
}

export default function SalesTrainerPathsPage() {
    const pathname = usePathname();
    const router = useRouter();
    const [units, setUnits] = useState<SalesTrainerUnit[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    async function loadUnits() {
        setIsLoading(true);
        setError(null);
        try {
            const result = await api.admin.salesTrainer.listUnits({
                include_archived: true,
                limit: 200,
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

    const pathGroups = useMemo(() => groupPathUnits(units), [units]);

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="销售训练路径"
                    description="训练路径由训练单元的路径配置聚合而来；调整关卡顺序、解锁条件和反馈文案请进入对应训练单元编辑。"
                    icon={<Milestone className="h-7 w-7 text-slate-800" />}
                    primaryAction={(
                        <Button className="rounded-full bg-slate-900 text-white" onClick={() => router.push("/admin/sales-trainer/units/new")}>
                            新建关卡
                        </Button>
                    )}
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
                />
            )}
        >
            {error ? (
                <GlassCard className="space-y-3 border-red-100 bg-red-50 p-4">
                    <p className="text-sm font-medium text-red-700">训练路径加载失败：{error}</p>
                    <Button variant="outline" className="rounded-full" onClick={() => void loadUnits()}>
                        重试
                    </Button>
                </GlassCard>
            ) : null}

            <div className="flex justify-end">
                <Button variant="outline" className="rounded-full" onClick={() => void loadUnits()} disabled={isLoading}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    刷新
                </Button>
            </div>

            {isLoading ? (
                <GlassCard className="p-8 text-center text-sm text-slate-500">正在加载训练路径...</GlassCard>
            ) : pathGroups.length === 0 ? (
                <GlassCard className="space-y-3 p-8 text-center">
                    <p className="text-lg font-bold text-slate-900">暂无训练路径</p>
                    <p className="text-sm text-slate-500">在训练单元中开启“加入销售训练闯关路径”后，这里会自动聚合展示。</p>
                    <Button className="rounded-full bg-slate-900 text-white" onClick={() => router.push("/admin/sales-trainer/units/new")}>
                        创建第一个关卡
                    </Button>
                </GlassCard>
            ) : (
                <div className="space-y-5">
                    {pathGroups.map((items) => {
                        const first = items[0];
                        const publishedCount = items.filter((item) => item.unit.status === "published").length;
                        return (
                            <GlassCard key={first.pathKey} className="space-y-4 p-6">
                                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                    <div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <h2 className="text-xl font-black text-slate-900">{first.pathTitle}</h2>
                                            <Badge className="bg-slate-100 text-slate-700">{first.pathKey}</Badge>
                                        </div>
                                        <p className="mt-1 text-sm text-slate-500">{first.goalTitle || "未配置训练目标。"}</p>
                                    </div>
                                    <div className="rounded-2xl bg-slate-50 px-4 py-3 text-right">
                                        <p className="text-xs text-slate-500">已发布关卡</p>
                                        <p className="mt-1 text-2xl font-black text-slate-900">{publishedCount}/{items.length}</p>
                                    </div>
                                </div>

                                <div className="overflow-hidden rounded-2xl border border-slate-100">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="border-b border-slate-100 bg-slate-50 text-left text-slate-500">
                                                <th className="px-4 py-3">顺序</th>
                                                <th className="px-4 py-3">关卡</th>
                                                <th className="px-4 py-3">类型</th>
                                                <th className="px-4 py-3">通关规则</th>
                                                <th className="px-4 py-3">前置关卡</th>
                                                <th className="px-4 py-3">状态</th>
                                                <th className="px-4 py-3">操作</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {items.map((item) => (
                                                <tr key={item.unit.unit_id} className="border-b border-slate-100 last:border-b-0">
                                                    <td className="px-4 py-3 font-semibold text-slate-900">{item.orderIndex}</td>
                                                    <td className="px-4 py-3">
                                                        <p className="font-medium text-slate-900">{item.levelTitle}</p>
                                                        <p className="mt-1 text-xs text-slate-500">{item.unit.name}</p>
                                                    </td>
                                                    <td className="px-4 py-3">{getUnitTypeLabel(item.unit.unit_type)}</td>
                                                    <td className="px-4 py-3">{item.completionRule}</td>
                                                    <td className="px-4 py-3">{item.unlockAfterUnitIds.length ? item.unlockAfterUnitIds.join(", ") : "无"}</td>
                                                    <td className="px-4 py-3">
                                                        <Badge className="bg-slate-100 text-slate-700">{item.unit.status}</Badge>
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <Button variant="outline" size="sm" onClick={() => router.push(`/admin/sales-trainer/units/${item.unit.unit_id}/edit`)}>
                                                            编辑关卡
                                                        </Button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </GlassCard>
                        );
                    })}
                </div>
            )}
        </AdminIndexShell>
    );
}
