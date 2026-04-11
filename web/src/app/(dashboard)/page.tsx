"use client";

import packageJson from "../../../package.json";
import { useEffect, useState } from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { DashboardSkeleton } from "@/components/dashboard-skeleton";
import { SwipeableItem } from "@/components/ui/swipeable-item";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";
import {
    TrendingUp,
    Filter,
    CheckCircle2,
    Zap,
    ArrowRight,
    Presentation,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { DashboardStats, Recommendation, SessionItem } from "@/lib/api/types";
import { useCurrentUser } from "@/hooks/use-current-user";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/glass-modal";
import { useRouter } from "next/navigation";

const DASHBOARD_HISTORY_FALLBACK_PREFIX = "session-";

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
    if (diffInSeconds < 172800) return "昨天";
    return `${Math.floor(diffInSeconds / 86400)}天前`;
};

const DEFAULT_STATS: DashboardStats = {
    weekly_activity: { total_duration_minutes: 0, session_count: 0, trend_direction: "flat", trend_percentage: 0 },
    last_session: { score: 0, percentile: 50, trend: "stable" },
    effectiveness: {
        pass_rate_3min_flow: 0,
        pass_rate_5turn_defense: 0,
        pass_rate_4step_structure: 0,
        next_day_retry_rate: 0,
    },
};

const DEFAULT_RECOMMENDATION: Recommendation = {
    title: "开始练习",
    reason: "欢迎使用训练系统，开始一次练习来提升您的技能吧！",
    action_label: "开始训练",
    target_path: "/training",
};

function getGreeting(): string {
    const hour = new Date().getHours();
    if (hour < 12) return "早安";
    if (hour < 18) return "午安";
    return "晚安";
}

function getVersionBadge(): string {
    return `v${packageJson.version}`;
}

function getDisplayName(currentUser: ReturnType<typeof useCurrentUser>["data"]): string {
    return currentUser?.display_name || currentUser?.name || currentUser?.email?.split("@")[0] || "用户";
}

function resolveDashboardSessionId(item: Pick<SessionItem, "id" | "session_id">): string | null {
    const sessionId = item.session_id?.trim();
    if (sessionId) {
        return sessionId;
    }

    const fallbackId = item.id?.trim();
    if (fallbackId && !fallbackId.startsWith(DASHBOARD_HISTORY_FALLBACK_PREFIX)) {
        return fallbackId;
    }

    return null;
}

function getDashboardHistoryActions(item: SessionItem): {
    historyHref: string;
    reportHref: string | null;
    reportLabel: string;
    disabledReason: string | null;
} {
    // Dashboard 首页只保留“查看报告”深链，不重新引入导出报告 affordance。
    const sessionId = resolveDashboardSessionId(item);
    const supportsSharedReportRoute = item.scenario_type === "sales" || item.scenario_type === "presentation";

    if (!sessionId) {
        return {
            historyHref: "/history",
            reportHref: null,
            reportLabel: "报告暂不可用",
            disabledReason: "缺少会话编号，请到历史页核对这条记录。",
        };
    }

    if (!supportsSharedReportRoute) {
        return {
            historyHref: "/history",
            reportHref: null,
            reportLabel: "报告暂不可用",
            disabledReason: "当前记录类型请到历史页查看，首页暂不提供快捷入口。",
        };
    }

    if (item.status !== "completed") {
        return {
            historyHref: "/history",
            reportHref: null,
            reportLabel: "报告生成中",
            disabledReason: "会话完成并生成统一训练证据后即可查看报告。",
        };
    }

    return {
        historyHref: "/history",
        reportHref: `/practice/${sessionId}/report`,
        reportLabel: "查看报告",
        disabledReason: null,
    };
}

function getOnboardingTitle(hasHistory: boolean): string {
    return hasHistory ? "继续按这 3 步推进训练" : "第一次来，先这样开始";
}

