
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

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <GlassCard className="p-8 border border-slate-200/70">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <div className="text-slate-500 text-xs font-bold uppercase tracking-widest mb-3">总用户数</div>
                            <div className="text-3xl font-black text-slate-900 mb-4 tracking-tight">待接真实统计</div>
                            <p className="text-sm text-slate-500 text-pretty">
                                首页当前没有统一的总用户 authority；如果恢复该卡片，应先明确是复用用户集合还是 admin analytics 的 cohort 统计。
                            </p>
                        </div>
                        <Users className="w-10 h-10 text-slate-300" />
                    </div>
                    <div className="mt-5">
                        <Link href="/admin/users" className="text-sm font-medium text-blue-600 hover:text-blue-700">
                            进入用户管理
                        </Link>
                    </div>
                </GlassCard>

                <GlassCard className="p-8 border border-slate-200/70">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <div className="text-slate-500 text-xs font-bold uppercase tracking-widest mb-3">活跃会话</div>
                            <div className="text-3xl font-black text-slate-900 mb-4 tracking-tight">待接真实统计</div>
                            <p className="text-sm text-slate-500 text-pretty">
                                首页不再本地维护活跃会话示意值；真实判断应回到 admin analytics 的 operating pack、趋势页或 support/runtime 相关观测面。
                            </p>
                        </div>
                        <Activity className="w-10 h-10 text-slate-300" />
                    </div>
                    <div className="mt-5">
                        <Link href="/admin/analytics" className="text-sm font-medium text-blue-600 hover:text-blue-700">
                            进入数据分析
                        </Link>
                    </div>
                </GlassCard>

                <GlassCard className="p-8 border border-slate-200/70">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <div className="text-slate-500 text-xs font-bold uppercase tracking-widest mb-3">系统健康度</div>
                            <div className={`text-2xl font-bold ${liveMetrics.backendStatus === "online" ? "text-emerald-600" : liveMetrics.backendStatus === "offline" ? "text-rose-600" : "text-slate-500"}`}>
                                {liveMetrics.backendStatus === "online" ? "仅后端状态已接通" : liveMetrics.backendStatus === "offline" ? "后端离线" : "状态未知"}
                            </div>
                            <p className="mt-4 text-sm text-slate-500 text-pretty">
                                首页目前只保留后端在线 / 离线这一条真实信号；CPU、内存、数据库延迟与主机资源仍未接入统一 authority。
                            </p>
                        </div>
                        <Server className="w-10 h-10 text-slate-300" />
                    </div>
                    <div className="mt-5">
                        <Link href="/admin/logs" className="text-sm font-medium text-blue-600 hover:text-blue-700">
                            进入系统日志
                        </Link>
                    </div>
                </GlassCard>
            </div>

            <GlassCard className="p-6 border border-emerald-100 bg-emerald-50/60">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">当前真实管理入口</h2>
                        <p className="mt-2 text-sm text-slate-700 text-pretty">
                            直接进入当前已接真实 authority 的管理面，不再在首页伪装表单、日志控制台或自动告警。
                        </p>
                    </div>
                    <Badge variant="green">live authority only</Badge>
                </div>
                <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <GlassCard className="p-5 border border-white/80 bg-white/80">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h3 className="text-base font-bold text-slate-900">用户管理与主管详情</h3>
                                <p className="mt-2 text-sm text-slate-600 text-pretty">
                                    用户列表、详情页、主管重点与 intervention 闭环都建立在当前真实用户集合和统一训练证据上。
                                </p>
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
                                    需要看系统侧证据时，直接回到日志与后端健康信号，而不是留在首页消费示意控制台或虚构告警。
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
                        <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">仍为 inventory 的管理面</h2>
                        <p className="mt-2 text-sm text-slate-600 text-pretty">
                            这些区域当前仍然没有统一 authority；首页只保留缺口说明，避免误导主管把草拟 UI 当成已经接通的系统能力。
                        </p>
                    </div>
                    <Badge variant="secondary">inventory only</Badge>
                </div>
                <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <GlassCard className="p-5 border border-dashed border-slate-200 bg-white/80">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h3 className="text-base font-bold text-slate-900">首页动作编排</h3>
                                <p className="mt-2 text-sm text-slate-600 text-pretty">
                                    公告发布、批量动作、配置快捷入口等还没有一条首页级 authority；当前只保留到真实管理面的跳转，不再假装本页已经具备这些操作流。
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
                                    当前仓库还没有一条可直接复用到首页的统一告警 / 动态 authority；如果未来恢复，应先明确事件来源、过滤口径和 operator 响应动作。
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
                                    首页当前没有统一的磁盘、对象存储或备份容量 authority；在真实 telemetry 接通之前，这块继续保留为 inventory，不再展示容量、百分比或扩容建议。
                                </p>
                            </div>
                            <HardDrive className="w-5 h-5 text-slate-400" />
                        </div>
                    </GlassCard>
                </div>
            </GlassCard>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <GlassCard className="p-6 border border-slate-200/70">
                    <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">首页后续 truth surface</h2>
                    <p className="mt-3 text-sm text-slate-600 text-pretty">
                        若后续要恢复首页级组织运营卡片，必须先明确复用哪条 backend authority，并让 admin home 只做 read-side 展示，不能再在本地维护第二套统计口径。
                    </p>
                    <ul className="mt-4 space-y-2 text-sm text-slate-600 list-disc pl-5">
                        <li>组织侧统计优先复用 <code>/admin/users</code> 或 <code>/admin/analytics</code> 的真实集合。</li>
                        <li>系统侧状态优先复用 <code>api.internal.health()</code>、日志页和后续统一 runtime surfaces。</li>
                        <li>主管视图优先复用 manager-lite、用户详情连续变化和 intervention 闭环。</li>
                    </ul>
                </GlassCard>

                <GlassCard className="p-6 border border-slate-200/70">
                    <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">首页不再承担的职责</h2>
                    <p className="mt-3 text-sm text-slate-600 text-pretty">
                        首页只负责显示当前已接通的极少数 live authority 与尚未 truthify 的缺口，不再伪装实时运营、配置控制台、动态流或告警面已经建成。
                    </p>
                    <div className="mt-5 flex flex-wrap gap-3">
                        <Badge variant="secondary">不再展示示意日志</Badge>
                        <Badge variant="secondary">不再展示示意告警</Badge>
                        <Badge variant="secondary">不再展示示意配置</Badge>
                        <Badge variant="secondary">不再展示示意动态</Badge>
                    </div>
                    <div className="mt-5">
                        <Link href="/admin/analytics">
                            <Button className="rounded-full bg-slate-900 text-white">查看真实主管统计面</Button>
                        </Link>
                    </div>
                </GlassCard>
            </div>
        </div>
    );
}
