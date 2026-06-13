"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, usePathname } from "next/navigation";

import { AdminDetailShell } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import {
    formatAdminRecordStatus,
    formatTrainingTaskDisplay,
    formatUnitTypeLabel,
} from "@/lib/sales-trainer/admin-display";
import type {
    SalesTrainerTrainingRecord,
    SalesTrainerTrainingRecordType,
} from "@/lib/api/types";

const RECORD_TYPES = new Set<string>([
    "audio_submission",
    "quiz_attempt",
    "ai_coach_session",
]);

function isRecordType(value: string): value is SalesTrainerTrainingRecordType {
    return RECORD_TYPES.has(value);
}

function formatScore(score: number | null | undefined, maxScore: number | null | undefined): string {
    if (score == null) {
        return "--";
    }
    return maxScore == null ? String(score) : `${score} / ${maxScore}`;
}

function fieldText(item: Record<string, unknown>, keys: string[], fallback = "--"): string {
    for (const key of keys) {
        const value = item[key];
        if (typeof value === "string" && value.trim()) {
            return value;
        }
        if (typeof value === "number" || typeof value === "boolean") {
            return String(value);
        }
    }
    return fallback;
}

function formatDelta(record: SalesTrainerTrainingRecord): string {
    const delta = record.effective_score?.score_delta;
    if (typeof delta !== "number" || delta === 0) {
        return "无变化";
    }
    return `${delta > 0 ? "+" : ""}${delta}`;
}

function learnerText(record: SalesTrainerTrainingRecord): string {
    const primary = record.user_name || record.user_email || record.user_id;
    const secondary = record.user_department || (
        record.user_email && record.user_email !== primary ? record.user_email : null
    );
    return secondary ? `${primary} · ${secondary}` : primary;
}

function RawPayload({ value }: { value: unknown }) {
    if (!value) {
        return <p className="text-sm text-slate-500">暂无原始数据。</p>;
    }
    return (
        <pre className="max-h-80 overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-100">
            {JSON.stringify(value, null, 2)}
        </pre>
    );
}

