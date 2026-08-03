"use client";

import Link from "next/link";
import { useState } from "react";
import { AlertCircle, CheckCircle2, Clock3, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api } from "@/lib/api/client";
import { getFoundationUserErrorMessage } from "@/lib/newcomer-training/errors";
import type {
    EvidenceDossierV1,
    ReadinessAppealCreateRequest,
    ReadinessCompetencyProjection,
} from "@/lib/api/types/newcomer-training";

type AppealDraft = Pick<
    ReadinessAppealCreateRequest,
    "target_type" | "target_id" | "reason_category" | "statement"
>;

const STATUS_LABELS: Record<ReadinessCompetencyProjection["status"], string> = {
    sufficient: "已具备复核条件",
    gap: "需要继续练习",
    quality_review: "结果待确认",
    missing: "尚缺训练证据",
};

const STATUS_CLASSES: Record<ReadinessCompetencyProjection["status"], string> = {
    sufficient: "bg-emerald-50 text-emerald-700",
    gap: "bg-amber-50 text-amber-700",
    quality_review: "bg-blue-50 text-blue-700",
    missing: "bg-slate-100 text-slate-700",
};

export function readinessCompetencyStatusLabel(
    status: ReadinessCompetencyProjection["status"],
): string {
    return STATUS_LABELS[status];
}

function CompetencyRow({ competency }: { competency: ReadinessCompetencyProjection }) {
    const score = competency.latest_score !== null && competency.latest_max_score !== null
        ? `${competency.latest_score}/${competency.latest_max_score}`
        : null;
    return (
        <li className="border-b border-slate-100 py-4 last:border-b-0">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                    <h3 className="font-semibold text-slate-950">{competency.title}</h3>
                    <p className="mt-1 text-sm leading-6 text-slate-600">{competency.description}</p>
                    {competency.gap_reason ? (
                        <p className="mt-2 text-sm font-medium text-amber-800">
                            下一步：{competency.gap_reason}
                        </p>
                    ) : null}
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                    {score ? <span className="text-sm tabular-nums text-slate-500">最近 {score}</span> : null}
                    <Badge className={STATUS_CLASSES[competency.status]}>
                        {readinessCompetencyStatusLabel(competency.status)}
                    </Badge>
                </div>
            </div>
        </li>
    );
}

