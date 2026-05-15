"use client";

import Link from "next/link";
import { TrendDataPoint } from "@/lib/api/types";
import { ArrowRight } from "lucide-react";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
} from "recharts";

interface TrendsChartProps {
    data: TrendDataPoint[];
}

export function TrendsChart({ data }: TrendsChartProps) {
    if (!data || data.length === 0) {
        return (
            <div className="h-72 flex items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-6 text-center">
                <div>
                    <p className="text-sm font-semibold text-slate-900">暂无趋势数据</p>
                    <p className="mt-2 text-sm text-slate-500">
                        当前时间范围还没有可评估训练快照；完成一次有足够证据的训练后，这里会显示练习次数、平均分和活跃用户走势。
                    </p>
                    <Link
                        href="/training"
                        className="mt-4 inline-flex items-center gap-2 rounded-full bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-blue-700"
                    >
                        去训练大厅
                        <ArrowRight className="w-4 h-4" />
                    </Link>
                </div>
            </div>
        );
    }

    // Format date for display
    const formattedData = data.map((item) => ({
        ...item,
        date: new Date(item.date).toLocaleDateString("zh-CN", {
            month: "short",
            day: "numeric",
        }),
    }));

    return (
        <div className="h-72">
            <ResponsiveContainer
                width="100%"
                height="100%"
                initialDimension={{ width: 320, height: 288 }}
            >
                <LineChart
                    data={formattedData}
                    margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                        dataKey="date"
                        tick={{ fontSize: 12, fill: "#64748b" }}
                        axisLine={{ stroke: "#e2e8f0" }}
                    />
                    <YAxis
                        yAxisId="left"
                        tick={{ fontSize: 12, fill: "#64748b" }}
                        axisLine={{ stroke: "#e2e8f0" }}
                        tickFormatter={(value) => value.toLocaleString()}
                    />
                    <YAxis
                        yAxisId="right"
                        orientation="right"
                        domain={[0, 100]}
                        tick={{ fontSize: 12, fill: "#64748b" }}
                        axisLine={{ stroke: "#e2e8f0" }}
                    />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: "rgba(255, 255, 255, 0.95)",
                            border: "none",
                            borderRadius: "12px",
                            boxShadow: "0 4px 20px rgba(0, 0, 0, 0.1)",
                            padding: "12px 16px",
                        }}
                        labelStyle={{ fontWeight: "bold", marginBottom: "8px" }}
                        formatter={(value, name) => {
                            const numValue = value as number ?? 0;
                            const labels: Record<string, string> = {
                                sessions_count: "练习次数",
                                average_score: "平均分",
                                active_users: "活跃用户",
                            };
                            return [
                                name === "average_score" ? numValue.toFixed(1) : numValue.toLocaleString(),
                                labels[name as string] || name,
                            ];
                        }}
                    />
                    <Legend
                        formatter={(value: string) => {
                            const labels: Record<string, string> = {
                                sessions_count: "练习次数",
                                average_score: "平均分",
                                active_users: "活跃用户",
                            };
                            return labels[value] || value;
                        }}
                        wrapperStyle={{ paddingTop: "20px" }}
                    />
                    <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="sessions_count"
                        stroke="#6366f1"
                        strokeWidth={2}
                        dot={{ fill: "#6366f1", strokeWidth: 0, r: 3 }}
                        activeDot={{ r: 5, strokeWidth: 0 }}
                    />
                    <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="average_score"
                        stroke="#10b981"
                        strokeWidth={2}
                        dot={{ fill: "#10b981", strokeWidth: 0, r: 3 }}
                        activeDot={{ r: 5, strokeWidth: 0 }}
                    />
                    <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="active_users"
                        stroke="#f59e0b"
                        strokeWidth={2}
                        dot={{ fill: "#f59e0b", strokeWidth: 0, r: 3 }}
                        activeDot={{ r: 5, strokeWidth: 0 }}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
