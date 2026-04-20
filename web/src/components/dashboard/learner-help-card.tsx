import Link from "next/link";
import {
    ArrowRight,
    BookOpenCheck,
    FileText,
    History,
    LifeBuoy,
    Mic,
    PanelLeftOpen,
    ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type LearnerHelpContext = "dashboard" | "history" | "practice" | "report";

type LearnerHelpAction = {
    label: string;
    href: string;
};

type LearnerHelpItem = {
    icon: LucideIcon;
    iconClassName: string;
    copy: string;
};

type LearnerHelpCopy = {
    badge: string;
    title: string;
    description: string;
    items: [LearnerHelpItem, LearnerHelpItem];
    primaryAction: LearnerHelpAction;
    secondaryAction?: LearnerHelpAction;
};

const LEARNER_HELP_COPY: Record<LearnerHelpContext, LearnerHelpCopy> = {
    dashboard: {
        badge: "帮助与反馈",
        title: "需要帮助或反馈？",
        description: "统一入口在侧边栏底部的“帮助与反馈”里；手机端先打开左上角菜单。",
        items: [
            {
                icon: PanelLeftOpen,
                iconClassName: "text-blue-600",
                copy: "页面异常、入口缺失或结果不对时，请通过这个统一入口反馈当前页面路径或会话编号。",
            },
            {
                icon: ShieldCheck,
                iconClassName: "text-emerald-600",
                copy: "当前 learner 默认只看到训练、历史、个人中心；运行状态和管理后台只对管理员或支持角色开放。",
            },
        ],
        primaryAction: { label: "去训练大厅", href: "/training" },
        secondaryAction: { label: "查看历史", href: "/history" },
    },
    history: {
        badge: "历史页帮助",
        title: "历史记录看不全时还能做什么？",
        description: "历史页只展示已同步的训练证据；统计或趋势短暂不可用时，列表和复练入口会尽量保留。",
        items: [
            {
                icon: History,
                iconClassName: "text-blue-600",
                copy: "如果历史列表为空，先完成一次可评估训练；证据不足记录不会被包装成复练榜或成就。",
            },
            {
                icon: ShieldCheck,
                iconClassName: "text-emerald-600",
                copy: "如果某条报告缺少入口，请带会话编号反馈；不要截图上传隐私信息或他人训练内容。",
            },
        ],
        primaryAction: { label: "开始训练", href: "/training" },
        secondaryAction: { label: "回到首页", href: "/" },
    },
    practice: {
        badge: "练习中帮助",
        title: "练习中遇到异常怎么办？",
        description: "练习页会优先保留当前对话状态；连接、麦克风、留痕或会话状态异常会在故障面板中分开提示。",
        items: [
            {
                icon: Mic,
                iconClassName: "text-blue-600",
                copy: "麦克风或连接异常时，先按故障面板动作重试；仍可阅读右侧行动卡，准备下一轮表达。",
            },
            {
                icon: ShieldCheck,
                iconClassName: "text-emerald-600",
                copy: "如果需要反馈，请记录当前会话编号和页面路径；系统不会要求你提供后台权限或部署信息。",
            },
        ],
        primaryAction: { label: "返回训练大厅", href: "/training" },
        secondaryAction: { label: "查看历史", href: "/history" },
    },
    report: {
        badge: "报告页帮助",
        title: "报告看不懂或证据不足时怎么办？",
        description: "报告页只解释当前会话已有证据；证据不足会直接说明影响范围，而不是把缺失内容伪装成低分。",
        items: [
            {
                icon: FileText,
                iconClassName: "text-blue-600",
                copy: "先看主问题、下一轮目标和高光复习清单；如果报告缺少再练配置，可回训练页重新选择。",
            },
            {
                icon: BookOpenCheck,
                iconClassName: "text-emerald-600",
                copy: "反馈报告问题时，请附上会话编号、报告页路径和你认为不准确的段落，方便定位证据链。",
            },
        ],
        primaryAction: { label: "去训练大厅", href: "/training" },
        secondaryAction: { label: "查看历史", href: "/history" },
    },
};

export function LearnerHelpCard({
    className,
    context = "dashboard",
}: {
    className?: string;
    context?: LearnerHelpContext;
}) {
    const copy = LEARNER_HELP_COPY[context];

    return (
        <GlassCard className={cn("p-5 bg-white/80 border-none shadow-sm ring-1 ring-slate-100", className)}>
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="space-y-2">
                    <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-slate-500">
                        <LifeBuoy className="h-3.5 w-3.5" />
                        {copy.badge}
                    </div>
                    <div>
                        <h2 className="text-lg font-bold text-slate-900">{copy.title}</h2>
                        <p className="mt-1 text-sm leading-6 text-slate-600">
                            {copy.description}
                        </p>
                    </div>
                    <div className="flex flex-wrap gap-2 pt-1">
                        <Button asChild size="sm" className="rounded-full">
                            <Link href={copy.primaryAction.href}>
                                {copy.primaryAction.label}
                                <ArrowRight className="ml-1 h-3.5 w-3.5" />
                            </Link>
                        </Button>
                        {copy.secondaryAction && (
                            <Button asChild size="sm" variant="outline" className="rounded-full bg-white/70">
                                <Link href={copy.secondaryAction.href}>
                                    {copy.secondaryAction.label}
                                </Link>
                            </Button>
                        )}
                    </div>
                </div>

                <div className="grid gap-3 text-sm text-slate-600 md:max-w-[28rem]">
                    {copy.items.map((item) => {
                        const Icon = item.icon;
                        return (
                            <div key={item.copy} className="flex gap-3 rounded-2xl border border-slate-100 bg-slate-50/80 px-3 py-3">
                                <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", item.iconClassName)} />
                                <p>{item.copy}</p>
                            </div>
                        );
                    })}
                </div>
            </div>
        </GlassCard>
    );
}
