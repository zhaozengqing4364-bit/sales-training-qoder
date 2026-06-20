"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";
import { getSalesTrainerAdminContextNavGroup } from "@/lib/sales-trainer/routes";

export { SALES_TRAINER_ADMIN_WORKBENCH_LINKS } from "@/lib/sales-trainer/routes";

interface SalesTrainerAdminModuleNavProps {
    currentPath: string;
}

export function SalesTrainerAdminModuleNav({
    currentPath,
}: SalesTrainerAdminModuleNavProps) {
    const group = getSalesTrainerAdminContextNavGroup(currentPath);

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
