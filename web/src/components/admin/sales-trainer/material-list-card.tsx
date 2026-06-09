"use client";

import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import type { SalesTrainerMaterial } from "@/lib/api/types";
import { formatAdminStatus } from "@/lib/sales-trainer/admin-display";

interface MaterialListCardProps {
    readonly isLoading: boolean;
    readonly items: readonly SalesTrainerMaterial[];
    readonly onSelect: (materialId: string) => void;
}

export function MaterialListCard({
    isLoading,
    items,
    onSelect,
}: MaterialListCardProps) {
    return (
        <GlassCard className="overflow-hidden p-0">
            <div className="border-b border-slate-100 px-6 py-4">
                <h2 className="text-lg font-bold text-slate-900">材料列表</h2>
            </div>
            {isLoading ? (
                <div className="px-6 py-10 text-center text-sm text-slate-500">正在加载材料...</div>
            ) : items.length === 0 ? (
                <div className="px-6 py-10 text-center text-sm text-slate-500">暂无训练材料</div>
            ) : (
                <div className="divide-y divide-slate-100">
                    {items.map((item) => (
                        <button
                            key={item.material_id}
                            type="button"
                            onClick={() => onSelect(item.material_id)}
                            className="w-full px-6 py-4 text-left hover:bg-slate-50"
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <p className="font-medium text-slate-900">{item.name}</p>
                                    <p className="mt-1 text-xs text-slate-500">{item.material_key}</p>
                                </div>
                                <Badge className="bg-slate-100 text-slate-700">{formatAdminStatus(item.status)}</Badge>
                            </div>
                            <p className="mt-2 text-xs text-slate-500">
                                最新版：{item.current_version?.version_label ?? "未发布"}
                            </p>
                        </button>
                    ))}
                </div>
            )}
        </GlassCard>
    );
}
