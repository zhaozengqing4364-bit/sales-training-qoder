"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, usePathname } from "next/navigation";
import { AlertTriangle, ClipboardCheck, FileText, RefreshCw } from "lucide-react";

import { AdminDetailShell } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    ReadinessDossier,
    ReadinessDossierCompetency,
    ReadinessDossierEvidence,
    ReadinessDossierReviewAction,
    ReadinessReviewDecision,
} from "@/lib/api/types/training-journey";
import { useSalesTrainerAdminRouteAccess } from "@/lib/sales-trainer/use-admin-route-access";
import {
    capabilityNames,
    defaultCapabilitySelection,
    defaultEvidenceSelection,
    evidenceLabel,
    evidenceResultSummary,
    formatDate,
    formatScore,
    paramValue,
    readinessDisplayMessage,
    recordTypeLabel,
    retrainingTaskResultText,
    retrainingTaskStatusText,
    snapshotSummary,
    statusBadgeClass,
    statusLabel,
    toggleValue,
} from "./readiness-view-model";

const DECISION_OPTIONS: Array<{
    value: ReadinessReviewDecision;
    label: string;
}> = [
    { value: "approve", label: "确认达标" },
    { value: "require_retraining", label: "要求重练" },
    { value: "mark_manual_follow_up", label: "标记需人工跟进" },
];

function CompetencyRow({ competency }: { competency: ReadinessDossierCompetency }) {
    return (
        <div className="border-b border-slate-100 px-5 py-4 last:border-b-0">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold text-slate-900">{competency.display_name}</h3>
                        <Badge className={statusBadgeClass(competency.status)}>
                            {statusLabel(competency.status)}
                        </Badge>
                    </div>
                    <p className="mt-1 text-sm leading-6 text-slate-600">
                        {competency.reason || competency.description}
                    </p>
                    {competency.evidence_ids.length > 0 ? (
                        <p className="mt-1 text-xs text-slate-400">
                            关联证据 {competency.evidence_ids.length} 条
                        </p>
                    ) : null}
                </div>
                <div className="text-sm font-semibold text-slate-900">
                    {formatScore(competency.score, competency.max_score)}
                </div>
            </div>
        </div>
    );
}

function EvidenceRow({ evidence }: { evidence: ReadinessDossierEvidence }) {
    return (
        <div className="border-b border-slate-100 px-5 py-4 last:border-b-0">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold text-slate-900">{evidenceLabel(evidence)}</h3>
                        <Badge className={statusBadgeClass(evidence.status || "")}>
                            {statusLabel(evidence.status)}
                        </Badge>
                    </div>
                    <p className="text-sm text-slate-500">
                        {recordTypeLabel(evidence.record_type)} ·{" "}
                        {formatDate(evidence.submitted_at)}
                    </p>
                    <p className="text-sm leading-6 text-slate-700">
                        {evidenceResultSummary(evidence)}
                    </p>
                    <div className="grid gap-2 text-xs text-slate-500 md:grid-cols-3">
                        <span>材料：{snapshotSummary(evidence.material_snapshot, "material")}</span>
                        <span>评分：{snapshotSummary(evidence.scoring_snapshot, "scoring")}</span>
                        <span>任务：{snapshotSummary(evidence.task_brief_snapshot, "task")}</span>
                    </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-slate-900">
                        {formatScore(evidence.score, evidence.max_score)}
                    </span>
                    {evidence.target_path ? (
                        <Button asChild variant="outline" size="sm">
                            <Link href={evidence.target_path}>
                                <FileText className="mr-2 h-4 w-4" />
                                查看记录
                            </Link>
                        </Button>
                    ) : null}
                </div>
            </div>
        </div>
    );
}

