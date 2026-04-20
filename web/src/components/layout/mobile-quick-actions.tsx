"use client";

import Link from "next/link";
import { History, PlayCircle } from "lucide-react";

import { LearnerHelpEntry } from "@/components/layout/learner-help-entry";
import { cn } from "@/lib/utils";

type MobileQuickActionsProps = {
    primaryLabel?: string;
    primaryHref?: string;
    placement?: "default" | "practice";
    className?: string;
};

const placementClassNames: Record<NonNullable<MobileQuickActionsProps["placement"]>, string> = {
    default: "bottom-3",
    practice: "bottom-[7.25rem]",
};

export function MobileQuickActions({
    primaryLabel = "继续训练",
    primaryHref = "/training",
    placement = "default",
    className,
}: MobileQuickActionsProps) {
    return (
        <nav
            aria-label="移动快捷入口"
            className={cn(
                "md:hidden fixed inset-x-3 z-40 rounded-[1.75rem] border border-white/70 bg-white/90 p-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))] shadow-[0_18px_50px_rgba(15,23,42,0.16)] backdrop-blur-2xl",
                placementClassNames[placement],
                className,
            )}
        >
            <div className="grid grid-cols-3 gap-2">
                <Link
                    href={primaryHref}
                    className="flex h-11 items-center justify-center gap-1.5 rounded-2xl bg-slate-900 px-2 text-xs font-bold text-white shadow-sm"
                >
                    <PlayCircle className="h-4 w-4" />
                    <span>{primaryLabel}</span>
                </Link>
                <Link
                    href="/history"
                    className="flex h-11 items-center justify-center gap-1.5 rounded-2xl border border-slate-200 bg-white/80 px-2 text-xs font-bold text-slate-700 shadow-sm"
                >
                    <History className="h-4 w-4" />
                    <span>历史</span>
                </Link>
                <LearnerHelpEntry
                    className="h-11 justify-center rounded-2xl border-slate-200 bg-white/80 px-2 text-xs font-bold text-slate-700 shadow-sm"
                />
            </div>
            <p className="sr-only">
                手机端无需打开抽屉即可进入训练、历史和帮助与反馈。
            </p>
        </nav>
    );
}
