"use client";

import { AnalyticsOverview } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { TrendingUp, TrendingDown, Users, Activity, Award, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

interface MetricsCardsProps {
    data: AnalyticsOverview;
}

interface MetricCardProps {
    title: string;
    value: string | number;
    subtitle?: string;
    growthRate?: number;
    icon: React.ReactNode;
    iconBgColor: string;
}

function MetricCard({ title, value, subtitle, growthRate, icon, iconBgColor }: MetricCardProps) {
    const isPositive = growthRate !== undefined && growthRate >= 0;

    return (
        <GlassCard className="p-6 relative overflow-hidden">
            {/* Icon */}
            <div className={cn("w-12 h-12 rounded-2xl flex items-center justify-center mb-4", iconBgColor)}>
                {icon}
            </div>

            {/* Title */}
            <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                {title}
            </p>

            {/* Value */}
            <p className="text-3xl font-black text-slate-900 mb-2">
                {value}
            </p>

            {/* Growth Rate or Subtitle */}
            {growthRate !== undefined ? (
                <div
                    className={cn(
                        "flex items-center gap-1 text-sm font-medium",
                        isPositive ? "text-emerald-600" : "text-red-500"
                    )}
                >
                    {isPositive ? (
                        <TrendingUp className="w-4 h-4" />
                    ) : (
                        <TrendingDown className="w-4 h-4" />
                    )}
                    <span>{Math.abs(growthRate).toFixed(1)}% 较上期</span>
                </div>
            ) : subtitle ? (
                <p className="text-sm text-slate-500">{subtitle}</p>
            ) : null}

            {/* Decorative blur */}
            <div className={cn("absolute -right-6 -bottom-6 w-24 h-24 rounded-full blur-2xl opacity-30", iconBgColor)} />
        </GlassCard>
    );
}

export function MetricsCards({ data }: MetricsCardsProps) {
    const formatNumber = (num: number): string => {
        if (num >= 10000) {
            return (num / 10000).toFixed(1) + "万";
        }
        if (num >= 1000) {
            return (num / 1000).toFixed(1) + "K";
        }
        return num.toLocaleString();
    };

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Total Users */}
            <MetricCard
                title="总用户数"
                value={formatNumber(data.total_users)}
                growthRate={data.growth.users_rate}
                icon={<Users className="w-6 h-6 text-blue-600" />}
                iconBgColor="bg-blue-50"
            />

            {/* Active Users Today */}
            <MetricCard
                title="今日活跃"
                value={formatNumber(data.active_users_today)}
                subtitle={`本周 ${data.active_users_week} 人活跃`}
                icon={<Activity className="w-6 h-6 text-emerald-600" />}
                iconBgColor="bg-emerald-50"
            />

            {/* Total Sessions */}
            <MetricCard
                title="练习次数"
                value={formatNumber(data.total_sessions)}
                growthRate={data.growth.sessions_rate}
                icon={<Clock className="w-6 h-6 text-violet-600" />}
                iconBgColor="bg-violet-50"
            />

            {/* Average Score */}
            <MetricCard
                title="平均分"
                value={data.average_score.toFixed(1)}
                growthRate={data.growth.score_rate}
                icon={<Award className="w-6 h-6 text-amber-600" />}
                iconBgColor="bg-amber-50"
            />
        </div>
    );
}
