"use client";

import Link from "next/link";
import {
    BookOpen,
    ClipboardList,
    FileText,
    Headphones,
    LayoutDashboard,
    Library,
    ListChecks,
    Mic,
    Route,
    ScrollText,
    Settings,
    SlidersHorizontal,
    Tags,
    type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

interface ContextNavItem {
    readonly href: string;
    readonly icon: LucideIcon;
    readonly label: string;
}

interface ContextNavGroup {
    readonly items: readonly ContextNavItem[];
    readonly label: string;
    readonly root: string;
}

const CONTEXT_NAV_GROUPS = [
    {
        root: "/admin/sales-trainer/questions",
        label: "题库管理",
        items: [
            { href: "/admin/sales-trainer/questions", label: "题目清单", icon: BookOpen },
            { href: "/admin/sales-trainer/questions/categories", label: "分类管理", icon: Tags },
        ],
    },
    {
        root: "/admin/sales-trainer/score-standards",
        label: "录音评分标准",
        items: [
            { href: "/admin/sales-trainer/score-standards", label: "标准列表", icon: SlidersHorizontal },
        ],
    },
    {
        root: "/admin/sales-trainer/paths",
        label: "路径配置",
        items: [{ href: "/admin/sales-trainer/paths", label: "路径配置", icon: Route }],
    },
    {
        root: "/admin/sales-trainer/articles",
        label: "商务技巧文章",
        items: [{ href: "/admin/sales-trainer/articles", label: "文章绑定", icon: FileText }],
    },
    {
        root: "/admin/sales-trainer/papers",
        label: "考卷管理",
        items: [{ href: "/admin/sales-trainer/papers", label: "考卷管理", icon: ClipboardList }],
    },
    {
        root: "/admin/sales-trainer/materials",
        label: "材料库",
        items: [{ href: "/admin/sales-trainer/materials", label: "材料库", icon: Library }],
    },
    {
        root: "/admin/sales-trainer/training-records",
        label: "训练记录",
        items: [{ href: "/admin/sales-trainer/training-records", label: "训练记录", icon: ListChecks }],
    },
    {
        root: "/admin/sales-trainer/audio-submissions",
        label: "学员录音",
        items: [{ href: "/admin/sales-trainer/audio-submissions", label: "录音列表", icon: Mic }],
    },
    {
        root: "/admin/sales-trainer/score-results",
        label: "评分结果",
        items: [{ href: "/admin/sales-trainer/score-results", label: "评分结果", icon: Headphones }],
    },
    {
        root: "/admin/sales-trainer/settings",
        label: "配置",
        items: [{ href: "/admin/sales-trainer/settings", label: "配置健康", icon: Settings }],
    },
    {
        root: "/admin/sales-trainer/operation-logs",
        label: "操作日志",
        items: [{ href: "/admin/sales-trainer/operation-logs", label: "操作日志", icon: ScrollText }],
    },
    {
        root: "/admin/sales-trainer",
        label: "工作台",
        items: [{ href: "/admin/sales-trainer", label: "工作台", icon: LayoutDashboard }],
    },
] as const satisfies readonly ContextNavGroup[];

interface SalesTrainerAdminModuleNavProps {
    currentPath: string;
}

function isPathInGroup(currentPath: string, root: string): boolean {
    if (root === "/admin/sales-trainer") {
        return currentPath === root;
    }
    return currentPath === root || currentPath.startsWith(`${root}/`);
}

function getContextNavGroup(currentPath: string): ContextNavGroup {
    return CONTEXT_NAV_GROUPS.find((group) => isPathInGroup(currentPath, group.root))
        ?? CONTEXT_NAV_GROUPS[CONTEXT_NAV_GROUPS.length - 1];
}

export function SalesTrainerAdminModuleNav({
    currentPath,
}: SalesTrainerAdminModuleNavProps) {
    const group = getContextNavGroup(currentPath);

    if (group.items.length < 2) {
        return null;
    }

    return (
        <nav
            aria-label={`${group.label}模块内导航`}
            className="w-full overflow-x-auto rounded-2xl border border-slate-200/70 bg-white/80 p-1 shadow-sm"
        >
            <div className="flex min-w-max items-center gap-1">
                <span className="px-3 text-xs font-semibold text-slate-400">
                    {group.label}
                </span>
                {group.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = currentPath === item.href;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "inline-flex items-center gap-2 whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                                isActive
                                    ? "bg-slate-900 text-white"
                                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                            )}
                        >
                            <Icon className="h-4 w-4" aria-hidden />
                            {item.label}
                        </Link>
                    );
                })}
            </div>
        </nav>
    );
}
