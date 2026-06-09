"use client";

import Link from "next/link";
import { AlertTriangle, FileAudio, GraduationCap, Upload, Bot } from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SalesTrainerPath, SalesTrainerUnit } from "@/lib/api/types";
import { buildModuleViews } from "@/lib/sales-trainer/module-path";

interface SalesTrainerModuleGridProps {
    path: SalesTrainerPath;
    unitsById: Map<string, SalesTrainerUnit>;
}

const MODULE_ICONS = {
    ppt: Upload,
    business_skills: GraduationCap,
    elevator_pitch: FileAudio,
    realtime_practice: Bot,
} as const;

export function SalesTrainerModuleGrid({ path, unitsById }: SalesTrainerModuleGridProps) {
    const modules = buildModuleViews(path, unitsById);

    if (modules.length === 0) {
        return (
            <GlassCard className="space-y-4 border-amber-100 bg-amber-50 p-6">
                <div className="flex items-start gap-3">
                    <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-700" aria-hidden />
                    <div className="space-y-2">
                        <h3 className="text-lg font-black text-amber-950">新人训练路径暂不可用</h3>
                        <p className="max-w-2xl text-sm leading-6 text-amber-800">
                            当前路径缺少后台模块配置。请管理员到新人训练路径配置中心检查模块启用、绑定内容和发布状态。
                        </p>
                    </div>
                </div>
                <Button asChild variant="outline" className="rounded-full border-amber-200 bg-white text-amber-900">
                    <Link href="/admin/sales-trainer/paths">
                        去配置中心处理
                    </Link>
                </Button>
            </GlassCard>
        );
    }

    return (
        <div className="space-y-4">
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
                                    <Button asChild className="w-full rounded-full bg-slate-900 text-white">
                                        <Link href={module.pptUploadHref}>
                                            {module.primaryActionLabel ?? "上传 PPT 讲解录音"}
                                        </Link>
                                    </Button>
                                ) : null}
                                {module.key === "business_skills" && module.learnHref ? (
                                    <Button asChild className="w-full rounded-full bg-slate-900 text-white">
                                        <Link href={module.learnHref}>
                                            {module.primaryActionLabel ?? "开始学习"}
                                        </Link>
                                    </Button>
                                ) : null}
                                {module.key === "elevator_pitch"
                                    ? module.audioOptions.map((option) => (
                                        <Button
                                            key={option.level.unit_id}
                                            asChild
                                            variant="outline"
                                            className="w-full rounded-full border-slate-200"
                                        >
                                            <Link href={option.level.target_path}>
                                                {option.durationLabel}
                                            </Link>
                                        </Button>
                                    ))
                                    : null}
                                {module.disabled ? (
                                    <Button className="w-full rounded-full" variant="outline" disabled>
                                        {module.disabledReason ?? "暂不开放"}
                                    </Button>
                                ) : null}
                            </div>
                        </GlassCard>
                    );
                })}
            </div>
        </div>
    );
}
