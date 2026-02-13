"use client";

import { ScoreDistribution } from "@/lib/api/types";
import {
    PieChart,
    Pie,
    Cell,
    ResponsiveContainer,
    Legend,
    Tooltip,
} from "recharts";

interface ScoreDistributionChartProps {
    data: ScoreDistribution;
}

const COLORS = ["#10b981", "#3b82f6", "#f59e0b", "#ef4444"];
const LABELS: Record<keyof ScoreDistribution, string> = {
    excellent: "优秀 (90+)",
    good: "良好 (70-89)",
    fair: "及格 (50-69)",
    poor: "待提升 (<50)",
};

export function ScoreDistributionChart({ data }: ScoreDistributionChartProps) {
    const chartData = [
        { name: LABELS.excellent, value: data.excellent, key: "excellent" },
        { name: LABELS.good, value: data.good, key: "good" },
        { name: LABELS.fair, value: data.fair, key: "fair" },
        { name: LABELS.poor, value: data.poor, key: "poor" },
    ].filter((item) => item.value > 0);

    const total = data.excellent + data.good + data.fair + data.poor;

    if (total === 0) {
        return (
            <div className="h-72 flex items-center justify-center text-slate-400">
                暂无分数数据
            </div>
        );
    }

    return (
        <div className="h-72 relative">
            <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                    <Pie
                        data={chartData}
                        cx="50%"
                        cy="45%"
                        innerRadius={50}
                        outerRadius={80}
                        paddingAngle={2}
                        dataKey="value"
                        labelLine={false}
                    >
                        {chartData.map((entry, index) => (
                            <Cell
                                key={entry.key}
                                fill={COLORS[["excellent", "good", "fair", "poor"].indexOf(entry.key)]}
                            />
                        ))}
                    </Pie>
                    <Tooltip
                        contentStyle={{
                            backgroundColor: "rgba(255, 255, 255, 0.95)",
                            border: "none",
                            borderRadius: "12px",
                            boxShadow: "0 4px 20px rgba(0, 0, 0, 0.1)",
                            padding: "12px 16px",
                        }}
                        formatter={(value) => {
                            const numValue = value as number ?? 0;
                            return [
                                `${numValue} 次 (${((numValue / total) * 100).toFixed(1)}%)`,
                                "数量",
                            ];
                        }}
                    />
                    <Legend
                        layout="horizontal"
                        verticalAlign="bottom"
                        align="center"
                        wrapperStyle={{ paddingTop: "20px" }}
                        formatter={(value: string) => (
                            <span className="text-sm text-slate-600">{value}</span>
                        )}
                    />
                </PieChart>
            </ResponsiveContainer>

            {/* Center total */}
            <div className="absolute top-[45%] left-1/2 -translate-x-1/2 -translate-y-1/2 text-center">
                <p className="text-2xl font-black text-slate-900">{total}</p>
                <p className="text-xs text-slate-500">总计</p>
            </div>
        </div>
    );
}