export default function SalesTrainerTrainingRecordDetailPage() {
    const params = useParams<{ recordType: string; recordId: string }>();
    const pathname = usePathname();
    const [record, setRecord] = useState<SalesTrainerTrainingRecord | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const recordType = params.recordType;

    useEffect(() => {
        async function loadRecord() {
            setIsLoading(true);
            setError(null);
            if (!isRecordType(recordType)) {
                setRecord(null);
                setError("训练记录类型无效。");
                setIsLoading(false);
                return;
            }
            try {
                setRecord(await api.admin.salesTrainer.getTrainingRecordDetail(
                    recordType,
                    params.recordId,
                ));
            } catch (loadError) {
                setRecord(null);
                setError(getApiErrorMessage(loadError));
            } finally {
                setIsLoading(false);
            }
        }
        void loadRecord();
    }, [params.recordId, recordType]);

    const taskDisplay = record
        ? formatTrainingTaskDisplay(record.unit_name, record.unit_id)
        : null;
    const explanation = record?.score_explanation;
    const abilityProfile = record?.ability_profile;
    const rawPayload = record?.audio_submission
        ?? record?.quiz_attempt
        ?? record?.ai_coach_session
        ?? null;

    return (
        <AdminDetailShell
            backHref="/admin/sales-trainer/training-records"
            title="训练记录详情"
            description="统一查看当前有效分、原始分、重评、评分解释、能力弱项、补救动作和原始记录。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
        >
            {isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载训练记录...</div>
            ) : !record ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error || "未找到训练记录。"}
                </div>
            ) : (
                <div className="space-y-6">
                    <GlassCard className="space-y-4 p-6">
                        <div className="flex flex-wrap items-center gap-2">
                            <Badge className="bg-slate-100 text-slate-700">
                                {formatUnitTypeLabel(record.unit_type)}
                            </Badge>
                            <Badge className="bg-slate-100 text-slate-700">
                                {formatAdminRecordStatus(record.status)}
                            </Badge>
                            {record.remediation?.needed ? (
                                <Badge className="bg-amber-50 text-amber-700">
                                    {record.remediation.action_label}
                                </Badge>
                            ) : null}
                        </div>
                        <div className="grid gap-4 md:grid-cols-4">
                            <div>
                                <p className="text-xs text-slate-500">学员</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">{learnerText(record)}</p>
                                <p className="mt-1 text-xs text-slate-400">{record.user_id}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">训练任务</p>
                                <p className="mt-1 text-sm text-slate-900">{taskDisplay?.title}</p>
                                {taskDisplay?.detail ? (
                                    <p className="mt-1 text-xs text-slate-400">{taskDisplay.detail}</p>
                                ) : null}
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">当前有效分</p>
                                <p className="mt-1 text-2xl font-black text-slate-900">
                                    {formatScore(record.effective_score?.score, record.effective_score?.max_score)}
                                </p>
                                <p className="mt-1 text-xs text-slate-500">
                                    原始分 {formatScore(record.score, record.max_score)}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">提交时间</p>
                                <p className="mt-1 text-sm text-slate-900">
                                    {record.submitted_at ? new Date(record.submitted_at).toLocaleString() : "--"}
                                </p>
                            </div>
                        </div>
                    </GlassCard>

                    <GlassCard className="space-y-4 p-6">
                        <h2 className="text-lg font-bold text-slate-900">重评与补救</h2>
                        <div className="grid gap-4 md:grid-cols-3">
                            <div>
                                <p className="text-xs text-slate-500">有效分来源</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">
                                    {record.effective_score?.source === "latest_regrade" ? "最近重评" : "原始记录"}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">重评分差</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">{formatDelta(record)}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">最近重评</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">
                                    {record.latest_regrade?.["regrade_run_id"] ? String(record.latest_regrade["regrade_run_id"]) : "--"}
                                </p>
                            </div>
                        </div>
                        {record.remediation ? (
                            <div className="rounded-lg border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                                <p className="font-semibold">{record.remediation.action_label}</p>
                                <p className="mt-1">{record.remediation.reason}</p>
                                <Link href={record.remediation.target_path}>
                                    <Button className="mt-3 rounded-full bg-slate-900 text-white" size="sm">
                                        进入补救入口
                                    </Button>
                                </Link>
                            </div>
                        ) : null}
                    </GlassCard>

                    <GlassCard className="space-y-4 p-6">
                        <h2 className="text-lg font-bold text-slate-900">评分解释</h2>
                        <p className="text-sm text-slate-600">
                            {explanation?.summary || "暂无评分解释。"}
                        </p>
                        <div className="grid gap-3 md:grid-cols-3">
                            {(explanation?.dimensions || []).map((dimension, index) => (
                                <div key={`${fieldText(dimension, ["key"], String(index))}-${index}`} className="rounded-lg border border-slate-100 p-3">
                                    <p className="font-medium text-slate-900">
                                        {fieldText(dimension, ["label", "key"], "维度")}
                                    </p>
                                    <p className="mt-1 text-xs text-slate-500">
                                        {fieldText(dimension, ["score"])} / {fieldText(dimension, ["max_score"])}
                                    </p>
                                    {dimension["is_weak"] === true ? (
                                        <Badge className="mt-2 bg-amber-50 text-amber-700">弱项</Badge>
                                    ) : null}
                                </div>
                            ))}
                        </div>
                        {(explanation?.issues || []).length ? (
                            <div className="space-y-2">
                                <h3 className="text-sm font-semibold text-slate-900">问题</h3>
                                {explanation?.issues.map((issue, index) => (
                                    <div key={`${fieldText(issue, ["type"], String(index))}-${index}`} className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-700">
                                        {fieldText(issue, ["text", "feedback", "title", "type"])}
                                    </div>
                                ))}
                            </div>
                        ) : null}
                        {(explanation?.evidence || []).length ? (
                            <div className="space-y-2">
                                <h3 className="text-sm font-semibold text-slate-900">证据</h3>
                                {explanation?.evidence.map((evidence, index) => (
                                    <div key={`${fieldText(evidence, ["type"], String(index))}-${index}`} className="rounded-lg bg-white px-4 py-3 text-sm text-slate-700">
                                        {fieldText(evidence, ["text", "title", "question_id", "type"])}
                                    </div>
                                ))}
                            </div>
                        ) : null}
                    </GlassCard>

                    <GlassCard className="space-y-4 p-6">
                        <h2 className="text-lg font-bold text-slate-900">能力画像</h2>
                        <div className="grid gap-4 md:grid-cols-3">
                            <div>
                                <p className="text-xs text-slate-500">总体分</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">
                                    {formatScore(abilityProfile?.overall_score, record.effective_score?.max_score)}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">弱项数</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">
                                    {abilityProfile?.weak_dimensions.length ?? 0}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">证据数</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">
                                    {abilityProfile?.evidence_count ?? 0}
                                </p>
                            </div>
                        </div>
                    </GlassCard>

                    <GlassCard className="space-y-4 p-6">
                        <h2 className="text-lg font-bold text-slate-900">原始记录</h2>
                        <RawPayload value={rawPayload} />
                    </GlassCard>

                    {record.operation_logs.length ? (
                        <GlassCard className="space-y-4 p-6">
                            <h2 className="text-lg font-bold text-slate-900">操作日志</h2>
                            <div className="space-y-2">
                                {record.operation_logs.map((log) => (
                                    <div key={log.log_id} className="rounded-lg border border-slate-100 px-4 py-3 text-sm text-slate-700">
                                        <p className="font-medium text-slate-900">{log.action}</p>
                                        <p className="mt-1 text-xs text-slate-500">
                                            {new Date(log.created_at).toLocaleString()} · {log.actor_role || "--"}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        </GlassCard>
                    ) : null}
                </div>
            )}
        </AdminDetailShell>
    );
}
