"use client";

import type { CurriculumAnalyticsHeatmapCell } from "@/lib/api/types";
import { cn } from "@/lib/utils";

interface CurriculumHeatmapProps {
    data: CurriculumAnalyticsHeatmapCell[];
}

function getCellTone(score: number): string {
    if (score >= 85) return "bg-emerald-100 text-emerald-900 border-emerald-200";
    if (score >= 70) return "bg-blue-100 text-blue-900 border-blue-200";
    if (score >= 60) return "bg-amber-100 text-amber-900 border-amber-200";
    return "bg-red-100 text-red-900 border-red-200";
}

export function CurriculumHeatmap({ data }: CurriculumHeatmapProps) {
    if (data.length === 0) {
        return (
            <div className="flex min-h-72 items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-6 text-center text-sm text-slate-500">
                暂无课程维度热图
            </div>
        );
    }

    return (
        <div className="space-y-4" aria-label="课程维度热图">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {data.map((cell) => (
                    <div
                        key={`${cell.template_id}-${cell.dimension}`}
                        className={cn(
                            "rounded-2xl border p-4 shadow-sm transition-colors duration-200",
                            getCellTone(cell.average_score),
                        )}
                    >
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <p className="text-sm font-bold">{cell.dimension}</p>
                                <p className="mt-1 text-xs opacity-80">{cell.template_name}</p>
                            </div>
                            <span className="text-2xl font-black">{cell.average_score.toFixed(1)}</span>
                        </div>
                        <p className="mt-3 text-xs opacity-80">样本 {cell.sample_count} 次</p>
                    </div>
                ))}
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
                <span className="font-semibold text-slate-700">图例</span>
                <span className="rounded-full bg-red-100 px-3 py-1 text-red-800">&lt;60 风险</span>
                <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-800">60-69 关注</span>
                <span className="rounded-full bg-blue-100 px-3 py-1 text-blue-800">70-84 稳定</span>
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-emerald-800">85+ 优秀</span>
            </div>
        </div>
    );
}
