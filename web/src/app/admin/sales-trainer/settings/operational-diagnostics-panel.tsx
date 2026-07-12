"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import type {
    NewcomerConfigurationDiagnosticStatus,
    NewcomerFailedTask,
    NewcomerOperationalDiagnostics,
} from "@/lib/sales-trainer/operational-diagnostics";

export function OperationalDiagnosticsPanel({
    diagnostics,
}: {
    readonly diagnostics: NewcomerOperationalDiagnostics;
}) {
    return (
        <GlassCard className="space-y-5 p-6 lg:col-span-2">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                    <p className="text-xs font-bold uppercase text-slate-400">运维诊断</p>
                    <h2 className="mt-1 text-lg font-bold text-slate-900">路径配置诊断</h2>
                    <p className="mt-1 text-sm text-slate-500">
                        聚合路径版本、关卡绑定、legacy 快照和最近 100 条失败记录。
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Button asChild variant="outline" className="rounded-full">
                        <Link href="/admin/newcomer-training/path">打开路径编辑器</Link>
                    </Button>
                    <Button asChild variant="outline" className="rounded-full">
                        <Link href="/support/runtime">查看运行时健康</Link>
                    </Button>
                    <Button asChild variant="outline" className="rounded-full">
                        <Link href="/admin/sales-trainer/operation-logs">查看操作日志</Link>
                    </Button>
                </div>
            </div>
            <ConfigurationDiagnostics diagnostics={diagnostics} />
            <RecentFailureDiagnostics diagnostics={diagnostics} />
        </GlassCard>
    );
}

function ConfigurationDiagnostics({
    diagnostics,
}: {
    readonly diagnostics: NewcomerOperationalDiagnostics;
}) {
    const configuration = diagnostics.configuration;
    if (!configuration) {
        return (
            <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                尚未读取到路径级发布配置。请到“新人训练路径配置中心”完成发布配置。
            </div>
        );
    }
    return (
        <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-4">
                <DiagnosticMetric label="配置来源" value={configuration.sourceLabel} />
                <DiagnosticMetric label="当前版本" value={configuration.activeRevisionLabel} />
                <DiagnosticMetric label="待发布" value={configuration.workingRevisionLabel} />
                <DiagnosticMetric
                    label="历史快照"
                    value={`legacy 快照记录 ${configuration.legacySnapshotOnlyCount} 条`}
                />
            </div>
            {configuration.latestReason ? (
                <p className="text-sm text-slate-500">最近发布原因：{configuration.latestReason}</p>
            ) : null}
            <div className="grid gap-3 md:grid-cols-2">
                {configuration.moduleBindings.map((module) => (
                    <Link
                        key={module.title}
                        href={module.href}
                        className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 transition-colors hover:bg-slate-100"
                    >
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <p className="font-bold text-slate-900">{module.title}</p>
                                <p className="mt-1 text-sm text-slate-500">{module.detail}</p>
                            </div>
                            <ConfigurationBadge status={module.status} />
                        </div>
                    </Link>
                ))}
            </div>
        </div>
    );
}

function RecentFailureDiagnostics({
    diagnostics,
}: {
    readonly diagnostics: NewcomerOperationalDiagnostics;
}) {
    return (
        <div className="space-y-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                    <h3 className="text-base font-bold text-slate-900">最近失败任务</h3>
                    <p className="mt-1 text-sm text-slate-500">
                        定位 ASR、AI 评分或配置错误，并进入对应处理页面。
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Button asChild variant="outline" className="rounded-full">
                        <Link href="/admin/sales-trainer/audio/submissions">查看学员录音</Link>
                    </Button>
                    <Button asChild variant="outline" className="rounded-full">
                        <Link href="/admin/sales-trainer/audio/results">查看评分结果</Link>
                    </Button>
                </div>
            </div>
            <ErrorCodeBuckets diagnostics={diagnostics} />
            <FailedTaskList tasks={diagnostics.failedTasks} />
        </div>
    );
}

function DiagnosticMetric({
    label,
    value,
}: {
    readonly label: string;
    readonly value: string;
}) {
    return (
        <div className="rounded-2xl border border-slate-100 bg-white px-4 py-3">
            <p className="text-xs font-bold uppercase text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-bold text-slate-900">{value}</p>
        </div>
    );
}

function ConfigurationBadge({
    status,
}: {
    readonly status: NewcomerConfigurationDiagnosticStatus;
}) {
    const labelByStatus: Record<NewcomerConfigurationDiagnosticStatus, string> = {
        disabled: "已关闭",
        missing: "缺配置",
        ready: "可用",
    };
    const classByStatus: Record<NewcomerConfigurationDiagnosticStatus, string> = {
        disabled: "bg-slate-100 text-slate-600",
        missing: "bg-amber-50 text-amber-700",
        ready: "bg-emerald-50 text-emerald-700",
    };
    return <Badge className={classByStatus[status]}>{labelByStatus[status]}</Badge>;
}

function ErrorCodeBuckets({
    diagnostics,
}: {
    readonly diagnostics: NewcomerOperationalDiagnostics;
}) {
    if (diagnostics.errorCodeBuckets.length === 0) {
        return (
            <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                最近没有 ASR 或 AI 评分失败记录。
            </div>
        );
    }
    return (
        <div className="grid gap-3 md:grid-cols-3">
            {diagnostics.errorCodeBuckets.map((bucket) => (
                <div key={bucket.code} className="rounded-2xl border border-amber-100 bg-amber-50 p-4">
                    <p className="text-xs font-bold uppercase text-amber-600">高频错误码</p>
                    <p className="mt-2 font-black text-amber-900">{bucket.code}</p>
                    <p className="mt-1 text-sm text-amber-700">{bucket.count} 次失败</p>
                </div>
            ))}
        </div>
    );
}

function FailedTaskList({ tasks }: { readonly tasks: readonly NewcomerFailedTask[] }) {
    if (tasks.length === 0) {
        return null;
    }
    return (
        <div className="space-y-3">
            {tasks.slice(0, 5).map((task) => (
                <Link
                    key={`${task.source}-${task.id}`}
                    href={task.href}
                    className="block rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 transition-colors hover:bg-slate-100"
                >
                    <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
                        <p className="font-bold text-slate-900">{task.title}</p>
                        <Badge className="bg-red-50 text-red-700">{task.errorCode}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-slate-500">
                        {task.status} · {task.errorMessage ?? "暂无错误详情"}
                    </p>
                </Link>
            ))}
        </div>
    );
}
