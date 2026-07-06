"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
    AlertTriangle,
    CheckCircle2,
    Eye,
    History,
    RefreshCw,
    XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { PathConfigMetricCard } from "@/components/admin/sales-trainer/path-config-metric-card";
import { PathConfigModuleCard } from "@/components/admin/sales-trainer/path-config-module-card";
import { PathConfigRevisionHistory } from "@/components/admin/sales-trainer/path-config-revision-history";
import {
    learnerPreviewStatusLabel,
    statusCopy,
} from "@/components/admin/sales-trainer/path-config-center-copy";
import type {
    NewcomerConfigCenterModel,
    NewcomerConfigModuleSummary,
    NewcomerOperationalCheck,
} from "@/lib/sales-trainer/config-center";

interface PathConfigCenterProps {
    readonly model: NewcomerConfigCenterModel;
    readonly focusedModuleKey?: string | null;
    readonly isRefreshing: boolean;
    readonly isMutating?: boolean;
    readonly changeReason?: string;
    readonly onRefresh: () => void;
    readonly onChangeReason?: (reason: string) => void;
    readonly onSaveCurrentRevision?: () => void;
    readonly onPublishWorkingRevision?: () => void;
    readonly onRollbackRevision?: (revisionId: string, reason: string) => void;
    readonly renderModuleEditor?: (module: NewcomerConfigModuleSummary) => ReactNode;
}