function AppealForm({ dossier }: { dossier: EvidenceDossierV1 }) {
    const firstTargetId = dossier.human_decision?.decision_id
        ?? dossier.evidence[0]?.evidence_id
        ?? "";
    const [draft, setDraft] = useState<AppealDraft>({
        target_type: dossier.human_decision ? "decision" : "evidence",
        target_id: firstTargetId,
        reason_category: "fact_error",
        statement: "",
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [submitted, setSubmitted] = useState(false);

    if (!dossier.human_decision && dossier.evidence.length === 0) {
        return <p className="text-sm text-slate-600">当前还没有可申诉的训练结果。</p>;
    }
    if (submitted) {
        return (
            <div role="status" className="rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-800">
                申诉已提交，处理进度会持续保留在训练档案中。
            </div>
        );
    }
    return (
        <form
            className="space-y-4"
            onSubmit={(event) => {
                event.preventDefault();
                setIsSubmitting(true);
                setError(null);
                void api.newcomerTraining.submitAppeal(
                    { ...draft, dossier_version: dossier.dossier_version },
                    globalThis.crypto?.randomUUID?.() ?? `appeal-${Date.now()}`,
                ).then(() => setSubmitted(true)).catch((submitError) => {
                    setError(getFoundationUserErrorMessage(submitError));
                }).finally(() => setIsSubmitting(false));
            }}
        >
            <div>
                <label htmlFor="appeal-target" className="text-sm font-medium text-slate-800">申诉对象</label>
                <select
                    id="appeal-target"
                    value={`${draft.target_type}:${draft.target_id}`}
                    onChange={(event) => {
                        const [targetType, ...idParts] = event.target.value.split(":");
                        setDraft((current) => ({
                            ...current,
                            target_type: targetType as AppealDraft["target_type"],
                            target_id: idParts.join(":"),
                        }));
                    }}
                    className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                >
                    {dossier.human_decision ? (
                        <option value={`decision:${dossier.human_decision.decision_id}`}>
                            复核结论 · {dossier.human_decision.decision_label}
                        </option>
                    ) : null}
                    {dossier.evidence.map((item) => (
                        <option key={item.evidence_id} value={`evidence:${item.evidence_id}`}>
                            {item.competency_title} · 训练结果
                        </option>
                    ))}
                </select>
            </div>
            <div>
                <label htmlFor="appeal-reason" className="text-sm font-medium text-slate-800">问题类型</label>
                <select
                    id="appeal-reason"
                    value={draft.reason_category}
                    onChange={(event) => setDraft((current) => ({
                        ...current,
                        reason_category: event.target.value as AppealDraft["reason_category"],
                    }))}
                    className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                >
                    <option value="audio_quality">录音质量影响结果</option>
                    <option value="transcript_error">转写内容有误</option>
                    <option value="score_error">评分结果有误</option>
                    <option value="fact_error">档案或复核事实有误</option>
                </select>
            </div>
            <div>
                <label htmlFor="appeal-statement" className="text-sm font-medium text-slate-800">情况说明</label>
                <textarea
                    id="appeal-statement"
                    required
                    minLength={1}
                    maxLength={10000}
                    rows={4}
                    value={draft.statement}
                    onChange={(event) => setDraft((current) => ({ ...current, statement: event.target.value }))}
                    className="mt-1.5 w-full resize-y rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                    placeholder="说明你认为需要核对的具体内容。提交失败时，这段说明会继续保留。"
                />
            </div>
            {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
            <Button type="submit" disabled={isSubmitting || !draft.statement.trim()}>
                {isSubmitting ? "正在提交..." : "提交申诉"}
            </Button>
        </form>
    );
}

export function ReadinessDossierView({ dossier }: { dossier: EvidenceDossierV1 }) {
    const progress = dossier.summary.total_required_activities > 0
        ? Math.round(
            (dossier.summary.completed_required_activities / dossier.summary.total_required_activities) * 100,
        )
        : 0;
    const activeRetraining = dossier.retraining.find((item) =>
        item.status === "assigned" || item.status === "draft_pending_governance",
    );
    return (
        <main className="min-h-screen bg-slate-50 px-4 py-6 md:px-6 md:py-8">
            <div className="mx-auto max-w-5xl space-y-5">
                <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                        <Link href="/newcomer-training" className="text-sm font-medium text-blue-700 hover:underline">
                            返回训练任务
                        </Link>
                        <h1 className="mt-2 text-2xl font-bold text-slate-950">训练档案</h1>
                        <p className="mt-1 text-sm text-slate-600">
                            {dossier.path.title} · {dossier.path.revision_label}
                        </p>
                    </div>
                    <Badge className={dossier.snapshot_stale ? "bg-amber-50 text-amber-700" : "bg-blue-50 text-blue-700"}>
                        {dossier.status_label}
                    </Badge>
                </header>

                {dossier.snapshot_stale ? (
                    <div role="status" className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                        <RefreshCw className="mt-0.5 h-4 w-4 shrink-0" />
                        <div><p className="font-semibold">档案正在根据新结果更新</p><p className="mt-1">{dossier.summary.stale_reason ?? "培训负责人刷新后会继续复核。"}</p></div>
                    </div>
                ) : null}

                <GlassCard className="p-5">
                    <div className="grid gap-5 sm:grid-cols-3">
                        <div><p className="text-sm text-slate-500">必修完成</p><p className="mt-1 text-2xl font-bold text-slate-950">{progress}%</p></div>
                        <div><p className="text-sm text-slate-500">训练证据</p><p className="mt-1 text-2xl font-bold text-slate-950">{dossier.summary.evidence_count}</p></div>
                        <div><p className="text-sm text-slate-500">当前阶段</p><p className="mt-1 font-semibold text-slate-950">{dossier.status_label}</p></div>
                    </div>
                    {dossier.summary.eligibility.reasons.length > 0 ? (
                        <div className="mt-5 rounded-2xl bg-slate-50 p-4">
                            <p className="text-sm font-semibold text-slate-900">接下来需要处理</p>
                            <ul className="mt-2 space-y-1 text-sm text-slate-600">
                                {dossier.summary.eligibility.reasons.map((reason) => <li key={reason}>· {reason}</li>)}
                            </ul>
                        </div>
                    ) : (
                        <div className="mt-5 flex gap-2 rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-800">
                            <CheckCircle2 className="h-4 w-4 shrink-0" />训练材料已具备人工复核条件。
                        </div>
                    )}
                </GlassCard>

                {dossier.human_decision ? (
                    <GlassCard className="border-emerald-200 p-5">
                        <div className="flex items-start gap-3">
                            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                            <div><h2 className="font-semibold text-slate-950">{dossier.human_decision.decision_label}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{dossier.human_decision.reason}</p></div>
                        </div>
                    </GlassCard>
                ) : (
                    <GlassCard className="p-5">
                        <div className="flex items-start gap-3"><Clock3 className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" /><div><h2 className="font-semibold text-slate-950">等待正式结论</h2><p className="mt-2 text-sm leading-6 text-slate-600">AI 辅助内容不会自动决定达标，最终结论由培训负责人依据当前训练档案作出。</p></div></div>
                    </GlassCard>
                )}

                {activeRetraining ? (
                    <GlassCard className="border-amber-200 p-5">
                        <h2 className="font-semibold text-slate-950">补充训练：{activeRetraining.activity_title}</h2>
                        <p className="mt-2 text-sm leading-6 text-slate-600">{activeRetraining.reason}</p>
                        {activeRetraining.next_action?.href ? <Button asChild className="mt-4"><Link href={activeRetraining.next_action.href}>{activeRetraining.next_action.label}</Link></Button> : <p className="mt-3 text-sm text-amber-800">培训负责人正在完善补练内容，完成后会在这里开放。</p>}
                    </GlassCard>
                ) : null}

                <GlassCard className="p-5">
                    <div className="mb-2"><h2 className="text-lg font-semibold text-slate-950">七项基础能力</h2><p className="mt-1 text-sm text-slate-500">结果来自当前训练版本中的有效证据，不用单一平均分掩盖短板。</p></div>
                    <ul>{dossier.competencies.map((competency) => <CompetencyRow key={competency.competency_key} competency={competency} />)}</ul>
                </GlassCard>

                <GlassCard className="p-5">
                    <details>
                        <summary className="cursor-pointer list-none font-semibold text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">训练结果需要核对？提交申诉</summary>
                        <div className="mt-4 border-t border-slate-100 pt-4"><AppealForm dossier={dossier} /></div>
                    </details>
                </GlassCard>

                {dossier.appeals.length > 0 ? (
                    <GlassCard className="p-5"><h2 className="font-semibold text-slate-950">申诉进度</h2><ul className="mt-3 space-y-3">{dossier.appeals.map((appeal) => <li key={appeal.appeal_id} className="flex gap-2 text-sm text-slate-600"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><span>{appeal.statement} · {appeal.status === "resolved" ? "已处理" : appeal.status === "rejected" ? "已反馈" : "处理中"}</span></li>)}</ul></GlassCard>
                ) : null}
            </div>
        </main>
    );
}
