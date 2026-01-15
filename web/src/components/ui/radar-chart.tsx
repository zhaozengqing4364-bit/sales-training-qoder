"use client";

import { PolarAngleAxis, PolarGrid, Radar, RadarChart as RechartsRadar, ResponsiveContainer } from "recharts";

interface RadarChartProps {
    data: { subject: string; A: number; fullMark: number }[];
    color?: string;
    className?: string;
}

export function RadarChart({ data, color = "#8884d8", className }: RadarChartProps) {
    return (
        <div className={className || "w-full h-[300px]"}>
            <ResponsiveContainer width="100%" height="100%">
                <RechartsRadar outerRadius="80%" data={data}>
                    <PolarGrid stroke="#e5e7eb" />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#6b7280', fontSize: 12 }} />
                    <Radar
                        name="Score"
                        dataKey="A"
                        stroke={color}
                        fill={color}
                        fillOpacity={0.5}
                    />
                </RechartsRadar>
            </ResponsiveContainer>
        </div>
    );
}
