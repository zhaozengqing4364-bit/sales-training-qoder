"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";

const MODULE_LINKS = [
    { href: "/admin/sales-trainer", label: "工作台" },
    { href: "/admin/sales-trainer/units", label: "训练单元" },
    { href: "/admin/sales-trainer/paths", label: "训练路径" },
    { href: "/admin/sales-trainer/questions", label: "销售题库" },
    { href: "/admin/sales-trainer/score-standards", label: "录音评分标准" },
    { href: "/admin/sales-trainer/audio-submissions", label: "学员录音" },
    { href: "/admin/sales-trainer/score-results", label: "评分结果" },
    { href: "/admin/sales-trainer/settings", label: "配置" },
    { href: "/admin/sales-trainer/operation-logs", label: "操作记录" },
];

interface SalesTrainerAdminModuleNavProps {
    currentPath: string;
}

export function SalesTrainerAdminModuleNav({
    currentPath,
}: SalesTrainerAdminModuleNavProps) {
    return (
        <div className="flex flex-wrap gap-2">
            {MODULE_LINKS.map((item) => {
                const isActive = currentPath === item.href || currentPath.startsWith(`${item.href}/`);
                return (
                    <Link
                        key={item.href}
                        href={item.href}
                        className={cn(
                            "rounded-full px-4 py-2 text-sm font-medium transition-colors",
                            isActive
                                ? "bg-slate-900 text-white"
                                : "bg-white text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                        )}
                    >
                        {item.label}
                    </Link>
                );
            })}
        </div>
    );
}
