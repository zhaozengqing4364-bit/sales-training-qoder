"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { ApiRequestError, api, getApiErrorMessage } from "@/lib/api/client";
import type { EvidenceDossierV1 } from "@/lib/api/types/newcomer-training";
import { generateClientToken } from "@/lib/sales-trainer/idempotency";
import {
    readinessCompetencyStatusLabel,
    readinessEvidenceTypeLabel,
} from "../readiness-view-model";

type DecisionType = "approve_foundation_ready" | "request_more_evidence" | "reject_due_to_integrity_issue" | "close_without_decision";

function parameter(value: string | string[] | undefined): string {
    return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

export function ReadinessDossierWorkspace() {
    const params = useParams<{ learnerId?: string | string[] }>();
    const dossierId = parameter(params.learnerId);
    const [dossier, setDossier] = useState<EvidenceDossierV1 | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [permissionDenied, setPermissionDenied] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isRebuilding, setIsRebuilding] = useState(false);
    const [decision, setDecision] = useState<DecisionType>("approve_foundation_ready");
    const [reason, setReason] = useState("");
    const [message, setMessage] = useState<string | null>(null);

    const load = useCallback(async () => {
        if (!dossierId) {
            setError("复核档案地址不完整，请返回复核队列重新进入。");
            setIsLoading(false);
            return;
        }
        setIsLoading(true);
        setError(null);
        setPermissionDenied(false);
        try {
            setDossier(await api.admin.newcomerTraining.getReadinessReview(dossierId));
        } catch (loadError) {
            setDossier(null);
            if (loadError instanceof ApiRequestError && loadError.status === 403) {
                setPermissionDenied(true);
            } else {
                setError(getApiErrorMessage(loadError));
            }
        } finally {
            setIsLoading(false);
        }
    }, [dossierId]);

    useEffect(() => { void load(); }, [load]);

    useEffect(() => {
        if (dossier) {
            setDecision(
                dossier.summary.eligibility.eligible
                    ? "approve_foundation_ready"
                    : "request_more_evidence",
            );
        }
    }, [dossier]);

    async function submitDecision(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!dossier || !reason.trim()) return;
        setIsSubmitting(true);
        setActionError(null);
        setMessage(null);
        try {
            await api.admin.newcomerTraining.recordReadinessDecision(
                dossier.dossier_id,
                {
                    decision_type: decision,
                    expected_dossier_version: dossier.dossier_version,
                    snapshot_id: dossier.snapshot_id,
                    reason: reason.trim(),
                    notes: null,
                    competency_keys: dossier.competencies.map((item) => item.competency_key),
                    evidence_ids: dossier.evidence.map((item) => item.evidence_id),
                },
                generateClientToken(),
            );
            setMessage("复核结论已保存并写入审计记录。刷新后可查看最新档案版本。");
            setReason("");
            await load();
        } catch (submitError) {
            setActionError(getApiErrorMessage(submitError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function rebuildDossier() {
        if (!dossier) return;
        setIsRebuilding(true);
        setActionError(null);
        setMessage(null);
        try {
            await api.admin.newcomerTraining.rebuildReadinessReview(
                dossier.dossier_id,
                "复核前刷新过期档案",
            );
            setMessage("训练档案已重建，请基于最新证据继续复核。");
            await load();
        } catch (rebuildError) {
            setActionError(getApiErrorMessage(rebuildError));
        } finally {
            setIsRebuilding(false);
        }
    }

    if (isLoading) return <main className="min-h-screen bg-slate-50 p-6"><GlassCard className="mx-auto max-w-5xl p-6 text-sm text-slate-600">正在加载训练档案...</GlassCard></main>;
    if (permissionDenied) return <main className="min-h-screen bg-slate-50 p-6"><GlassCard className="mx-auto max-w-5xl border-amber-200 p-6"><h1 className="font-semibold text-slate-950">当前账号不能查看这份训练档案</h1><p className="mt-2 text-sm text-slate-600">系统没有加载学员证据。请返回达标复核队列，或联系培训负责人申请相应复核范围。</p><Button asChild variant="outline" className="mt-4"><Link href="/admin/newcomer-training/reviews">返回达标复核</Link></Button></GlassCard></main>;
    if (error && !dossier) return <main className="min-h-screen bg-slate-50 p-6"><GlassCard className="mx-auto max-w-5xl border-red-200 p-6"><p role="alert" className="text-sm text-red-700">训练档案加载失败：{error}</p><Button variant="outline" className="mt-4" onClick={() => void load()}>重新加载</Button></GlassCard></main>;
    if (!dossier) return null;

    const canReview = dossier.capabilities.includes("readiness.review");
    const canRebuild = dossier.capabilities.includes("readiness.rebuild");
    const eligibility = dossier.summary.eligibility;

    return (
        <main className="min-h-screen bg-slate-50 p-4 md:p-6" aria-busy={isSubmitting || isRebuilding}>
            <div className="mx-auto max-w-5xl space-y-5">
                <Link href="/admin/newcomer-training/reviews" className="text-sm font-medium text-blue-700 hover:underline">← 返回达标复核</Link>
                <header className="rounded-3xl bg-slate-900 p-6 text-white"><p className="text-sm text-blue-200">{dossier.learner.name || "未命名学员"} · {dossier.learner.cohort_name ?? "未命名班级"}</p><h1 className="mt-1 text-2xl font-semibold">{dossier.path.title}</h1><p className="mt-2 text-sm text-slate-300">{dossier.status_label} · {dossier.path.revision_label} · {dossier.data_freshness === "fresh" ? "档案已更新" : "档案待刷新"}</p></header>

                {dossier.snapshot_stale ? <GlassCard className="border-amber-200 p-5"><div className="flex gap-3 text-amber-900"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" /><div><h2 className="font-semibold">档案快照已过期</h2><p className="mt-1 text-sm">{dossier.summary.stale_reason ?? "先重建档案，再记录正式结论。"}</p>{canRebuild ? <Button variant="outline" className="mt-3" onClick={() => void rebuildDossier()} disabled={isRebuilding}><RefreshCw className="mr-2 h-4 w-4" />{isRebuilding ? "正在重建..." : "重建档案"}</Button> : <p className="mt-2 text-sm">当前账号没有重建权限，请交由档案管理员处理。</p>}</div></div></GlassCard> : null}

                {actionError ? <GlassCard className="border-red-200 p-4"><p role="alert" className="text-sm text-red-700">操作失败：{actionError}。已保留本页输入，可核对后重试。</p></GlassCard> : null}
                {message ? <GlassCard className="border-emerald-200 p-4"><p role="status" className="text-sm text-emerald-700">{message}</p></GlassCard> : null}

                <div className="grid gap-5 lg:grid-cols-2">
                    <GlassCard className="p-5"><h2 className="font-semibold text-slate-950">规则校验</h2><p className="mt-2 text-sm text-slate-700">{eligibility.eligible ? "当前训练证据满足人工复核前置条件。" : "当前训练证据尚未满足正式达标前置条件。"}</p>{eligibility.reasons.length > 0 ? <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600">{eligibility.reasons.map((item) => <li key={item}>{item}</li>)}</ul> : null}</GlassCard>
                    <GlassCard className="p-5"><h2 className="font-semibold text-slate-950">AI 辅助评估</h2><p className="mt-2 text-sm font-medium text-slate-800">{dossier.ai_assessment.label}</p><p className="mt-1 text-sm text-slate-600">{dossier.ai_assessment.message ?? "暂无可展示的辅助评估。"}</p><p className="mt-3 text-xs text-slate-500">该内容属于辅助推断，不会自动授予基础训练达标结论。</p></GlassCard>
                </div>

                <div className="grid gap-5 lg:grid-cols-2">
                    <GlassCard className="p-5"><h2 className="font-semibold text-slate-950">能力证据</h2><ul className="mt-3 space-y-3">{dossier.competencies.map((item) => <li key={item.competency_key} className="rounded-xl bg-slate-50 p-3"><div className="flex items-center justify-between gap-3"><span className="font-medium text-slate-900">{item.title}</span><Badge className={item.status === "sufficient" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}>{readinessCompetencyStatusLabel(item.status)}</Badge></div><p className="mt-1 text-sm text-slate-600">{item.gap_reason ?? item.description}</p></li>)}</ul></GlassCard>
                    <GlassCard className="p-5"><h2 className="font-semibold text-slate-950">证据明细</h2><ul className="mt-3 space-y-3">{dossier.evidence.length > 0 ? dossier.evidence.map((item) => <li key={item.evidence_id} className="rounded-xl bg-slate-50 p-3"><p className="font-medium text-slate-900">{item.competency_title}</p><p className="mt-1 text-sm text-slate-600">{readinessEvidenceTypeLabel(item.evidence_type)} · {item.observed_result ?? "结果已记录"}</p></li>) : <li className="text-sm text-slate-600">尚无有效证据，不能授予正式达标结论。</li>}</ul></GlassCard>
                </div>

                <GlassCard className="p-5"><h2 className="font-semibold text-slate-950">当前结论</h2>{dossier.human_decision ? <div className="mt-3 flex gap-3"><CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" /><div><p className="font-medium text-slate-900">{dossier.human_decision.decision_label}</p><p className="mt-1 text-sm text-slate-600">{dossier.human_decision.reason}</p></div></div> : <p className="mt-2 text-sm text-slate-600">尚未记录人工结论。AI 初评不会自动授予 foundation_ready。</p>}</GlassCard>

                <GlassCard className="p-5"><h2 className="font-semibold text-slate-950">记录人工复核</h2>{canReview ? <form className="mt-4 space-y-4" onSubmit={submitDecision}><div><label htmlFor="review-decision" className="text-sm font-medium text-slate-800">复核结论</label><select id="review-decision" value={decision} onChange={(event) => setDecision(event.target.value as DecisionType)} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"><option value="approve_foundation_ready" disabled={!eligibility.eligible}>确认基础训练达标{eligibility.eligible ? "" : "（前置条件未满足）"}</option><option value="request_more_evidence">要求补充证据</option><option value="reject_due_to_integrity_issue">因证据完整性问题拒绝</option><option value="close_without_decision">关闭但不作达标结论</option></select></div><div><label htmlFor="review-reason" className="text-sm font-medium text-slate-800">复核原因</label><textarea id="review-reason" rows={4} required value={reason} onChange={(event) => setReason(event.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="说明依据、风险和下一步；提交失败时内容会保留。" /></div><Button type="submit" disabled={isSubmitting || dossier.snapshot_stale || !reason.trim()}>{isSubmitting ? "正在保存..." : "保存复核结论"}</Button></form> : <p className="mt-2 text-sm text-slate-600">当前账号只能查看档案，不能记录正式复核结论。</p>}</GlassCard>
            </div>
        </main>
    );
}
