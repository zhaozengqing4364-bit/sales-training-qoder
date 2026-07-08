"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ClipboardList } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { GlassCard } from "@/components/ui/glass-card";
import { AUDIO_EVALUATION_SCENARIOS } from "@/lib/sales-trainer/audio-evaluation-scenarios";
import { useSalesTrainerAdminRouteAccess } from "@/lib/sales-trainer/use-admin-route-access";

const AUDIO_MANAGEMENT_SECTIONS = [
    {
        title: "查看全部材料",
        description: "批量检索和维护 PPT、脚本、附件等材料；日常配置优先在具体录音任务内就地完成。",
        href: "/admin/sales-trainer/audio/materials",
    },
    {
        title: "高级管理评分标准",
        description: "批量维护 AI 评分标准和发布版本；日常新建优先在具体录音任务内完成并自动绑定。",
        href: "/admin/sales-trainer/audio/score-standards",
    },
    {
        title: "学员录音",
        description: "查看录音上传、转写状态、重试入口和文件访问。",
        href: "/admin/sales-trainer/audio/submissions",
    },
    {
        title: "评分结果",
        description: "查看录音评分结论、AI 反馈和历史快照。",
        href: "/admin/sales-trainer/audio/results",
    },
] as const;

export default function SalesTrainerAudioManagementPage() {
    const pathname = usePathname();
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="录音管理"
                    description="按前台录音任务组织后台配置。进入任一任务后，可在同一页选择已有资源、缺失时就地新建，并保存发布。"
                    icon={<ClipboardList className="h-7 w-7 text-slate-800" />}
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={routeAccess.capabilities} />}
                />
            )}
        >
            {routeAccess.isLoading ? (
                <GlassCard className="p-8 text-center text-sm text-slate-500">
                    正在校验录音管理权限...
                </GlassCard>
            ) : null}

            {routeAccess.denialMessage ? (
                <AdminLoadErrorCard
                    title="录音管理不可访问"
                    description="当前账号没有配置或查看新人训练录音任务的权限。"
                    message={routeAccess.denialMessage}
                    retryLabel="重新检查权限"
                    onRetry={routeAccess.reloadCapabilities}
                />
            ) : null}

            {routeAccess.canAccess ? (
                <>
                    <section className="space-y-3">
                        <div>
                            <h2 className="text-base font-bold text-slate-900">录音任务</h2>
                            <p className="text-sm text-slate-500">
                                每个任务都在同一处管理单元、材料、评分标准和发布状态，主流程不再要求跨页面补配置。
                            </p>
                        </div>
                        <div className="grid gap-4 md:grid-cols-3">
                            {AUDIO_EVALUATION_SCENARIOS.map((scenario) => (
                                <Link key={scenario.scenarioKey} href={`/admin/sales-trainer/audio/${scenario.slug}`}>
                                    <GlassCard className="h-full p-5 transition hover:border-slate-300 hover:bg-white">
                                        <div className="flex items-start justify-between gap-3">
                                            <div>
                                                <p className="text-sm font-semibold text-slate-500">{scenario.orderLabel}</p>
                                                <h3 className="mt-1 text-lg font-black text-slate-950">{scenario.title}</h3>
                                            </div>
                                            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                                                {scenario.materialRequired ? "材料必选" : "材料选配"}
                                            </span>
                                        </div>
                                        <p className="mt-3 text-sm leading-6 text-slate-600">{scenario.description}</p>
                                        <p className="mt-4 text-sm font-semibold text-blue-700">进入录音任务</p>
                                    </GlassCard>
                                </Link>
                            ))}
                        </div>
                    </section>

                    <section className="space-y-3">
                        <div>
                            <h2 className="text-base font-bold text-slate-900">高级管理与查看全部</h2>
                            <p className="text-sm text-slate-500">
                                这些入口保留给批量治理、历史检索和旧书签兼容；配置单个录音任务时优先回到任务页就地完成。
                            </p>
                        </div>
                        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                            {AUDIO_MANAGEMENT_SECTIONS.map((section) => (
                                <Link key={section.href} href={section.href}>
                                    <GlassCard className="h-full p-5 transition hover:border-slate-300 hover:bg-white">
                                        <h3 className="text-lg font-black text-slate-950">{section.title}</h3>
                                        <p className="mt-3 text-sm leading-6 text-slate-600">{section.description}</p>
                                        <p className="mt-4 text-sm font-semibold text-blue-700">进入管理</p>
                                    </GlassCard>
                                </Link>
                            ))}
                        </div>
                    </section>
                </>
            ) : null}
        </AdminIndexShell>
    );
}
