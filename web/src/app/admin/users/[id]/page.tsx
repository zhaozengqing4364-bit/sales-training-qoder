"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import {
    UserDetailStats,
    UserSessionsResponse,
    UserProgressResponse,
    UserSessionItem,
} from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import {
    ArrowLeft,
    User,
    Calendar,
    Clock,
    Target,
    TrendingUp,
    TrendingDown,
    Award,
    BarChart3,
    Activity,
    RefreshCw,
} from "lucide-react";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    BarChart,
    Bar,
    Legend,
} from "recharts";

type TimeRange = "7d" | "30d" | "90d" | "all_time";

export default function UserDetailPage() {
    const params = useParams();
    const router = useRouter();
    const userId = params.id as string;

    // State
    const [timeRange, setTimeRange] = useState<TimeRange>("30d");
    const [stats, setStats] = useState<UserDetailStats | null>(null);
    const [sessions, setSessions] = useState<UserSessionsResponse | null>(null);
    const [progress, setProgress] = useState<UserProgressResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [sessionsPage, setSessionsPage] = useState(1);

    // Load all data
    const loadData = useCallback(async () => {
        setIsLoading(true);
        try {
            const [statsData, sessionsData, progressData] = await Promise.all([
                api.admin.getUserStats(userId, { time_range: timeRange }),
                api.admin.getUserSessions(userId, { page: 1, page_size: 10 }),
                api.admin.getUserProgress(userId, { time_range: timeRange }),
            ]);

            setStats(statsData);
            setSessions(sessionsData);
            setProgress(progressData);
            setSessionsPage(1);
        } catch (err) {
            console.error("Failed to load user data:", err);
        } finally {
            setIsLoading(false);
        }
    }, [userId, timeRange]);

    // Load more sessions
    const loadMoreSessions = async () => {
        if (!sessions?.has_more) return;
        
        try {
            const nextPage = sessionsPage + 1;
            const data = await api.admin.getUserSessions(userId, {
                page: nextPage,
                page_size: 10,
            });
            
            setSessions({
                ...data,
                items: [...(sessions?.items || []), ...data.items],
            });
            setSessionsPage(nextPage);
        } catch (err) {
            console.error("Failed to load more sessions:", err);
        }
    };

    useEffect(() => {
        loadData();
    }, [loadData]);

    // Time range options
    const timeRangeOptions: { value: TimeRange; label: string }[] = [
        { value: "7d", label: "7天" },
        { value: "30d", label: "30天" },
        { value: "90d", label: "90天" },
        { value: "all_time", label: "全部" },
    ];

    // Format date
    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return "-";
        return new Date(dateStr).toLocaleString("zh-CN", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    // Get status badge color
    const getStatusColor = (status: string) => {
        switch (status) {
            case "completed":
                return "bg-green-50 text-green-600";
            case "in_progress":
                return "bg-blue-50 text-blue-600";
            case "scoring":
                return "bg-amber-50 text-amber-600";
            default:
                return "bg-slate-50 text-slate-600";
        }
    };

    // Get score color
    const getScoreColor = (score: number | null) => {
        if (score === null) return "text-slate-400";
        if (score >= 90) return "text-green-600";
        if (score >= 70) return "text-blue-600";
        if (score >= 50) return "text-amber-600";
        return "text-red-600";
    };

    if (isLoading) {
        return (
            <div className="space-y-8 animate-in fade-in">
                <div className="flex items-center gap-4">
                    <div className="h-10 w-10 bg-slate-200 rounded-full animate-pulse" />
                    <div className="h-8 w-48 bg-slate-200 rounded-lg animate-pulse" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    {[1, 2, 3, 4].map((i) => (
                        <GlassCard key={i} className="p-6 h-32 animate-pulse" />
                    ))}
                </div>
            </div>
        );
    }

    if (!stats) {
        return (
            <div className="flex flex-col items-center justify-center py-20">
                <p className="text-slate-500">用户不存在或加载失败</p>
                <Button onClick={() => router.back()} className="mt-4">
                    返回
                </Button>
            </div>
        );
    }

    const { user, statistics } = stats;

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => router.back()}
                        className="rounded-full"
                    >
                        <ArrowLeft className="w-5 h-5" />
                    </Button>
                    <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-lg">
                            {(user.username || user.email || "U").charAt(0).toUpperCase()}
                        </div>
                        <div>
                            <h1 className="text-2xl font-black text-slate-900">
                                {user.username || user.email || "未知用户"}
                            </h1>
                            <p className="text-slate-500 text-sm">
                                {user.department || "未设置部门"} · {user.email}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="flex flex-wrap gap-3">
                    {/* Time Range Filter */}
                    <div className="flex bg-slate-100 rounded-full p-1">
                        {timeRangeOptions.map((option) => (
                            <button
                                key={option.value}
                                onClick={() => setTimeRange(option.value)}
                                className={`px-4 py-2 text-sm font-medium rounded-full transition-all ${
                                    timeRange === option.value
                                        ? "bg-white text-slate-900 shadow-sm"
                                        : "text-slate-500 hover:text-slate-700"
                                }`}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                    <Button
                        variant="outline"
                        onClick={loadData}
                        className="rounded-full"
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        刷新
                    </Button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <GlassCard className="p-5">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center">
                            <Target className="w-5 h-5 text-blue-600" />
                        </div>
                        <div>
                            <p className="text-sm text-slate-500">练习次数</p>
                            <p className="text-2xl font-black text-slate-900">
                                {statistics.total_sessions}
                            </p>
                        </div>
                    </div>
                    <p className="text-xs text-slate-400 mt-2">
                        完成 {statistics.completed_sessions} 次 ({statistics.completion_rate}%)
                    </p>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center">
                            <Award className="w-5 h-5 text-green-600" />
                        </div>
                        <div>
                            <p className="text-sm text-slate-500">平均分</p>
                            <p className={`text-2xl font-black ${getScoreColor(statistics.average_score)}`}>
                                {statistics.average_score}
                            </p>
                        </div>
                    </div>
                    <p className="text-xs text-slate-400 mt-2">
                        最高 {statistics.best_score} / 最低 {statistics.worst_score}
                    </p>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-purple-50 flex items-center justify-center">
                            <Clock className="w-5 h-5 text-purple-600" />
                        </div>
                        <div>
                            <p className="text-sm text-slate-500">练习时长</p>
                            <p className="text-2xl font-black text-slate-900">
                                {Math.round(statistics.total_duration_minutes)} 分钟
                            </p>
                        </div>
                    </div>
                    <p className="text-xs text-slate-400 mt-2">
                        最近: {formatDate(statistics.last_practice)}
                    </p>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center">
                            {progress && progress.improvement_rate >= 0 ? (
                                <TrendingUp className="w-5 h-5 text-amber-600" />
                            ) : (
                                <TrendingDown className="w-5 h-5 text-red-600" />
                            )}
                        </div>
                        <div>
                            <p className="text-sm text-slate-500">进步率</p>
                            <p className={`text-2xl font-black ${
                                progress && progress.improvement_rate >= 0
                                    ? "text-green-600"
                                    : "text-red-600"
                            }`}>
                                {progress ? `${progress.improvement_rate > 0 ? "+" : ""}${progress.improvement_rate}%` : "-"}
                            </p>
                        </div>
                    </div>
                    <p className="text-xs text-slate-400 mt-2">
                        对比首周与最近一周
                    </p>
                </GlassCard>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Progress Chart */}
                <GlassCard className="p-6">
                    <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                        <Activity className="w-5 h-5 text-blue-600" />
                        分数趋势
                    </h3>
                    {progress && progress.trend_data.length > 0 ? (
                        <ResponsiveContainer width="100%" height={280}>
                            <LineChart data={progress.trend_data}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                <XAxis
                                    dataKey="date"
                                    tick={{ fontSize: 12, fill: "#64748b" }}
                                    tickFormatter={(v) => v.slice(5)}
                                />
                                <YAxis
                                    domain={[0, 100]}
                                    tick={{ fontSize: 12, fill: "#64748b" }}
                                />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: "white",
                                        border: "none",
                                        borderRadius: "12px",
                                        boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
                                    }}
                                />
                                <Legend />
                                <Line
                                    type="monotone"
                                    dataKey="average_score"
                                    name="综合分"
                                    stroke="#3b82f6"
                                    strokeWidth={2}
                                    dot={{ fill: "#3b82f6", r: 4 }}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="logic_score"
                                    name="逻辑分"
                                    stroke="#10b981"
                                    strokeWidth={1.5}
                                    strokeDasharray="5 5"
                                />
                                <Line
                                    type="monotone"
                                    dataKey="accuracy_score"
                                    name="准确分"
                                    stroke="#f59e0b"
                                    strokeWidth={1.5}
                                    strokeDasharray="5 5"
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-64 flex items-center justify-center text-slate-400">
                            暂无数据
                        </div>
                    )}
                </GlassCard>

                {/* Usage Stats */}
                <GlassCard className="p-6">
                    <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                        <BarChart3 className="w-5 h-5 text-purple-600" />
                        使用统计
                    </h3>
                    <div className="space-y-6">
                        {/* Agent Usage */}
                        <div>
                            <p className="text-sm font-medium text-slate-600 mb-3">Agent 使用</p>
                            {stats.agent_usage.length > 0 ? (
                                <div className="space-y-2">
                                    {stats.agent_usage.map((item, idx) => (
                                        <div
                                            key={idx}
                                            className="flex items-center justify-between p-3 bg-slate-50 rounded-xl"
                                        >
                                            <span className="font-medium text-slate-700">{item.name}</span>
                                            <span className="text-sm text-slate-500">{item.count} 次</span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-slate-400">暂无数据</p>
                            )}
                        </div>

                        {/* Persona Usage */}
                        <div>
                            <p className="text-sm font-medium text-slate-600 mb-3">Persona 使用</p>
                            {stats.persona_usage.length > 0 ? (
                                <div className="space-y-2">
                                    {stats.persona_usage.map((item, idx) => (
                                        <div
                                            key={idx}
                                            className="flex items-center justify-between p-3 bg-slate-50 rounded-xl"
                                        >
                                            <span className="font-medium text-slate-700">{item.name}</span>
                                            <span className="text-sm text-slate-500">{item.count} 次</span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-slate-400">暂无数据</p>
                            )}
                        </div>
                    </div>
                </GlassCard>
            </div>

            {/* Sessions Table */}
            <GlassCard className="p-6">
                <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-blue-600" />
                    练习记录
                </h3>

                {sessions && sessions.items.length > 0 ? (
                    <>
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-slate-100">
                                        <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">
                                            时间
                                        </th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">
                                            场景
                                        </th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">
                                            Agent / Persona
                                        </th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">
                                            状态
                                        </th>
                                        <th className="text-right py-3 px-4 text-sm font-medium text-slate-500">
                                            时长
                                        </th>
                                        <th className="text-right py-3 px-4 text-sm font-medium text-slate-500">
                                            得分
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {sessions.items.map((session) => (
                                        <tr
                                            key={session.session_id}
                                            className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors"
                                        >
                                            <td className="py-3 px-4 text-sm text-slate-700">
                                                {formatDate(session.start_time)}
                                            </td>
                                            <td className="py-3 px-4">
                                                <span className="text-sm font-medium text-slate-700">
                                                    {session.scenario_name || session.scenario_type || "-"}
                                                </span>
                                            </td>
                                            <td className="py-3 px-4 text-sm text-slate-600">
                                                {session.agent_name || "-"}
                                                {session.persona_name && ` / ${session.persona_name}`}
                                            </td>
                                            <td className="py-3 px-4">
                                                <span
                                                    className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${getStatusColor(
                                                        session.status
                                                    )}`}
                                                >
                                                    {session.status === "completed"
                                                        ? "已完成"
                                                        : session.status === "in_progress"
                                                        ? "进行中"
                                                        : session.status}
                                                </span>
                                            </td>
                                            <td className="py-3 px-4 text-sm text-slate-600 text-right">
                                                {session.duration_minutes.toFixed(1)} 分钟
                                            </td>
                                            <td className="py-3 px-4 text-right">
                                                <span
                                                    className={`text-lg font-bold ${getScoreColor(
                                                        session.scores.overall
                                                    )}`}
                                                >
                                                    {session.scores.overall ?? "-"}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        {sessions.has_more && (
                            <div className="flex justify-center mt-4">
                                <Button
                                    variant="outline"
                                    onClick={loadMoreSessions}
                                    className="rounded-full"
                                >
                                    加载更多
                                </Button>
                            </div>
                        )}
                    </>
                ) : (
                    <div className="py-12 text-center text-slate-400">
                        暂无练习记录
                    </div>
                )}
            </GlassCard>
        </div>
    );
}
