"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
    AlertTriangle,
    CheckCircle2,
    ClipboardCheck,
    Wrench,
} from "lucide-react";

import {
    issueActionLabel,
    moduleAvailabilityLabel,
    remediationLabel,
    statusCopy,
} from "@/components/admin/sales-trainer/path-config-center-copy";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import type { NewcomerConfigModuleSummary } from "@/lib/sales-trainer/config-center";

interface PathConfigModuleCardProps {
    readonly editor?: ReactNode;
    readonly module: NewcomerConfigModuleSummary;
    readonly isFocused: boolean;
}

export function PathConfigModuleCard({ editor, module, isFocused }: PathConfigModuleCardProps) {
    const copy = statusCopy(module.status);
    return (
        <GlassCard
            className={`flex min-h-[320px] flex-col gap-5 p-5 ${isFocused ? "border-blue-300 bg-blue-50/70 ring-2 ring-blue-100" : ""}`}
            role={isFocused ? "region" : undefined}
            aria-label={isFocused ? `正在配置 ${module.title}` : undefined}
        >
            <div className="flex items-start justify-between gap-3">
                <div>
                    <p className="text-xs font-bold text-slate-400">{module.orderLabel}</p>
                    <h2 className="mt-1 text-xl font-black text-slate-900">{module.title}</h2>
                    <p className="mt-2 text-sm leading-6 text-slate-500">{module.description}</p>
                </div>
                <Badge className={copy.className}>{copy.label}</Badge>
            </div>

            <div className="rounded-2xl bg-slate-50 p-4">
                <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
                    <ClipboardCheck className="h-4 w-4" />
                    当前绑定
                </div>
                <div className="mt-3 space-y-2">
                    {module.bindings.map((binding) => (
                        <p key={binding} className="text-sm text-slate-600">{binding}</p>
                    ))}
                </div>
            </div>

            <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
                    {module.issues.length ? (
                        <AlertTriangle className="h-4 w-4 text-amber-600" />
                    ) : (
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    )}
                    配置诊断
                </div>
                {module.issues.length ? (
                    <ul className="space-y-2">
                        {module.issues.map((issue) => (
                            <li key={`${module.moduleKey}-${issue.code}`} className="flex flex-col gap-2 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-sm text-amber-800 sm:flex-row sm:items-center sm:justify-between">
                                <span>{issue.message}</span>
                                <Link href={issue.href} className="shrink-0 font-semibold text-amber-900 underline">
                                    {issueActionLabel(issue.code)}
                                </Link>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                        当前配置可供学员端使用。
                    </p>
                )}
            </div>

            {editor}

            <div className="mt-auto flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm font-medium text-slate-500">
                    {moduleAvailabilityLabel(module)}
                </p>
                <Button asChild variant="outline" className="rounded-full">
                    <Link href={module.remediationHref}>
                        <Wrench className="mr-2 h-4 w-4" />
                        {remediationLabel(module)}
                    </Link>
                </Button>
            </div>
        </GlassCard>
    );
}