function ReviewActionRow({
    action,
    competenciesByKey,
}: {
    action: ReadinessDossierReviewAction;
    competenciesByKey: Map<string, ReadinessDossierCompetency>;
}) {
    const task = action.retraining_task;
    const taskResult = task ? retrainingTaskResultText(task) : null;
    const taskCapabilities = task
        ? capabilityNames(task.capability_keys, competenciesByKey)
        : capabilityNames(action.capability_keys, competenciesByKey);
    return (
        <div className="border-b border-slate-100 px-5 py-4 last:border-b-0">
            <div className="flex flex-wrap items-center gap-2">
                <Badge className="bg-slate-900 text-white">
                    {action.decision_label}
                </Badge>
                <span className="text-sm text-slate-500">
                    {formatDate(action.created_at)}
                </span>
            </div>
            {action.reason ? (
                <p className="mt-2 text-sm leading-6 text-slate-700">
                    {action.reason}
                </p>
            ) : null}
            {task ? (
                <div className="mt-3 rounded-md border border-amber-100 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                    <p className="font-medium">{retrainingTaskStatusText(task)}</p>
                    {taskCapabilities.length > 0 ? (
                        <p className="mt-1 text-xs text-amber-800">
                            关联能力：{taskCapabilities.join("、")}
                        </p>
                    ) : null}
                    <p className="mt-1 text-xs text-amber-800">
                        原证据 {task.source_evidence_ids.length} 条 · 重练证据{" "}
                        {task.completed_evidence_ids?.length ?? 0} 条
                    </p>
                    {taskResult ? (
                        <p className="mt-1 text-xs text-amber-800">{taskResult}</p>
                    ) : null}
                </div>
            ) : null}
        </div>
    );
}

