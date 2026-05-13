"use client";

import {
    CartesianGrid,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import type { CurriculumAnalyticsScoreTrendPoint } from "@/lib/api/types";

interface CurriculumScoreTrendProps {
    data: CurriculumAnalyticsScoreTrendPoint[];
}

export function CurriculumScoreTrend({ data }: CurriculumScoreTrendProps) {
    if (data.length === 0) {
        return (
            <div className="flex h-72 items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-6 text-center text-sm text-slate-500">
                暂无课程分数趋势
            </div>
        );
    }

    const formattedData = data.map((point) => ({
        ...point,
        date: new Date(point.date).toLocaleDateString("zh-CN", { month: "short", day: "numeric" }),
    }));

    return (
        <div className="h-72" aria-label="课程分数趋势图">
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={formattedData} margin={{ top: 12, right: 20, left: 0, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 12, fill: "#64748b" }} axisLine={{ stroke: "#e2e8f0" }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: "#64748b" }} axisLine={{ stroke: "#e2e8f0" }} />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: "rgba(255,255,255,0.96)",
                            border: "1px solid #e2e8f0",
                            borderRadius: "14px",
                            boxShadow: "0 16px 40px rgba(15,23,42,0.12)",
                        }}
                        formatter={(value, name) => [
                            Number(value).toFixed(1),
                            name === "average_score" ? "平均分" : String(name),
                        ]}
                    />
                    <Line
                        type="monotone"
                        dataKey="average_score"
                        stroke="#2563eb"
                        strokeWidth={3}
                        dot={{ fill: "#2563eb", strokeWidth: 0, r: 4 }}
                        activeDot={{ r: 6, strokeWidth: 0 }}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
