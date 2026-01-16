"use client";

import { AnalyticsAgents } from "@/lib/api/types";
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
            <div className="h-72 flex items-center justify-center text-slate-400">
                暂无 Agent 使用数据
            </div>
        );
    }

    return (
        <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
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
                        formatter={(value: number, name: string, props: any) => {
                            const item = props.payload;
                            return [
                                <div key="tooltip" className="space-y-1">
                                    <p>使用次数: {value}</p>
                                    <p>平均分: {item.score.toFixed(1)}</p>
                                    <p className="text-xs text-slate-500">类型: {item.type}</p>
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
