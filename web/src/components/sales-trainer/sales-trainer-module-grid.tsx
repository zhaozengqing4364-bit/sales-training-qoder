"use client";

import Link from "next/link";
import { FileAudio, GraduationCap, Upload } from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SalesTrainerPath, SalesTrainerUnit } from "@/lib/api/types";
import {
    MODULE_SUGGESTED_ORDER_HINT,
    buildModuleViews,
} from "@/lib/sales-trainer/module-path";

interface SalesTrainerModuleGridProps {
    path: SalesTrainerPath;
    unitsById: Map<string, SalesTrainerUnit>;
}

const MODULE_ICONS = {
    ppt: Upload,
    visit_prep: GraduationCap,
    pyramid: FileAudio,
} as const;

export function SalesTrainerModuleGrid({ path, unitsById }: SalesTrainerModuleGridProps) {
    const modules = buildModuleViews(path, unitsById);

    return (
        <div className="space-y-4">
            <p className="text-sm text-slate-500">{MODULE_SUGGESTED_ORDER_HINT}</p>
            <div className="grid gap-4 lg:grid-cols-3">
                {modules.map((module) => {
                    const Icon = MODULE_ICONS[module.key];
                    return (
                        <GlassCard key={module.key} className="flex h-full flex-col gap-4 p-6">
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900 text-white">
                                    <Icon className="h-5 w-5" aria-hidden />
                                </div>
                                <Badge className="bg-slate-100 text-slate-600">{module.orderLabel}</Badge>
                            </div>
                            <div className="flex-1 space-y-2">
                                <h3 className="text-xl font-black text-slate-900">{module.title}</h3>
                                <p className="text-sm leading-6 text-slate-500">{module.description}</p>
                            </div>
                            <div className="flex flex-col gap-2">
                                {module.key === "ppt" && module.pptUploadHref ? (
                                    <Link href={module.pptUploadHref}>
                                        <Button className="w-full rounded-full bg-slate-900 text-white">
                                            上传 PPT 讲解录音
                                        </Button>
                                    </Link>
                                ) : null}
                                {module.key === "visit_prep" && module.learnHubHref ? (
                                    <Link href={module.learnHubHref}>
                                        <Button className="w-full rounded-full bg-slate-900 text-white">
                                            阅读学习
                                        </Button>
                                    </Link>
                                ) : null}
                                {module.key === "pyramid"
                                    ? module.audioOptions.map((option) => (
                                        <Link key={option.level.unit_id} href={option.level.target_path}>
                                            <Button
                                                variant="outline"
                                                className="w-full rounded-full border-slate-200"
                                            >
                                                {option.durationLabel}
                                            </Button>
                                        </Link>
                                    ))
                                    : null}
                            </div>
                        </GlassCard>
                    );
                })}
            </div>
        </div>
    );
}