export function PathConfigCenter({
    model,
    focusedModuleKey = null,
    isRefreshing,
    isMutating = false,
    changeReason = "",
    onRefresh,
    onChangeReason,
    onSaveCurrentRevision,
    onPublishWorkingRevision,
    onRollbackRevision,
    renderModuleEditor,
}: PathConfigCenterProps) {
    const focusedModule = model.modules.find((module) => module.moduleKey === focusedModuleKey) ?? null;
    const hasChangeReason = changeReason.trim().length > 0;

    return (
        <div className="space-y-6">
            <section className="grid gap-3 md:grid-cols-4">
                <PathConfigMetricCard label="可发布模块" value={model.summary.readyCount} />
                <PathConfigMetricCard label="缺配置模块" value={model.summary.missingCount} tone="danger" />
                <PathConfigMetricCard label="需确认模块" value={model.summary.warningCount} tone="warning" />
                <PathConfigMetricCard label="占位模块" value={model.summary.disabledCount} />
            </section>

            {focusedModule ? (
                <GlassCard className="border-blue-100 bg-blue-50/70 p-4 text-sm text-blue-900">
                    <p className="font-bold">正在配置：{focusedModule.title}</p>
                    <p className="mt-1 text-blue-800">
                        请在对应关卡卡片里补齐绑定，保存为待发布修订后再发布生效。
                    </p>
                </GlassCard>
            ) : null}

            <GlassCard className="p-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <p className="text-xs font-bold uppercase text-slate-400">发布治理</p>
                        <h2 className="mt-1 text-xl font-black text-slate-900">
                            编辑将生成新修订，只影响后续学员
                        </h2>
                        <p className="mt-1 max-w-3xl text-sm text-slate-500">
                            配置中心当前读取{model.governance.sourceLabel}。编辑会保存为新的待发布修订，发布后更新当前生效指针；旧学员记录继续使用当时快照，回滚也只影响未来学员。
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-slate-600">
                            <span className="rounded-full bg-slate-100 px-3 py-1">{model.governance.activeRevisionLabel}</span>
                            <span className="rounded-full bg-slate-100 px-3 py-1">{model.governance.workingRevisionLabel}</span>
                            <span className="rounded-full bg-slate-100 px-3 py-1">历史版本 {model.governance.revisionCount}</span>
                            {model.governance.fallbackApplied ? (
                                <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-800">
                                    fallback_applied=true / {model.governance.fallbackReason ?? "unknown"}
                                </span>
                            ) : null}
                        </div>
                        {model.governance.publishPreview || model.governance.publishPreviewLoadError ? (
                            <div className="mt-4 rounded-2xl border border-slate-100 bg-slate-50 p-3 text-sm">
                                <div className="flex items-center gap-2 font-bold text-slate-900">
                                    {model.governance.publishPreviewLoadError ? (
                                        <AlertTriangle className="h-4 w-4 text-amber-600" />
                                    ) : (
                                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                                    )}
                                    发布预览
                                </div>
                                {model.governance.publishPreview ? (
                                    <p className="mt-2 text-slate-600">
                                        {model.governance.publishPreview.risk_level} 风险，
                                        只影响后续学员；
                                        回滚{rollbackAvailabilityLabel(model.governance.publishPreview.rollback_hint)}。
                                    </p>
                                ) : null}
                                {model.governance.publishPreviewLoadError ? (
                                    <p className="mt-2 text-amber-700">
                                        发布预览失败：{model.governance.publishPreviewLoadError}
                                    </p>
                                ) : null}
                            </div>
                        ) : null}
                    </div>
                    <div className="flex w-full flex-col gap-3 lg:max-w-sm">
                        <div>
                            <label
                                className="text-xs font-bold uppercase text-slate-400"
                                htmlFor="path-config-change-reason"
                            >
                                本次变更说明
                            </label>
                            <Input
                                id="path-config-change-reason"
                                value={changeReason}
                                placeholder="例如：更新商务技巧考卷绑定"
                                disabled={isMutating || !onChangeReason}
                                onChange={(event) => onChangeReason?.(event.target.value)}
                            />
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Button
                                variant="primary"
                                className="rounded-full"
                                onClick={onSaveCurrentRevision}
                                disabled={isMutating || !hasChangeReason || !onSaveCurrentRevision}
                            >
                                保存当前配置为新修订
                            </Button>
                            <Button
                                variant="outline"
                                className="rounded-full"
                                onClick={onPublishWorkingRevision}
                                disabled={
                                    isMutating
                                    || !hasChangeReason
                                    || !model.governance.hasUnpublishedRevision
                                    || !onPublishWorkingRevision
                                }
                            >
                                发布并生效
                            </Button>
                            <Button asChild variant="outline" className="rounded-full">
                                <Link href="/admin/sales-trainer/operation-logs">
                                    <History className="mr-2 h-4 w-4" />
                                    查看操作日志
                                </Link>
                            </Button>
                            <Button variant="outline" className="rounded-full" onClick={onRefresh} disabled={isRefreshing}>
                                <RefreshCw className={`mr-2 h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
                                刷新诊断
                            </Button>
                        </div>
                    </div>
                </div>
            </GlassCard>

            <section className="grid gap-4 xl:grid-cols-2">
                {model.modules.map((module) => (
                    <PathConfigModuleCard
                        key={module.moduleKey}
                        editor={module.moduleKey === focusedModule?.moduleKey ? renderModuleEditor?.(module) : null}
                        module={module}
                        isFocused={module.moduleKey === focusedModule?.moduleKey}
                    />
                ))}
            </section>

            <section className="grid gap-4 lg:grid-cols-[1.25fr_0.75fr]">
                <OperationalChecks checks={model.operationalChecks} />
                <LearnerPreview modules={model.modules} />
            </section>

            <PathConfigRevisionHistory
                model={model}
                isMutating={isMutating}
                onRollbackRevision={onRollbackRevision}
            />
        </div>
    );
}

function OperationalChecks({ checks }: { readonly checks: readonly NewcomerOperationalCheck[] }) {
    return (
        <GlassCard className="p-5">
            <div className="flex items-center justify-between gap-3">
                <div>
                    <p className="text-xs font-bold uppercase text-slate-400">运维诊断</p>
                    <h2 className="mt-1 text-lg font-black text-slate-900">转写与 AI 评分服务</h2>
                </div>
                <Button asChild variant="outline" className="rounded-full">
                    <Link href="/admin/sales-trainer/settings">
                        查看配置健康
                    </Link>
                </Button>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
                {checks.map((check) => (
                    <Link
                        key={check.key}
                        href={check.href}
                        className="rounded-2xl border border-slate-100 bg-slate-50 p-4 transition-colors hover:bg-slate-100"
                    >
                        <div className="flex items-center gap-2">
                            {check.ok ? (
                                <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                            ) : (
                                <XCircle className="h-5 w-5 text-red-600" />
                            )}
                            <p className="font-bold text-slate-900">{check.label}</p>
                        </div>
                        <p className="mt-2 text-sm text-slate-500">{check.detail}</p>
                    </Link>
                ))}
            </div>
        </GlassCard>
    );
}

function rollbackAvailabilityLabel(value: Record<string, unknown>): string {
    return value.available === true ? "可预览" : "暂无可用目标";
}

function LearnerPreview({ modules }: { readonly modules: readonly NewcomerConfigModuleSummary[] }) {
    return (
        <GlassCard className="p-5">
            <div className="flex items-center gap-2">
                <Eye className="h-5 w-5 text-slate-700" />
                <div>
                    <p className="text-xs font-bold uppercase text-slate-400">学员端预览</p>
                    <h2 className="text-lg font-black text-slate-900">学员会看到什么</h2>
                </div>
            </div>
            <div className="mt-4 space-y-3">
                {modules.map((module) => (
                    <div key={module.moduleKey} className="rounded-2xl border border-slate-100 p-3">
                        <div className="flex items-center justify-between gap-3">
                            <p className="font-bold text-slate-900">{module.orderLabel} · {module.title}</p>
                            <Badge className={statusCopy(module.status).className}>
                                {learnerPreviewStatusLabel(module)}
                            </Badge>
                        </div>
                        <p className="mt-2 text-sm text-slate-500">{module.learnerPreview}</p>
                    </div>
                ))}
            </div>
        </GlassCard>
    );
}
