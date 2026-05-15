"use client";

import Link from "next/link";
import { AnalyticsAgents } from "@/lib/api/types";
import { ArrowRight } from "lucide-react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
} from "recharts";

interface AgentRankingChartProps {
    data: AnalyticsAgents;
}

const COLORS = ["#6366f1", "#8b5cf6", "#a855f7", "#c084fc", "#d8b4fe"];

export function AgentRankingChart({ data }: AgentRankingChartProps) {
    const { agent_stats, persona_stats } = data;

    // Combine and sort by usage count
    const combinedData = [
        ...agent_stats.map((a) => ({
            name: a.agent_name,
            count: a.usage_count,
            score: a.average_score,
            type: "Agent",
        })),
        ...persona_stats.map((p) => ({
            name: p.persona_name,
            count: p.usage_count,
            score: p.average_score,
            type: "Persona",
        })),
    ]
        .sort((a, b) => b.count - a.count)
        .slice(0, 8);

    if (combinedData.length === 0) {
        return (
            <div className="h-72 flex items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-6 text-center">
                <div>
                    <p className="text-sm font-semibold text-slate-900">暂无 Agent 使用数据</p>
                    <p className="mt-2 text-sm text-slate-500">
                        当前范围还没有已完成且可评估的训练使用到智能体或客户角色；完成训练并生成稳定证据后，这里会显示使用次数与平均分。
                    </p>
                    <Link
                        href="/admin/records"
                        className="mt-4 inline-flex items-center gap-2 rounded-full bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-blue-700"
                    >
                        查看训练记录
                        <ArrowRight className="w-4 h-4" />
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="h-72">
            <ResponsiveContainer
                width="100%"
                height="100%"
                initialDimension={{ width: 320, height: 288 }}
            >
                <BarChart
                    data={combinedData}
                    layout="vertical"
                    margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                    <XAxis
                        type="number"
                        tick={{ fontSize: 12, fill: "#64748b" }}
                        axisLine={{ stroke: "#e2e8f0" }}
                    />
                    <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fontSize: 12, fill: "#64748b" }}
                        axisLine={{ stroke: "#e2e8f0" }}
                        width={100}
                        tickFormatter={(value) => (value.length > 10 ? value.slice(0, 10) + "..." : value)}
                    />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: "rgba(255, 255, 255, 0.95)",
                            border: "none",
                            borderRadius: "12px",
                            boxShadow: "0 4px 20px rgba(0, 0, 0, 0.1)",
                            padding: "12px 16px",
                        }}
                        formatter={(value, name, props) => {
                            const item = props?.payload;
                            return [
                                <div key="tooltip" className="space-y-1">
                                    <p>使用次数: {value as number ?? 0}</p>
                                    <p>平均分: {item?.score?.toFixed(1) ?? 'N/A'}</p>
                                    <p className="text-xs text-slate-500">类型: {item?.type}</p>
                                </div>,
                                "",
                            ];
                        }}
                        labelFormatter={(label) => <span className="font-bold">{label}</span>}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                        {combinedData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}