export default function HomePage() {
    const router = useRouter();
    const { data: currentUser } = useCurrentUser();
    const displayName = getDisplayName(currentUser);
    const versionBadge = getVersionBadge();
    const [isWeeklyStatsOpen, setIsWeeklyStatsOpen] = useState(false);

    const [isLoading, setIsLoading] = useState(true);
    const [stats, setStats] = useState<DashboardStats>(DEFAULT_STATS);
    const [recommendation, setRecommendation] = useState<Recommendation>(DEFAULT_RECOMMENDATION);
    const [historyItems, setHistoryItems] = useState<SessionItem[]>([]);

    const handleDeleteHistory = (id: string) => {
        setHistoryItems((prev) => prev.filter((item) => item.id !== id));
    };

    useEffect(() => {
        const loadDashboardData = async () => {
            setIsLoading(true);
            const [statsResult, recResult, historyResult] = await Promise.allSettled([
                api.dashboard.getStats(),
                api.dashboard.getRecommendation(),
                api.dashboard.getHistory(),
            ]);

            setStats(statsResult.status === "fulfilled" ? statsResult.value : DEFAULT_STATS);
            setRecommendation(recResult.status === "fulfilled" ? recResult.value : DEFAULT_RECOMMENDATION);
            setHistoryItems(historyResult.status === "fulfilled" ? historyResult.value : []);
            setIsLoading(false);
        };

        void loadDashboardData();
    }, []);

    const resolvedHistoryItems = historyItems.map((item) => ({
        item,
        historyActions: getDashboardHistoryActions(item),
    }));
    const reportShortcut = resolvedHistoryItems.find(({ historyActions }) => historyActions.reportHref);
    const hasHistory = historyItems.length > 0;
    const onboardingSteps = [
        {
            key: "train",
            badge: "第 1 步",
            title: recommendation.title,
            description: recommendation.reason,
            href: recommendation.target_path,
            actionLabel: recommendation.action_label,
            icon: Zap,
            accentClassName: "bg-blue-50 text-blue-700 border-blue-100",
            buttonClassName: "rounded-full bg-slate-900 text-white hover:bg-slate-800",
        },
        {
            key: "history",
            badge: "第 2 步",
            title: "去历史页复盘",
            description: "完整记录、筛选与复练线索统一收口在历史页。",
            href: "/history",
            actionLabel: "去历史页",
            icon: Presentation,
            accentClassName: "bg-violet-50 text-violet-700 border-violet-100",
            buttonClassName: "rounded-full",
        },
        {
            key: "report",
            badge: "第 3 步",
            title: reportShortcut ? "打开最近一次可用报告" : "完成训练后看统一报告",
            description: reportShortcut
                ? `最近一次可用报告：${reportShortcut.item.title}`
                : "报告生成后，可从最近记录或历史页进入统一报告。",
            href: reportShortcut?.historyActions.reportHref ?? "/history",
            actionLabel: "报告入口",
            icon: CheckCircle2,
            accentClassName: "bg-emerald-50 text-emerald-700 border-emerald-100",
            buttonClassName: "rounded-full",
        },
    ];
    const versionDialogHighlights = [
        {
            title: recommendation.title,
            description: recommendation.reason,
            icon: Zap,
            iconClassName: "bg-blue-100 text-blue-600",
        },
        {
            title: hasHistory ? "最近记录入口已就绪" : "先完成第一次训练",
            description: hasHistory
                ? `首页当前已加载 ${historyItems.length} 条最近记录，可直接去历史页或统一报告继续复盘。`
                : "完成第一次训练后，首页会出现历史页和统一报告的快捷入口。",
            icon: Presentation,
            iconClassName: "bg-violet-100 text-violet-600",
        },
        {
            title: "首页只保留真实闭环入口",
            description: reportShortcut
                ? "这个版本支持继续训练、查看历史，以及直接打开最近一次可用报告。"
                : "这个版本支持先训练、再去历史页/统一报告复盘，不再放装饰性空壳按钮。",
            icon: CheckCircle2,
            iconClassName: "bg-emerald-100 text-emerald-600",
        },
    ];

    if (isLoading) {
        return <DashboardSkeleton />;
    }

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
            <header className="flex items-end justify-between px-2">
                <div>
                    <div className="flex items-center gap-2 mb-3">
                        <Dialog>
                            <DialogTrigger asChild>
                                <button className="bg-yellow-100/50 text-yellow-700 border border-yellow-200/50 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider hover:bg-yellow-100 transition-colors">
                                    {versionBadge}
                                </button>
                            </DialogTrigger>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>当前版本可用入口</DialogTitle>
                                    <DialogDescription>{versionBadge} 当前只展示真实可用的训练、历史与报告入口。</DialogDescription>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    {versionDialogHighlights.map((highlight) => {
                                        const Icon = highlight.icon;
                                        return (
                                            <div key={highlight.title} className="flex gap-3">
                                                <div className={cn("mt-1 p-1 rounded-full h-fit", highlight.iconClassName)}>
                                                    <Icon className="w-3 h-3" />
                                                </div>
                                                <div>
                                                    <div className="text-sm font-bold text-slate-900">{highlight.title}</div>
                                                    <p className="text-xs text-slate-500">{highlight.description}</p>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                                <DialogFooter>
                                    <DialogClose asChild>
                                        <Button variant="ghost" className="rounded-full">稍后再看</Button>
                                    </DialogClose>
                                    <DialogClose asChild>
                                        <Button onClick={() => router.push(recommendation.target_path)} className="rounded-full bg-slate-900 text-white px-6">{recommendation.action_label}</Button>
                                    </DialogClose>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </div>
                    <h1 className="text-4xl font-black text-slate-900 tracking-tight leading-tight">
                        {getGreeting()}, <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600 cursor-pointer hover:opacity-80 transition-opacity">{displayName}</span> 👋
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
                                    <div className={cn("text-xs font-bold mt-1", stats.weekly_activity.trend_direction === "up" ? "text-emerald-600" : "text-red-600")}>
                                        {stats.weekly_activity.trend_direction === "up" ? "+" : ""}{stats.weekly_activity.trend_percentage}% 较上周
                                    </div>
                                </div>
                                <div className="p-4 bg-slate-50 rounded-2xl">
                                    <div className="text-xs font-bold text-slate-400 uppercase">训练场次</div>
                                    <div className="text-2xl font-black text-slate-900 mt-1">{stats.weekly_activity.session_count}</div>
                                    <div className="text-xs text-slate-500 font-bold mt-1">平均 {stats.weekly_activity.session_count > 0 ? Math.round(stats.weekly_activity.total_duration_minutes / stats.weekly_activity.session_count) : 0}分钟 / 场</div>
                                </div>
                                <div className="p-4 bg-slate-50 rounded-2xl">
                                    <div className="text-xs font-bold text-slate-400 uppercase">次日复练率</div>
                                    <div className="text-xl font-black text-blue-600 mt-1">
                                        {(stats.effectiveness?.next_day_retry_rate ?? 0).toFixed(1)}%
                                    </div>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div className="rounded-xl bg-blue-50 border border-blue-100 p-3">
                                    <p className="text-[11px] text-blue-700 font-semibold">3分钟连续表达通过率</p>
                                    <p className="text-xl font-black text-blue-900 mt-1">
                                        {(stats.effectiveness?.pass_rate_3min_flow ?? 0).toFixed(1)}%
                                    </p>
                                </div>
                                <div className="rounded-xl bg-emerald-50 border border-emerald-100 p-3">
                                    <p className="text-[11px] text-emerald-700 font-semibold">5轮追问稳定通过率</p>
                                    <p className="text-xl font-black text-emerald-900 mt-1">
                                        {(stats.effectiveness?.pass_rate_5turn_defense ?? 0).toFixed(1)}%
                                    </p>
                                </div>
                                <div className="rounded-xl bg-amber-50 border border-amber-100 p-3">
                                    <p className="text-[11px] text-amber-700 font-semibold">四段结构完整率</p>
                                    <p className="text-xl font-black text-amber-900 mt-1">
                                        {(stats.effectiveness?.pass_rate_4step_structure ?? 0).toFixed(1)}%
                                    </p>
                                </div>
                                <div className="rounded-xl bg-violet-50 border border-violet-100 p-3">
                                    <p className="text-[11px] text-violet-700 font-semibold">次日复练率</p>
                                    <p className="text-xl font-black text-violet-900 mt-1">
                                        {(stats.effectiveness?.next_day_retry_rate ?? 0).toFixed(1)}%
                                    </p>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button variant="outline" className="rounded-full" onClick={() => setIsWeeklyStatsOpen(false)}>关闭</Button>
                                <Link href="/history">
                                    <Button className="rounded-full bg-slate-900 text-white">查看历史报告</Button>
                                </Link>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </header>

            <section className="grid grid-cols-1 xl:grid-cols-[0.9fr_2.1fr] gap-4">
                <GlassCard className="p-6 bg-white/80 border-none shadow-sm ring-1 ring-slate-100">
                    <div className="flex items-center gap-3 mb-3">
                        <div className="w-10 h-10 rounded-2xl bg-blue-50 flex items-center justify-center text-blue-600">
                            <Zap className="w-5 h-5" />
                        </div>
                        <div>
                            <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">最小上手指引</p>
                            <h2 className="text-xl font-bold text-slate-900 mt-1">{getOnboardingTitle(hasHistory)}</h2>
                        </div>
                    </div>
                    <p className="text-sm leading-6 text-slate-600">
                        {recommendation.reason}
                    </p>
                    <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 px-4 py-3 text-xs leading-6 text-slate-500">
                        先训练，再去历史页和统一报告复盘；首页不再放看起来能点、实际没有闭环的装饰性按钮。
                    </div>
                </GlassCard>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {onboardingSteps.map((step) => {
                        const Icon = step.icon;
                        return (
                            <GlassCard key={step.key} className="p-5 bg-white/80 border-none shadow-sm ring-1 ring-slate-100 flex flex-col gap-4">
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <span className={cn("inline-flex rounded-full border px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide", step.accentClassName)}>
                                            {step.badge}
                                        </span>
                                        <h3 className="text-base font-bold text-slate-900 mt-3">{step.title}</h3>
                                    </div>
                                    <div className={cn("w-10 h-10 rounded-2xl flex items-center justify-center", step.accentClassName)}>
                                        <Icon className="w-5 h-5" />
                                    </div>
                                </div>
                                <p className="text-sm leading-6 text-slate-600 min-h-[72px]">{step.description}</p>
                                <Link href={step.href}>
                                    <Button variant={step.key === "train" ? "default" : "outline"} className={step.buttonClassName}>
                                        {step.actionLabel} <ArrowRight className="ml-2 w-4 h-4" />
                                    </Button>
                                </Link>
                            </GlassCard>
                        );
                    })}
                </div>
            </section>

            {stats.effectiveness && (
                <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                    <GlassCard className="p-5">
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">3分钟连续表达通过率</p>
                        <p className="text-2xl font-black text-slate-900 mt-2">
                            {stats.effectiveness.pass_rate_3min_flow.toFixed(1)}%
                        </p>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">5轮追问稳定通过率</p>
                        <p className="text-2xl font-black text-slate-900 mt-2">
                            {stats.effectiveness.pass_rate_5turn_defense.toFixed(1)}%
                        </p>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">四段结构完整率</p>
                        <p className="text-2xl font-black text-slate-900 mt-2">
                            {stats.effectiveness.pass_rate_4step_structure.toFixed(1)}%
                        </p>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">次日复练率</p>
                        <p className="text-2xl font-black text-slate-900 mt-2">
                            {stats.effectiveness.next_day_retry_rate.toFixed(1)}%
                        </p>
                    </GlassCard>
                </section>
            )}

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
                        <div className="text-3xl font-black text-slate-900">{stats.last_session?.score ?? 0}</div>
                        <div className="text-xs font-bold text-slate-400 uppercase mt-1">上次得分</div>
                    </div>
                    <p className="text-xs text-slate-500 px-4">您的表现优于 {stats.last_session?.percentile ?? 0}% 的用户，继续保持！</p>
                </GlassCard>
            </section>

            <section>
                <div className="flex items-center justify-between mb-6 px-2 gap-3 flex-wrap">
                    <h2 className="text-xl font-bold text-slate-900 flex items-center gap-3">
                        最近记录
                    </h2>
                    <div className="flex flex-col items-end gap-1 sm:flex-row sm:items-center">
                        {/* 首页不承载假筛选弹窗，复杂筛选统一深链到历史页。 */}
                        <span className="text-xs text-slate-400">高级筛选请在历史页进行</span>
                        <Link href="/history">
                            <Button variant="ghost" size="sm" className="text-slate-500 hover:text-slate-900 hover:bg-white/50">
                                <Filter className="w-4 h-4 mr-2" /> 去历史页筛选
                            </Button>
                        </Link>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {historyItems.length === 0 ? (
                        <div className="col-span-full">
                            <EmptyState
                                title="暂无历史记录"
                                description="开始您的第一次 AI 角色扮演，记录将显示在这里。"
                                actionLabel="开始训练"
                                onAction={() => router.push("/training")}
                            />
                        </div>
                    ) : (
                        resolvedHistoryItems.map(({ item, historyActions }) => {
                            return (
                                <SwipeableItem key={item.id} onDelete={() => handleDeleteHistory(item.id)}>
                                    <GlassCard className="p-0 flex flex-col hover:shadow-lg transition-all bg-white border-none shadow-sm ring-1 ring-slate-100">
                                        <div className="p-5 flex justify-between items-start pb-4 gap-4">
                                            <div className="flex gap-4">
                                                <div
                                                    className={cn(
                                                        "w-12 h-12 rounded-2xl flex items-center justify-center font-bold text-lg transition-transform",
                                                        item.scenario_type === "sales" ? "bg-blue-50 text-blue-600" : "bg-purple-50 text-purple-600",
                                                    )}
                                                >
                                                    {item.scenario_type === "sales" ? "S" : "P"}
                                                </div>
                                                <div className="text-left">
                                                    <h4 className="font-bold text-base text-slate-900">{item.title}</h4>
                                                    <p className="text-xs text-slate-500 mt-1 font-medium">
                                                        {formatTimeAgo(item.start_time)} • 持续 {formatDuration(item.duration_seconds)}
                                                    </p>
                                                </div>
                                            </div>
                                            <Link href={historyActions.historyHref}>
                                                <Button variant="ghost" size="sm" className="rounded-full text-slate-500 hover:text-slate-700">
                                                    查看历史
                                                </Button>
                                            </Link>
                                        </div>

                                        <div className="px-5 pb-5 space-y-4">
                                            <div className="bg-slate-50 rounded-xl p-3 flex gap-4">
                                                <div className="flex-1">
                                                    <div className="text-[10px] uppercase font-bold text-slate-400 mb-1 tracking-wider">综合评分</div>
                                                    <div className="text-2xl font-black text-slate-900">{item.overall_score}</div>
                                                </div>
                                                <div className="w-px bg-slate-200 my-1" />
                                                <div className="flex-1 pl-4">
                                                    <div className="text-[10px] uppercase font-bold text-slate-400 mb-1 tracking-wider">趋势</div>
                                                    <div className={cn("text-sm font-bold flex items-center gap-1 text-emerald-600")}>
                                                        --
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                                                <div className="space-y-1">
                                                    <div className="text-xs font-bold uppercase tracking-wider text-slate-400">快捷入口</div>
                                                    <p className="text-sm text-slate-600">
                                                        {historyActions.disabledReason || "可直接打开统一报告；更多筛选与完整记录请前往历史页。"}
                                                    </p>
                                                </div>
                                                <div className="flex flex-wrap gap-2 sm:justify-end">
                                                    <Link href={historyActions.historyHref}>
                                                        <Button variant="outline" className="rounded-full">历史页</Button>
                                                    </Link>
                                                    {historyActions.reportHref ? (
                                                        <Link href={historyActions.reportHref}>
                                                            <Button className="rounded-full bg-slate-900 text-white">{historyActions.reportLabel}</Button>
                                                        </Link>
                                                    ) : (
                                                        <Button disabled className="rounded-full">{historyActions.reportLabel}</Button>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    </GlassCard>
                                </SwipeableItem>
                            );
                        })
                    )}
                </div>
            </section>
        </div>
    );
}
