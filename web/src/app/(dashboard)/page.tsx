"use client";

import { useState, useEffect } from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DashboardSkeleton } from "@/components/dashboard-skeleton";
import { SwipeableItem } from "@/components/ui/swipeable-item";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";
import {
    TrendingUp, Filter, MoreHorizontal,
    Calendar, CheckCircle2, Zap, BarChart3, ArrowRight, Headphones
} from "lucide-react";
import Link from "next/link";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/glass-modal";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { DashboardStats, SessionItem, Recommendation } from "@/lib/api/types";

// Helper Functions
const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}分 ${s}秒`;
};

const formatTimeAgo = (isoString: string) => {
    const date = new Date(isoString);
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    if (diffInSeconds < 60) return "刚刚";
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}分钟前`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}小时前`;
    return "昨天"; // Simplified for mock
};

export default function HomePage() {
    const router = useRouter();
    // State for modals
    const [isWeeklyStatsOpen, setIsWeeklyStatsOpen] = useState(false);
    const [isFilterOpen, setIsFilterOpen] = useState(false);
    
    // Data State
    const [isLoading, setIsLoading] = useState(true);
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
    const [historyItems, setHistoryItems] = useState<SessionItem[]>([]);

    const handleDeleteHistory = (id: string) => {
        setHistoryItems(prev => prev.filter(item => item.id !== id));
    };

    // Load Data from API
    useEffect(() => {
        const loadDashboardData = async () => {
            try {
                setIsLoading(true);
                // Parallel fetching for better performance
                const [statsData, recData, historyData] = await Promise.all([
                    api.dashboard.getStats(),
                    api.dashboard.getRecommendation(),
                    api.dashboard.getHistory()
                ]);

                setStats(statsData);
                setRecommendation(recData);
                setHistoryItems(historyData);
            } catch (error) {
                console.error("Failed to load dashboard data:", error);
                // In a real app, you might show a toast error here
            } finally {
                setIsLoading(false);
            }
        };

        loadDashboardData();
    }, []);

    if (isLoading || !stats || !recommendation) {
        return <DashboardSkeleton />;
    }

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">

            {/* Dynamic Header */}
            <header className="flex items-end justify-between px-2">
                <div>
                    <div className="flex items-center gap-2 mb-3">
                        <Dialog>
                            <DialogTrigger asChild>
                                <button className="bg-yellow-100/50 text-yellow-700 border border-yellow-200/50 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider hover:bg-yellow-100 transition-colors">
                                    抢先体验 v2.4.0
                                </button>
                            </DialogTrigger>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>版本 2.4.0 更新日志</DialogTitle>
                                    <DialogDescription>发布于 2026年1月10日</DialogDescription>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="flex gap-3">
                                        <div className="mt-1 bg-amber-100 p-1 rounded-full h-fit"><Headphones className="w-3 h-3 text-amber-600" /></div>
                                        <div>
                                            <div className="text-sm font-bold text-slate-900">新板块：客户服务训练</div>
                                            <p className="text-xs text-slate-500">模拟高压投诉场景，提升危机处理能力。</p>
                                        </div>
                                    </div>
                                    <div className="flex gap-3">
                                        <div className="mt-1 bg-blue-100 p-1 rounded-full h-fit"><Zap className="w-3 h-3 text-blue-600" /></div>
                                        <div>
                                            <div className="text-sm font-bold text-slate-900">新角色：谈判教练</div>
                                            <p className="text-xs text-slate-500">练习薪资谈判与合同商议。</p>
                                        </div>
                                    </div>
                                    <div className="flex gap-3">
                                        <div className="mt-1 bg-emerald-100 p-1 rounded-full h-fit"><CheckCircle2 className="w-3 h-3 text-emerald-600" /></div>
                                        <div>
                                            <div className="text-sm font-bold text-slate-900">性能优化</div>
                                            <p className="text-xs text-slate-500">语音合成响应速度大幅提升。</p>
                                        </div>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="ghost" onClick={() => setIsWeeklyStatsOpen(false)} className="rounded-full">稍后再说</Button>
                                    <Button onClick={() => router.push('/training/customer-service')} className="rounded-full bg-slate-900 text-white px-6">立即体验</Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </div>
                    <h1 className="text-4xl font-black text-slate-900 tracking-tight leading-tight">
                        早安, <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600 cursor-pointer hover:opacity-80 transition-opacity">亚历山大</span> 👋
                    </h1>
                    <p className="text-slate-500 mt-2 text-lg font-medium">查看您的训练概览与最新进展。</p>
                </div>

                <div className="flex gap-4">
                    <Dialog open={isWeeklyStatsOpen} onOpenChange={setIsWeeklyStatsOpen}>
                        <DialogTrigger asChild>
                            <GlassCard className="px-5 py-2.5 flex items-center gap-3 !rounded-full bg-white/80 hover:bg-white cursor-pointer transition-colors shadow-sm group">
                                <div className="flex flex-col items-end">
                                    <span className="text-[10px] uppercase font-bold text-slate-400 group-hover:text-blue-500 transition-colors">本周练习</span>
                                    <span className="text-base font-bold text-slate-900">
                                        {(stats.weekly_activity.total_duration_minutes / 60).toFixed(1)} 小时
                                    </span>
                                </div>
                                <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center group-hover:bg-blue-100 transition-colors">
                                    <TrendingUp className="w-5 h-5 text-blue-600" />
                                </div>
                            </GlassCard>
                        </DialogTrigger>
                        <DialogContent className="max-w-2xl">
                            <DialogHeader>
                                <DialogTitle>本周训练报告</DialogTitle>
                                <DialogDescription>您的训练状态非常棒！</DialogDescription>
                            </DialogHeader>
                            <div className="grid grid-cols-3 gap-4 py-6">
                                <div className="p-4 bg-slate-50 rounded-2xl">
                                    <div className="text-xs font-bold text-slate-400 uppercase">总时长</div>
                                    <div className="text-2xl font-black text-slate-900 mt-1">
                                        {(stats.weekly_activity.total_duration_minutes / 60).toFixed(1)}h
                                    </div>
                                    <div className={cn("text-xs font-bold mt-1", stats.weekly_activity.trend_direction === 'up' ? "text-emerald-600" : "text-red-600")}>
                                        {stats.weekly_activity.trend_direction === 'up' ? '+' : ''}{stats.weekly_activity.trend_percentage}% 较上周
                                    </div>
                                </div>
                                <div className="p-4 bg-slate-50 rounded-2xl">
                                    <div className="text-xs font-bold text-slate-400 uppercase">训练场次</div>
                                    <div className="text-2xl font-black text-slate-900 mt-1">{stats.weekly_activity.session_count}</div>
                                    <div className="text-xs text-slate-500 font-bold mt-1">平均 {Math.round(stats.weekly_activity.total_duration_minutes / stats.weekly_activity.session_count)}分钟 / 场</div>
                                </div>
                                <div className="p-4 bg-slate-50 rounded-2xl">
                                    <div className="text-xs font-bold text-slate-400 uppercase">重点领域</div>
                                    <div className="text-xl font-black text-blue-600 mt-1">异议处理</div>
                                </div>
                            </div>
                            <div className="h-48 bg-slate-50 rounded-2xl flex items-center justify-center border border-dashed border-slate-200">
                                <span className="text-slate-400 font-medium flex items-center gap-2">
                                    <BarChart3 className="w-4 h-4" /> 活动图表可视化占位符
                                </span>
                            </div>
                            <DialogFooter>
                                <Button variant="outline" className="rounded-full">下载报告</Button>
                                <Button className="rounded-full bg-slate-900 text-white">设定目标</Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </header>

            {/* Dashboard Highlights / Call to Action */}
            <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <GlassCard className="col-span-1 md:col-span-2 p-8 bg-gradient-to-r from-slate-900 to-slate-800 text-white border-none relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/20 rounded-full blur-[80px] -translate-y-1/2 translate-x-1/2 pointer-events-none" />
                    <div className="relative z-10 flex flex-col justify-between h-full gap-6">
                        <div>
                            <div className="inline-block px-3 py-1 rounded-full bg-blue-500/20 text-blue-200 text-xs font-bold uppercase tracking-wider mb-4 border border-blue-500/30">
                                系统推荐
                            </div>
                            <h2 className="text-2xl font-bold mb-2">{recommendation.title}</h2>
                            <p className="text-slate-300 text-sm leading-relaxed max-w-lg">
                                {recommendation.reason}
                            </p>
                        </div>
                        <Link href={recommendation.target_path}>
                            <Button className="w-fit rounded-full bg-white text-slate-900 hover:bg-blue-50 font-bold">
                                {recommendation.action_label} <ArrowRight className="ml-2 w-4 h-4" />
                            </Button>
                        </Link>
                    </div>
                </GlassCard>

                <GlassCard className="col-span-1 p-6 flex flex-col justify-center items-center text-center gap-4">
                     <div className="w-16 h-16 rounded-full bg-emerald-50 flex items-center justify-center text-emerald-600 mb-2">
                        <TrendingUp className="w-8 h-8" />
                    </div>
                    <div>
                        <div className="text-3xl font-black text-slate-900">{stats.last_session.score}</div>
                        <div className="text-xs font-bold text-slate-400 uppercase mt-1">上次得分</div>
                    </div>
                     <p className="text-xs text-slate-500 px-4">您的表现优于 {stats.last_session.percentile}% 的用户，继续保持！</p>
                </GlassCard>
            </section>

            {/* Recent Activity */}
            <section>
                <div className="flex items-center justify-between mb-6 px-2">
                    <h2 className="text-xl font-bold text-slate-900 flex items-center gap-3">
                        最近记录
                    </h2>
                    <Dialog open={isFilterOpen} onOpenChange={setIsFilterOpen}>
                        <DialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="text-slate-500 hover:text-slate-900 hover:bg-white/50">
                                <Filter className="w-4 h-4 mr-2" /> 筛选
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>筛选记录</DialogTitle>
                            </DialogHeader>
                            <div className="py-6 space-y-4">
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">日期范围</label>
                                    <div className="flex gap-2">
                                        <Button variant="outline" className="flex-1 justify-start font-normal"><Calendar className="w-4 h-4 mr-2 text-slate-400" /> 开始日期</Button>
                                        <Button variant="outline" className="flex-1 justify-start font-normal"><Calendar className="w-4 h-4 mr-2 text-slate-400" /> 结束日期</Button>
                                    </div>
                                </div>
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">训练类型</label>
                                    <div className="flex gap-2 flex-wrap">
                                        <Badge variant="blue" className="cursor-pointer">全部</Badge>
                                        <Badge variant="neutral" className="cursor-pointer bg-slate-100 hover:bg-slate-200">销售对练</Badge>
                                        <Badge variant="neutral" className="cursor-pointer bg-slate-100 hover:bg-slate-200">PPT 演示</Badge>
                                    </div>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button className="rounded-full bg-slate-900 text-white w-full">应用筛选</Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {historyItems.length === 0 ? (
                        <div className="col-span-full">
                            <EmptyState
                                title="暂无历史记录"
                                description="开始您的第一次 AI 角色扮演，记录将显示在这里。"
                                actionLabel="开始训练"
                                onAction={() => router.push('/training')}
                            />
                        </div>
                    ) : (
                        historyItems.map((item) => (
                            <SwipeableItem key={item.id} onDelete={() => handleDeleteHistory(item.id)}>
                                <Dialog>
                                    <DialogTrigger asChild>
                                        <GlassCard className="p-0 flex flex-col hover:shadow-lg transition-all cursor-pointer group bg-white border-none shadow-sm ring-1 ring-slate-100">
                                            <div className="p-5 flex justify-between items-start pb-4">
                                                <div className="flex gap-4">
                                                    <div className={cn("w-12 h-12 rounded-2xl flex items-center justify-center font-bold text-lg group-hover:scale-110 transition-transform",
                                                        // UI mapping logic
                                                        item.scenario_type === 'sales_bot' ? "bg-blue-50 text-blue-600" : "bg-purple-50 text-purple-600"
                                                    )}>
                                                        {item.scenario_type === 'sales_bot' ? 'S' : 'P'}
                                                    </div>
                                                    <div className="text-left">
                                                        <h4 className="font-bold text-base text-slate-900">{item.title}</h4>
                                                        <p className="text-xs text-slate-500 mt-1 font-medium">
                                                            {formatTimeAgo(item.start_time)} • 持续 {formatDuration(item.duration_seconds)}
                                                        </p>
                                                    </div>
                                                </div>
                                                <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-300 hover:text-slate-600"><MoreHorizontal className="w-4 h-4" /></Button>
                                            </div>

                                            <div className="px-5 pb-5">
                                                <div className="bg-slate-50 rounded-xl p-3 flex gap-4">
                                                    <div className="flex-1">
                                                        <div className="text-[10px] uppercase font-bold text-slate-400 mb-1 tracking-wider">综合评分</div>
                                                        <div className="text-2xl font-black text-slate-900">{item.overall_score}</div>
                                                    </div>
                                                    <div className="w-px bg-slate-200 my-1"></div>
                                                    <div className="flex-1 pl-4">
                                                        <div className="text-[10px] uppercase font-bold text-slate-400 mb-1 tracking-wider">趋势</div>
                                                        <div className={cn("text-sm font-bold flex items-center gap-1 text-emerald-600")}>
                                                            {item.score_trend || "--"}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </GlassCard>
                                    </DialogTrigger>
                                    <DialogContent className="max-w-2xl">
                                        <DialogHeader>
                                            <DialogTitle className="flex items-center gap-3">
                                                <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center text-sm",
                                                    item.scenario_type === 'sales_bot' ? "bg-blue-50 text-blue-600" : "bg-purple-50 text-purple-600"
                                                )}>
                                                    {item.scenario_type === 'sales_bot' ? 'S' : 'P'}
                                                </div>
                                                {item.scenario_type === 'sales_bot' ? '会话分析' : '演示分析'}
                                            </DialogTitle>
                                            <DialogDescription>ID: #{item.id} • {formatTimeAgo(item.start_time)}</DialogDescription>
                                        </DialogHeader>
                                        <div className="grid grid-cols-2 gap-6 py-4">
                                            <div className="space-y-4">
                                                <h4 className="font-bold text-slate-900 border-b pb-2">得分详情</h4>
                                                {/* Simplified placeholder for breakdown */}
                                                <div className="space-y-3">
                                                    <div className="flex justify-between items-center">
                                                        <span className="text-sm text-slate-600">综合得分</span>
                                                        <div className="w-32 h-2 bg-slate-100 rounded-full overflow-hidden">
                                                            <div className="h-full bg-emerald-500" style={{ width: `${item.overall_score}%` }}></div>
                                                        </div>
                                                        <span className="text-sm font-bold text-emerald-600">{item.overall_score}</span>
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="space-y-4">
                                                <h4 className="font-bold text-slate-900 border-b pb-2">AI 点评</h4>
                                                <div className="p-3 rounded-xl text-xs leading-relaxed bg-slate-50 text-slate-600">
                                                    &quot;{item.feedback_summary || "暂无具体反馈。"}&quot;
                                                </div>
                                            </div>
                                        </div>
                                        <DialogFooter>
                                            <Button variant="outline" className="rounded-full">分享分析</Button>
                                            <Button className="rounded-full bg-slate-900 text-white">查看详情</Button>
                                        </DialogFooter>
                                    </DialogContent>
                                </Dialog>
                            </SwipeableItem>
                        ))
                    )}
                </div>
            </section>
        </div>
    );
}