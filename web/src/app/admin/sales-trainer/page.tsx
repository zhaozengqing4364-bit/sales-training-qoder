"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart3, Bot, FileText, Milestone, Mic, ScrollText, Settings, Target } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { GlassCard } from "@/components/ui/glass-card";

const WORKBENCH_LINKS = [
    { href: "/admin/sales-trainer/units", label: "模块单元", icon: Target },
    { href: "/admin/sales-trainer/paths", label: "路径配置", icon: Milestone },
    { href: "/admin/sales-trainer/ai-coach", label: "AI 教练配置", icon: Bot },
    { href: "/admin/sales-trainer/questions", label: "题库管理", icon: FileText },
    { href: "/admin/sales-trainer/score-standards", label: "录音评分标准", icon: Mic },
    { href: "/admin/sales-trainer/audio-submissions", label: "学员录音", icon: Activity },
    { href: "/admin/sales-trainer/score-results", label: "评分结果", icon: BarChart3 },
    { href: "/admin/sales-trainer/settings", label: "配置", icon: Settings },
    { href: "/admin/sales-trainer/operation-logs", label: "操作记录", icon: ScrollText },
];

export default function SalesTrainerWorkbenchPage() {
    const pathname = usePathname();

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="新人训练路径工作台"
                    description="新人训练路径的模块、文章、考卷、录音评分、配置健康和操作记录集中在这里管理。"
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
                />
            )}
        >
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {WORKBENCH_LINKS.map((item) => {
                    const Icon = item.icon;
                    return (
                        <Link key={item.href} href={item.href}>
                            <GlassCard className="flex items-center gap-4 p-5 transition hover:border-slate-300 hover:bg-white">
                                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900 text-white">
                                    <Icon className="h-5 w-5" />
                                </span>
                                <span className="font-semibold text-slate-900">{item.label}</span>
                            </GlassCard>
                        </Link>
                    );
                })}
            </div>
        </AdminIndexShell>
    );
}
