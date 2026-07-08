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

const LEARNING_TOPIC_TASKS = [
    {
        title: "商务礼仪专题",
        description: "学习专题得分只展示，不阻塞后续训练任务；后续销售技巧、客户异议可按同一层级扩展。",
        href: "/admin/sales-trainer/articles",
    },
] as const;

export default function SalesTrainerTrainingTasksPage() {
    const pathname = usePathname();
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="训练任务"
                    description="按管理员要治理的训练任务组织后台。录音评测是能力，PPT 讲解、公司产品 Demo 和金字塔演讲是同级场景。"
                    icon={<ClipboardList className="h-7 w-7 text-slate-800" />}
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={routeAccess.capabilities} />}
                />
            )}
        >
            {routeAccess.denialMessage ? (
                <AdminLoadErrorCard
                    title="训练任务不可访问"
                    description="当前账号没有配置新人训练任务的权限。"
                    message={routeAccess.denialMessage}
                    retryLabel="重新检查权限"
                    onRetry={routeAccess.reloadCapabilities}
                />
            ) : null}

            {!routeAccess.denialMessage ? (
                <>
                    <section className="space-y-3">
                        <div>
                            <h2 className="text-base font-bold text-slate-900">录音评测场景</h2>
                            <p className="text-sm text-slate-500">
                                这些任务复用同一套上传、转写和 AI 评分能力，区别在材料、评分标准和完成规则。
                            </p>
                        </div>
                        <div className="grid gap-4 md:grid-cols-3">
                            {AUDIO_EVALUATION_SCENARIOS.map((scenario) => (
                                <Link key={scenario.scenarioKey} href={`/admin/sales-trainer/training-tasks/${scenario.slug}`}>
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
                                        <p className="mt-4 text-sm font-semibold text-blue-700">进入任务治理</p>
                                    </GlassCard>
                                </Link>
                            ))}
                        </div>
                    </section>

                    <section className="space-y-3">
                        <div>
                            <h2 className="text-base font-bold text-slate-900">学习专题</h2>
                            <p className="text-sm text-slate-500">
                                学习专题独立于必修路径阻塞逻辑，得分用于展示和复盘。
                            </p>
                        </div>
                        <div className="grid gap-4 md:grid-cols-2">
                            {LEARNING_TOPIC_TASKS.map((task) => (
                                <Link key={task.href} href={task.href}>
                                    <GlassCard className="h-full p-5 transition hover:border-slate-300 hover:bg-white">
                                        <h3 className="text-lg font-black text-slate-950">{task.title}</h3>
                                        <p className="mt-3 text-sm leading-6 text-slate-600">{task.description}</p>
                                        <p className="mt-4 text-sm font-semibold text-blue-700">进入专题治理</p>
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