export default function SalesTrainerReadinessDossierPage() {
    const pathname = usePathname();
    const params = useParams();
    const learnerId = paramValue(params.learnerId);
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);
    const [dossier, setDossier] = useState<ReadinessDossier | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [decision, setDecision] = useState<ReadinessReviewDecision>("approve");
    const [reason, setReason] = useState("");
    const [selectedCapabilityKeys, setSelectedCapabilityKeys] = useState<string[]>([]);
    const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<string[]>([]);
    const [actionError, setActionError] = useState<string | null>(null);
    const [actionMessage, setActionMessage] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const loadDossier = useCallback(async () => {
        if (!routeAccess.canAccess || !learnerId) {
            return;
        }
        setIsLoading(true);
        setError(null);
        try {
            setDossier(await api.admin.salesTrainer.getReadinessDossier(learnerId));
        } catch (loadError) {
            setDossier(null);
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, [learnerId, routeAccess.canAccess]);

    useEffect(() => {
        void loadDossier();
    }, [loadDossier]);

    useEffect(() => {
        if (!dossier) {
            return;
        }
        setSelectedCapabilityKeys(defaultCapabilitySelection(dossier));
        setSelectedEvidenceIds(defaultEvidenceSelection(dossier));
    }, [dossier]);

    const failedCompetencies = useMemo(() => {
        return dossier?.competencies.filter((item) => item.weak) ?? [];
    }, [dossier]);
    const competenciesByKey = useMemo(() => {
        return new Map(
            (dossier?.competencies ?? []).map((competency) => [
                competency.capability_key,
                competency,
            ]),
        );
    }, [dossier]);

    async function submitReviewAction(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!dossier) {
            return;
        }
        const trimmedReason = reason.trim();
        if (!trimmedReason) {
            setActionError("请填写复核原因。");
            return;
        }
        setIsSubmitting(true);
        setActionError(null);
        setActionMessage(null);
        try {
            const action = await api.admin.salesTrainer.createReadinessReviewAction(
                dossier.learner.learner_id,
                {
                    decision,
                    reason: trimmedReason,
                    capability_keys: selectedCapabilityKeys,
                    source_evidence_ids: selectedEvidenceIds,
                },
            );
            setActionMessage(`${action.decision_label}已记录。`);
            setReason("");
            await loadDossier();
        } catch (submitError) {
            setActionError(getApiErrorMessage(submitError));
        } finally {
            setIsSubmitting(false);
        }
    }

    const content = (() => {
        if (routeAccess.isLoading) {
            return (
                <GlassCard className="p-5 text-sm text-slate-500">
                    正在确认档案查看权限...
                </GlassCard>
            );
        }
        if (!routeAccess.canAccess) {
            return (
                <AdminLoadErrorCard
                    title="训练达标档案不可访问"
                    description="当前账号没有查看或复核该新人训练档案的权限，系统不会加载档案证据。"
                    message={routeAccess.denialMessage}
                    retryLabel="重新检查权限"
                    onRetry={routeAccess.reloadCapabilities}
                />
            );
        }
        if (error) {
            return (
                <AdminLoadErrorCard
                    title="训练达标档案加载失败"
                    description="档案没有加载成功，已停止渲染证据链，避免把接口错误误判为暂无训练证据。"
                    message={error}
                    retryLabel="重新加载档案"
                    onRetry={() => void loadDossier()}
                />
            );
        }
        if (isLoading && !dossier) {
            return (
                <GlassCard className="p-5 text-sm text-slate-500">
                    正在加载训练达标档案...
                </GlassCard>
            );
        }
        if (!dossier) {
            return null;
        }
        return (
            <>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <GlassCard className="p-5">
                        <p className="text-sm text-slate-500">当前状态</p>
                        <p className="mt-2 text-xl font-bold text-slate-900">
                            {dossier.status_label}
                        </p>
                        <p className="mt-2 text-sm leading-6 text-slate-600">
                            {dossier.status_reason}
                        </p>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <p className="text-sm text-slate-500">任务进度</p>
                        <p className="mt-2 text-xl font-bold text-slate-900">
                            {dossier.summary.completed_modules} / {dossier.summary.total_modules}
                        </p>
                        <p className="mt-2 text-sm text-slate-600">
                            通过 {dossier.summary.passed_modules} · 未通过{" "}
                            {dossier.summary.failed_modules}
                        </p>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <p className="text-sm text-slate-500">证据链</p>
                        <p className="mt-2 text-xl font-bold text-slate-900">
                            {dossier.summary.evidence_count} 条
                        </p>
                        <p className="mt-2 text-sm text-slate-600">
                            复核动作 {dossier.summary.review_action_count} 条
                        </p>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <p className="text-sm text-slate-500">下一阶段</p>
                        <p className="mt-2 text-xl font-bold text-slate-900">
                            {dossier.realtime_gate.locked ? "暂未开放" : "可进入"}
                        </p>
                        <p className="mt-2 text-sm leading-6 text-slate-600">
                            {readinessDisplayMessage(dossier.realtime_gate.reason) ||
                                "训练准入和语音服务检查已满足。"}
                        </p>
                    </GlassCard>
                </div>

                {dossier.diagnostics.length > 0 ? (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                        <div className="flex gap-3">
                            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
                            <div>
                                <p className="font-semibold text-amber-950">
                                    档案存在需要处理的诊断
                                </p>
                                <ul className="mt-2 space-y-1">
                                    {dossier.diagnostics.map((diagnostic, index) => (
                                        <li key={`${diagnostic.code}-${diagnostic.message}-${index}`}>
                                            {readinessDisplayMessage(diagnostic.message)}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    </div>
                ) : null}

                <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
                    <div className="space-y-4">
                        <GlassCard className="overflow-hidden p-0">
                            <div className="border-b border-slate-100 px-5 py-4">
                                <h2 className="text-base font-bold text-slate-900">能力项状态</h2>
                                <p className="mt-1 text-sm text-slate-500">
                                    AI/规则给出初评，培训负责人给出最终复核结论。
                                </p>
                            </div>
                            {dossier.competencies.map((competency) => (
                                <CompetencyRow
                                    key={competency.capability_key}
                                    competency={competency}
                                />
                            ))}
                        </GlassCard>

                        <GlassCard className="overflow-hidden p-0">
                            <div className="border-b border-slate-100 px-5 py-4">
                                <h2 className="text-base font-bold text-slate-900">证据链</h2>
                                <p className="mt-1 text-sm text-slate-500">
                                    每条证据保留提交、材料快照、评分依据和记录入口。
                                </p>
                            </div>
                            {dossier.evidence.length > 0 ? (
                                dossier.evidence.map((evidence) => (
                                    <EvidenceRow key={evidence.evidence_id} evidence={evidence} />
                                ))
                            ) : (
                                <div className="px-5 py-8 text-sm text-slate-500">暂无训练证据</div>
                            )}
                        </GlassCard>

                        <GlassCard className="overflow-hidden p-0">
                            <div className="border-b border-slate-100 px-5 py-4">
                                <h2 className="text-base font-bold text-slate-900">复核记录</h2>
                            </div>
                            {dossier.review_actions.length > 0 ? (
                                dossier.review_actions.map((action) => (
                                    <ReviewActionRow
                                        key={action.action_id}
                                        action={action}
                                        competenciesByKey={competenciesByKey}
                                    />
                                ))
                            ) : (
                                <div className="px-5 py-8 text-sm text-slate-500">尚未复核</div>
                            )}
                        </GlassCard>
                    </div>

                    <GlassCard className="h-fit p-5">
                        <form className="space-y-5" onSubmit={submitReviewAction}>
                            <div>
                                <h2 className="text-base font-bold text-slate-900">复核动作</h2>
                                <p className="mt-1 text-sm text-slate-500">
                                    动作会写入审计，并回流到档案状态。
                                </p>
                            </div>

                            <div className="space-y-2">
                                <label
                                    className="text-sm font-medium text-slate-700"
                                    htmlFor="review-decision"
                                >
                                    结论
                                </label>
                                <select
                                    id="review-decision"
                                    className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                                    value={decision}
                                    onChange={(event) =>
                                        setDecision(event.target.value as ReadinessReviewDecision)
                                    }
                                >
                                    {DECISION_OPTIONS.map((option) => (
                                        <option key={option.value} value={option.value}>
                                            {option.label}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="space-y-2">
                                <label
                                    className="text-sm font-medium text-slate-700"
                                    htmlFor="review-reason"
                                >
                                    原因
                                </label>
                                <textarea
                                    id="review-reason"
                                    className="min-h-28 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                                    value={reason}
                                    onChange={(event) => setReason(event.target.value)}
                                    placeholder="写明复核依据、重练要求或人工跟进原因"
                                />
                            </div>

                            <div className="space-y-2">
                                <p className="text-sm font-medium text-slate-700">关联能力项</p>
                                <div className="space-y-2">
                                    {dossier.competencies.map((competency) => (
                                        <label
                                            key={competency.capability_key}
                                            className="flex items-start gap-2 rounded-md border border-slate-100 px-3 py-2 text-sm"
                                        >
                                            <input
                                                type="checkbox"
                                                className="mt-1"
                                                checked={selectedCapabilityKeys.includes(
                                                    competency.capability_key,
                                                )}
                                                onChange={() =>
                                                    setSelectedCapabilityKeys((current) =>
                                                        toggleValue(
                                                            current,
                                                            competency.capability_key,
                                                        ),
                                                    )
                                                }
                                            />
                                            <span>
                                                <span className="font-medium text-slate-900">
                                                    {competency.display_name}
                                                </span>
                                                {failedCompetencies.some(
                                                    (item) =>
                                                        item.capability_key ===
                                                        competency.capability_key,
                                                ) ? (
                                                    <span className="ml-2 text-amber-700">
                                                        需关注
                                                    </span>
                                                ) : null}
                                            </span>
                                        </label>
                                    ))}
                                </div>
                            </div>

                            <div className="space-y-2">
                                <p className="text-sm font-medium text-slate-700">关联证据</p>
                                <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
                                    {dossier.evidence.length > 0 ? (
                                        dossier.evidence.map((evidence) => (
                                            <label
                                                key={evidence.evidence_id}
                                                className="flex items-start gap-2 rounded-md border border-slate-100 px-3 py-2 text-sm"
                                            >
                                                <input
                                                    type="checkbox"
                                                    className="mt-1"
                                                    checked={selectedEvidenceIds.includes(
                                                        evidence.evidence_id,
                                                    )}
                                                    onChange={() =>
                                                        setSelectedEvidenceIds((current) =>
                                                            toggleValue(
                                                                current,
                                                                evidence.evidence_id,
                                                            ),
                                                        )
                                                    }
                                                />
                                                <span>
                                                    <span className="font-medium text-slate-900">
                                                        {evidenceLabel(evidence)}
                                                    </span>
                                                    <span className="block text-xs text-slate-500">
                                                        {formatScore(
                                                            evidence.score,
                                                            evidence.max_score,
                                                        )}{" "}
                                                        · {formatDate(evidence.submitted_at)}
                                                    </span>
                                                </span>
                                            </label>
                                        ))
                                    ) : (
                                        <p className="text-sm text-slate-500">暂无可关联证据</p>
                                    )}
                                </div>
                            </div>

                            {actionError ? (
                                <div
                                    role="alert"
                                    className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
                                >
                                    {actionError}
                                </div>
                            ) : null}
                            {actionMessage ? (
                                <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                                    {actionMessage}
                                </div>
                            ) : null}

                            <Button
                                type="submit"
                                className="w-full bg-slate-900 text-white"
                                disabled={isSubmitting}
                            >
                                <ClipboardCheck className="mr-2 h-4 w-4" />
                                {isSubmitting ? "正在提交" : "提交复核动作"}
                            </Button>
                        </form>
                    </GlassCard>
                </div>
            </>
        );
    })();

    const title = dossier
        ? `${dossier.learner.name || dossier.learner.learner_id} 的训练达标档案`
        : "训练达标档案";

    return (
        <AdminDetailShell
            backHref="/admin/sales-trainer/readiness"
            backLabel="返回达标验收"
            title={title}
            description="聚合训练进度、能力项、证据链、复核动作和下一阶段准入。"
            actions={
                routeAccess.canAccess ? (
                    <Button type="button" variant="outline" onClick={() => void loadDossier()}>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        刷新
                    </Button>
                ) : null
            }
        >
            {content}
        </AdminDetailShell>
    );
}
