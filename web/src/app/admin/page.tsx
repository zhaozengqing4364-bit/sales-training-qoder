
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, Database, HardDrive, Server, Users } from "lucide-react";

import { api } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";

function toPercent(value: unknown): number {
    if (typeof value === "number" && Number.isFinite(value)) {
        return Math.max(0, Math.min(100, value));
    }
    return 0;
}

export default function AdminDashboardPage() {
    const [liveMetrics, setLiveMetrics] = useState({
        backendStatus: "unknown" as "unknown" | "online" | "offline",
        passRate3minFlow: 0,
        passRate5turnDefense: 0,
        passRate4stepStructure: 0,
        nextDayRetryRate: 0,
    });

    useEffect(() => {
        let cancelled = false;

        const loadLiveMetrics = async () => {
            const [healthResult, dashboardResult] = await Promise.allSettled([
                api.internal.health(),
                api.analyticsOpen.getDashboard({ days: 7 }),
            ]);

            if (cancelled) return;

            const effect = (
                dashboardResult.status === "fulfilled"
                    ? dashboardResult.value.effectiveness
                    : undefined
            ) || {
                pass_rate_3min_flow: 0,
                pass_rate_5turn_defense: 0,
                pass_rate_4step_structure: 0,
                next_day_retry_rate: 0,
            };

            setLiveMetrics({
                backendStatus: healthResult.status === "fulfilled" ? "online" : "offline",
                passRate3minFlow: toPercent(effect.pass_rate_3min_flow),
                passRate5turnDefense: toPercent(effect.pass_rate_5turn_defense),
                passRate4stepStructure: toPercent(effect.pass_rate_4step_structure),
                nextDayRetryRate: toPercent(effect.next_day_retry_rate),
            });
        };

        void loadLiveMetrics();

        return () => {
            cancelled = true;
        };
    }, []);

    return (
        <div className="space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
            <header className="flex flex-col md:flex-row justify-between items-end gap-4">
                <div>
                    <h1 className="text-4xl font-black text-slate-900 tracking-tight">管理控制台</h1>
                    <p className="text-slate-500 mt-2 font-medium">系统运行状态概览与管理</p>
                </div>
                <div className="flex gap-4 w-full md:w-auto">
                    <Link
                        href="/admin/analytics"
                        className="inline-flex h-11 items-center justify-center rounded-full bg-slate-900 px-6 text-sm font-medium text-white shadow-lg shadow-slate-900/20 transition hover:bg-slate-800"
                    >
                        进入数据分析
                    </Link>
                </div>
            </header>

            <GlassCard className="p-5 border border-blue-100/60 bg-blue-50/40">
                <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                    <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">训练效果核心看板（近7天）</h2>
                    <Badge variant={liveMetrics.backendStatus === "online" ? "green" : liveMetrics.backendStatus === "offline" ? "red" : "secondary"}>
                        {liveMetrics.backendStatus === "online" ? "后端在线" : liveMetrics.backendStatus === "offline" ? "后端离线" : "状态未知"}
                    </Badge>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                        <div className="text-xs text-slate-500">3分钟连续表达通过率</div>
                        <div className="text-xl font-black text-slate-900 mt-1">{liveMetrics.passRate3minFlow.toFixed(1)}%</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">5轮追问稳定通过率</div>
                        <div className="text-xl font-black text-slate-900 mt-1">{liveMetrics.passRate5turnDefense.toFixed(1)}%</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">四段结构完整率</div>
                        <div className="text-xl font-black text-slate-900 mt-1">{liveMetrics.passRate4stepStructure.toFixed(1)}%</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">次日复练率</div>
                        <div className="text-xl font-black text-slate-900 mt-1">{liveMetrics.nextDayRetryRate.toFixed(1)}%</div>
                    </div>
                </div>
            </GlassCard>

            <GlassCard className="p-5 border border-amber-100/70 bg-amber-50/60">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">管理首页真实度说明</h2>
                        <p className="mt-2 text-sm text-slate-700 text-pretty">
                            当前只有上方“训练效果核心看板（近7天）”直接读取 <code>api.internal.health()</code> 与 <code>api.analyticsOpen.getDashboard()</code>。
                            以下卡片当前只作为 manager/admin truth surface inventory，用来标记还未接上真实 authority 的组织、资源与运维面。
                        </p>
                    </div>
                    <Badge variant="secondary">其余卡片已降级为 inventory</Badge>
                </div>
            </GlassCard>

            {/* Bento Grid Stats */}
            <div className="grid grid-cols-12 gap-6">

                {/* Total Users (Span 4) */}
                <Dialog>
                    <DialogTrigger asChild>
                        <GlassCard className="col-span-12 md:col-span-4 p-8 relative overflow-hidden group cursor-pointer hover:shadow-lg transition-all">
                            <div className="absolute right-0 top-0 p-8 opacity-5 group-hover:scale-110 transition-transform duration-500">
                                <Users className="w-32 h-32 text-slate-900" />
                            </div>
                            <div className="relative z-10">
                                <div className="text-slate-500 text-xs font-bold uppercase tracking-widest mb-3">总用户数</div>
                                <div className="text-3xl font-black text-slate-900 mb-4 tracking-tight">待接真实统计</div>
                                <p className="text-sm text-slate-500 text-pretty">
                                    当前首页没有统一的总用户 authority；需要回到用户列表 / admin analytics 决定应该复用哪条真实统计线。
                                </p>
                            </div>
                        </GlassCard>
                    </DialogTrigger>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader>
                            <DialogTitle>总用户数 truth surface 盘点</DialogTitle>
                            <DialogDescription>这个入口当前只说明缺口，不再伪装增长统计已经接通。</DialogDescription>
                        </DialogHeader>
                        <div className="py-6 space-y-4">
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 text-pretty">
                                当前首页缺少“总用户数 / 新增注册 / 流失率”的统一 authority。若后续要恢复该卡片，应先明确是复用 `/admin/users` 的真实用户集合，还是复用 admin analytics 的 cohort 统计，而不是继续展示示意数字。
                            </div>
                            <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500 text-pretty">
                                T01 先把这块降级为 inventory；T02 再决定接真实聚合还是仅保留跳转入口。
                            </div>
                        </div>
                        <DialogFooter>
                            <Link href="/admin/users" className="w-full">
                                <Button className="w-full rounded-full bg-slate-900 text-white">前往用户管理</Button>
                            </Link>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Active Sessions (Span 4) */}
                <Dialog>
                    <DialogTrigger asChild>
                        <GlassCard className="col-span-12 md:col-span-4 p-8 relative overflow-hidden group cursor-pointer hover:shadow-lg transition-all">
                            <div className="absolute right-0 top-0 p-8 opacity-5 group-hover:scale-110 transition-transform duration-500">
                                <Activity className="w-32 h-32 text-purple-600" />
                            </div>
                            <div className="relative z-10">
                                <div className="text-slate-500 text-xs font-bold uppercase tracking-widest mb-3">活跃会话</div>
                                <div className="text-3xl font-black text-slate-900 mb-4 tracking-tight">待接真实统计</div>
                                <p className="text-sm text-slate-500 text-pretty">
                                    当前首页没有活跃会话的统一 authority；真实判断应回到 admin analytics / support runtime，而不是继续沿用示意值。
                                </p>
                            </div>
                        </GlassCard>
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>活跃会话 truth surface 盘点</DialogTitle>
                            <DialogDescription>这块当前保留为 inventory，提醒后续应接入真实会话线。</DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 text-pretty">
                                如果要展示“当前活跃会话”，应该优先复用 support/runtime 的 session health 或 admin analytics 的真实窗口统计，而不是在首页本地维护另一套数字。
                            </div>
                            <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500 text-pretty">
                                当前管理面已有 projection-backed manager-lite 与趋势/排行榜页；首页这里只负责暴露还未 truthify 的入口。
                            </div>
                        </div>
                        <DialogFooter>
                            <Link href="/admin/analytics" className="w-full">
                                <Button className="w-full rounded-full bg-slate-900 text-white">前往数据分析</Button>
                            </Link>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* System Health (Span 4) */}
                <Dialog>
                    <DialogTrigger asChild>
                        <GlassCard className="col-span-12 md:col-span-4 p-8 flex flex-col justify-between cursor-pointer hover:shadow-lg transition-all">
                            <div className="flex justify-between items-start">
                                <div>
                                    <div className="text-slate-500 text-xs font-bold uppercase tracking-widest mb-2">系统健康度</div>
                                    <div className={`text-2xl font-bold ${liveMetrics.backendStatus === "online" ? "text-emerald-600" : liveMetrics.backendStatus === "offline" ? "text-rose-600" : "text-slate-500"}`}>
                                        {liveMetrics.backendStatus === "online" ? "仅后端状态已接通" : liveMetrics.backendStatus === "offline" ? "后端离线" : "状态未知"}
                                    </div>
                                </div>
                                <div className={`p-3 rounded-2xl ${liveMetrics.backendStatus === "online" ? "bg-emerald-50 text-emerald-600" : liveMetrics.backendStatus === "offline" ? "bg-rose-50 text-rose-600" : "bg-slate-100 text-slate-500"}`}>
                                    <Activity className="w-6 h-6" />
                                </div>
                            </div>
                            <div className="space-y-4 mt-4 text-sm text-slate-500 text-pretty">
                                <p>CPU、内存、数据库延迟等资源指标当前没有统一接入首页 authority。</p>
                                <p>这张卡暂时只保留“后端在线 / 离线”这一条真实信号，其余内容已降级为待接监控 inventory。</p>
                            </div>
                        </GlassCard>
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>系统诊断 truth surface 盘点</DialogTitle>
                            <DialogDescription>当前首页不再伪装 CPU / 内存 / 延迟数字已经接通。</DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 text-pretty">
                                已接通信号：后端健康检查（通过 <code>api.internal.health()</code> 读取在线 / 离线）。
                            </div>
                            <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500 text-pretty">
                                未接通信号：CPU、内存、数据库延迟、主机/磁盘资源。后续若要展示，应先明确复用哪条 support/runtime 或基础设施指标线。
                            </div>
                            <p className="mt-4 text-sm text-slate-500 text-pretty">
                                首页目前只保留后端在线 / 离线这一条真实信号；CPU、内存、数据库延迟与主机资源仍未接入统一数据源。
                            </p>
                        </div>
                        <DialogFooter>
                            <Link href="/admin/logs" className="w-full">
                                <Button className="w-full rounded-full bg-slate-900 text-white">查看系统日志入口</Button>
                            </Link>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            {/* Quick Actions & Recent */}
            <GlassCard className="p-5 border border-slate-200/70 bg-slate-50/70">
                <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">管理动作与运营动态盘点</h2>
                        <p className="text-sm text-slate-600 text-pretty">
                            下方区域当前主要用于盘点哪些入口仍是草拟动作、示意日志或待接告警；它们暂时不应被解读为已经接通的运营自动化或实时监控面。
                        </p>
                    </div>
                    <Badge variant="secondary">draft / inventory only</Badge>
                </div>
            </GlassCard>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Quick Actions Grid */}
                <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-4">
                    {/* Action 1: Add User */}
                    <Dialog>
                        <DialogTrigger asChild>
                            <GlassCard hoverEffect className="p-6 flex flex-col items-center justify-center gap-4 group cursor-pointer">
                                <div className="w-14 h-14 rounded-[1.2rem] bg-blue-50 hover:bg-blue-100 border-blue-100 text-blue-600 border flex items-center justify-center transition-all duration-300 group-hover:scale-110 group-hover:rotate-3 shadow-sm">
                                    <Users className="w-7 h-7" strokeWidth={1.5} />
                                </div>
                                <span className="text-sm font-bold text-slate-600 group-hover:text-slate-900 transition-colors">新增用户</span>
                            </GlassCard>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>新增用户</DialogTitle>
                                <DialogDescription>为员工或管理员创建新账户。</DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <label className="text-xs font-bold uppercase text-slate-500">名字</label>
                                        <input className="w-full h-10 border rounded-lg px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-xs font-bold uppercase text-slate-500">姓氏</label>
                                        <input className="w-full h-10 border rounded-lg px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold uppercase text-slate-500">电子邮箱</label>
                                    <input className="w-full h-10 border rounded-lg px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold uppercase text-slate-500">角色</label>
                                    <select className="w-full h-10 border rounded-lg px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white">
                                        <option>用户</option>
                                        <option>经理</option>
                                        <option>管理员</option>
                                    </select>
                                </div>
                            </div>
                            <Users className="w-5 h-5 text-blue-600" />
                        </div>
                        <Link href="/admin/users" className="mt-4 inline-flex text-sm font-medium text-blue-600 hover:text-blue-700">
                            进入用户管理
                        </Link>
                    </GlassCard>

                    <GlassCard className="p-5 border border-white/80 bg-white/80">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h3 className="text-base font-bold text-slate-900">数据分析与 manager-lite</h3>
                                <p className="mt-2 text-sm text-slate-600 text-pretty">
                                    not passed、趋势、重复 blocker、证据不足分布和 manager-lite 名单都从 projection-backed analytics 读真实统计。
                                </p>
                            </div>
                            <Database className="w-5 h-5 text-blue-600" />
                        </div>
                        <Link href="/admin/analytics" className="mt-4 inline-flex text-sm font-medium text-blue-600 hover:text-blue-700">
                            进入数据分析
                        </Link>
                    </GlassCard>

                    <GlassCard className="p-5 border border-white/80 bg-white/80">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h3 className="text-base font-bold text-slate-900">系统日志与后端状态</h3>
                                <p className="mt-2 text-sm text-slate-600 text-pretty">
                                    需要看系统侧证据时，直接回到日志与后端健康信号，而不是留在首页消费示意控制台或未接入告警。
                                </p>
                            </div>
                            <Server className="w-5 h-5 text-blue-600" />
                        </div>
                        <Link href="/admin/logs" className="mt-4 inline-flex text-sm font-medium text-blue-600 hover:text-blue-700">
                            进入系统日志
                        </Link>
                    </GlassCard>
                </div>
            </GlassCard>

            <GlassCard className="p-6 border border-slate-200/70 bg-slate-50/70">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">待接权威数据的管理面</h2>
                        <p className="mt-2 text-sm text-slate-600 text-pretty">
                            这些区域当前仍然没有统一数据源；首页只保留缺口说明，避免误导主管把草拟 UI 当成已经接通的系统能力。
                        </p>
                    </div>
                    <Badge variant="secondary">待接数据</Badge>
                </div>
                <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <GlassCard className="p-5 border border-dashed border-slate-200 bg-white/80">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h3 className="text-base font-bold text-slate-900">首页动作编排</h3>
                                <p className="mt-2 text-sm text-slate-600 text-pretty">
                                    公告发布、批量动作、配置快捷入口等还没有一条首页级数据源；当前只保留到真实管理面的跳转，当前不提供这些操作流。
                                </p>
                            </div>
                            <Activity className="w-5 h-5 text-slate-400" />
                        </div>
                    </GlassCard>

                    <GlassCard className="p-5 border border-dashed border-slate-200 bg-white/80">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h3 className="text-base font-bold text-slate-900">统一告警与动态</h3>
                                <p className="mt-2 text-sm text-slate-600 text-pretty">
                                    当前仓库还没有一条可直接复用到首页的统一告警 / 动态数据源；如果未来恢复，应先明确事件来源、过滤口径和 operator 响应动作。
                                </p>
                            </div>
                            <Server className="w-5 h-5 text-slate-400" />
                        </div>
                    </GlassCard>

                    <GlassCard className="p-5 border border-dashed border-slate-200 bg-white/80">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h3 className="text-base font-bold text-slate-900">存储与资源遥测</h3>
                                <div className="mt-2 text-2xl font-black text-slate-900">待接真实统计</div>
                                <p className="mt-2 text-sm text-slate-600 text-pretty">
                                    首页当前没有统一的磁盘、对象存储或备份容量数据源；在真实 telemetry 接通之前，这块仅展示入口说明，不展示容量、百分比或扩容建议。
                                </p>
                            </div>
                            <HardDrive className="w-5 h-5 text-slate-400" />
                        </div>
                    </GlassCard>
                </div>
            </GlassCard>

                {/* Right Column: Server Status & Storage */}
                <Dialog>
                    <DialogTrigger asChild>
                        <GlassCard className="lg:col-span-1 p-8 flex flex-col relative overflow-hidden cursor-pointer hover:shadow-lg transition-all group">
                            <h3 className="font-bold text-lg mb-4 z-10 relative text-slate-800">存储使用率</h3>
                            <div className="flex-1 flex items-center justify-center relative z-10 p-4">
                                <div className="text-center space-y-3">
                                    <div className="text-3xl font-black text-slate-800">待接真实统计</div>
                                    <p className="text-sm text-slate-500 text-pretty max-w-xs">
                                        首页当前没有统一的磁盘 / 对象存储遥测 authority，这里先保留为 inventory，避免继续伪装容量和使用率。
                                    </p>
                                </div>
                            </div>
                            <div className="mt-8 space-y-4 relative z-10 px-4">
                                <div className="flex justify-between text-sm items-center">
                                    <span className="text-slate-500 flex items-center gap-2 font-medium"><div className="w-2.5 h-2.5 rounded-full bg-blue-500 shadow-[0_0_8px_#3b82f6]" /> 当前状态</span>
                                    <span className="font-bold text-slate-800">待接真实存储统计</span>
                                </div>
                                <div className="flex justify-between text-sm items-center">
                                    <span className="text-slate-500 flex items-center gap-2 font-medium"><div className="w-2.5 h-2.5 rounded-full bg-slate-300" /> 后续处理</span>
                                    <span className="font-bold text-slate-800">明确指标来源后再恢复</span>
                                </div>
                            </div>
                        </GlassCard>
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>存储管理 truth surface 盘点</DialogTitle>
                            <DialogDescription>当前 admin 首页不再展示伪造的存储百分比和容量。</DialogDescription>
                        </DialogHeader>
                        <div className="py-6 space-y-4">
                            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 text-pretty">
                                目前仓库里没有一条已经接到 admin 首页的统一存储 telemetry：本地磁盘、对象存储、备份容量仍需要明确来自哪条基础设施指标或运维报告。
                            </div>
                            <div className="rounded-xl border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500 text-pretty">
                                在那之前，这里只保留为 inventory 说明，不再给出使用率、剩余空间或扩容建议的假数字。
                            </div>
                        </div>
                        <DialogFooter>
                            <Button className="w-full rounded-full bg-slate-900 text-white">记录为后续 truth surface</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </div>
    );
}
