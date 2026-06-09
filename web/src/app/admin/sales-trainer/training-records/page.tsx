"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import {
    formatAdminRecordStatus,
    formatTrainingTaskDisplay,
    formatUnitTypeLabel,
} from "@/lib/sales-trainer/admin-display";
import type { SalesTrainerTrainingRecord } from "@/lib/api/types";

function formatLearner(record: SalesTrainerTrainingRecord): string {
    const primary = record.user_name || record.user_email || record.user_id;
    const secondary = record.user_department || (
        record.user_email && record.user_email !== primary ? record.user_email : null
    );
    return secondary ? `${primary} · ${secondary}` : primary;
}

function formatScore(record: SalesTrainerTrainingRecord): string {
    if (record.score == null) {
        return "--";
    }
    if (record.max_score == null) {
        return String(record.score);
    }
    return `${record.score} / ${record.max_score}`;
}

export default function SalesTrainerTrainingRecordsPage() {
    const pathname = usePathname();
    const router = useRouter();
    const [items, setItems] = useState<SalesTrainerTrainingRecord[]>([]);
    const [userId, setUserId] = useState("");
    const [unitId, setUnitId] = useState("");
    const [materialVersionId, setMaterialVersionId] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    async function loadRecords(filters?: {
        user_id?: string;
        unit_id?: string;
        material_version_id?: string;
    }) {
        setIsLoading(true);
        setError(null);
        try {
            const result = await api.admin.salesTrainer.listTrainingRecords({
                ...filters,
                limit: 100,
            });
            setItems(result.items);
        } catch (loadError) {
            setItems([]);
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }

    useEffect(() => {
        void loadRecords();
    }, []);

    function applyFilters(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        void loadRecords({
            user_id: userId.trim() || undefined,
            unit_id: unitId.trim() || undefined,
            material_version_id: materialVersionId.trim() || undefined,
        });
    }

    function resetFilters() {
        setUserId("");
        setUnitId("");
        setMaterialVersionId("");
        void loadRecords();
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="学员训练记录"
                    description="统一查看材料版本、录音、转写、评分、做题和操作记录，替代单独追录音与评分结果。"
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
                />
            )}
        >
            <GlassCard className="p-6">
                <form className="grid gap-4 md:grid-cols-[1fr_1fr_1fr_auto_auto]" onSubmit={applyFilters}>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="records-user-id">学员编号</label>
                        <Input id="records-user-id" value={userId} onChange={(event) => setUserId(event.target.value)} />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="records-unit-id">训练任务编号</label>
                        <Input id="records-unit-id" value={unitId} onChange={(event) => setUnitId(event.target.value)} />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="records-material-version-id">材料版本编号</label>
                        <Input id="records-material-version-id" value={materialVersionId} onChange={(event) => setMaterialVersionId(event.target.value)} />
                    </div>
                    <div className="flex items-end">
                        <Button type="submit" className="w-full rounded-full bg-slate-900 text-white">查询</Button>
                    </div>
                    <div className="flex items-end">
                        <Button type="button" variant="outline" className="w-full rounded-full" onClick={resetFilters}>重置</Button>
                    </div>
                </form>
            </GlassCard>

            <GlassCard className="overflow-hidden p-0">
                {error ? (
                    <div className="border-b border-red-100 bg-red-50 px-6 py-4 text-sm text-red-700">
                        {error}
                    </div>
                ) : null}
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-slate-100 text-left text-slate-500">
                            <th className="px-6 py-4">学员</th>
                            <th className="px-6 py-4">任务</th>
                            <th className="px-6 py-4">类型</th>
                            <th className="px-6 py-4">材料版本</th>
                            <th className="px-6 py-4">得分</th>
                            <th className="px-6 py-4">状态</th>
                            <th className="px-6 py-4">提交时间</th>
                            <th className="px-6 py-4">操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        {isLoading ? (
                            <tr><td colSpan={8} className="px-6 py-10 text-center text-slate-500">正在加载训练记录...</td></tr>
                        ) : items.length === 0 ? (
                            <tr><td colSpan={8} className="px-6 py-10 text-center text-slate-500">暂无训练记录</td></tr>
                        ) : items.map((item) => {
                            const snapshot = item.material_snapshot;
                            const taskDisplay = formatTrainingTaskDisplay(item.unit_name, item.unit_id);
                            const snapshotItems = Array.isArray(snapshot?.items) ? snapshot.items : [];
                            const firstMaterial = snapshotItems[0] as { current_version?: { version_label?: string } } | undefined;
                            return (
                                <tr key={`${item.record_type}-${item.record_id}`} className="border-b border-slate-100 last:border-b-0">
                                    <td className="px-6 py-4">
                                        <p className="font-medium text-slate-900">{formatLearner(item)}</p>
                                        <p className="mt-1 text-xs text-slate-400">{item.user_id}</p>
                                    </td>
                                    <td className="px-6 py-4">
                                        <p>{taskDisplay.title}</p>
                                        {taskDisplay.detail ? (
                                            <p className="mt-1 text-xs text-slate-400">{taskDisplay.detail}</p>
                                        ) : null}
                                    </td>
                                    <td className="px-6 py-4">{formatUnitTypeLabel(item.unit_type)}</td>
                                    <td className="px-6 py-4">{firstMaterial?.current_version?.version_label ?? "--"}</td>
                                    <td className="px-6 py-4">{formatScore(item)}</td>
                                    <td className="px-6 py-4"><Badge className="bg-slate-100 text-slate-700">{formatAdminRecordStatus(item.status)}</Badge></td>
                                    <td className="px-6 py-4">{item.submitted_at ? new Date(item.submitted_at).toLocaleString() : "--"}</td>
                                    <td className="px-6 py-4">
                                        {item.record_type === "audio_submission" ? (
                                            <Button variant="outline" size="sm" onClick={() => router.push(`/admin/sales-trainer/audio-submissions/${item.record_id}`)}>
                                                查看详情
                                            </Button>
                                        ) : (
                                            <Button variant="outline" size="sm" onClick={() => router.push(`/admin/sales-trainer/quiz-attempts/${item.record_id}`)}>
                                                查看详情
                                            </Button>
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </GlassCard>
        </AdminIndexShell>
    );
}
