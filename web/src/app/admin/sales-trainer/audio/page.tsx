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
        title: "材料",
        description: "管理 PPT、脚本、附件等录音任务材料；任务只绑定已发布版本。",
        href: "/admin/sales-trainer/audio/materials",
    },
    {
        title: "评分标准",
        description: "管理 AI 评分 prompt、学员可见 rubric 和发布版本。",
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
                    description="按前台录音任务组织后台配置。PPT 讲解、公司产品 Demo、金字塔演讲复用同一套上传、转写和 AI 评分能力。"
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
                                每个任务都在同一处管理单元、材料、评分标准和发布状态。
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
                            <h2 className="text-base font-bold text-slate-900">配套管理</h2>
                            <p className="text-sm text-slate-500">
                                和录音任务配套的材料、评分标准、提交记录和评分结果统一放在录音管理内。
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
