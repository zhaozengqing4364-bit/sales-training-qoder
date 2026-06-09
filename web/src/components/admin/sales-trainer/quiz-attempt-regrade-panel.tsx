"use client";

import { useState } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    SalesTrainerQuizAttempt,
    SalesTrainerRegradePreviewResponse,
    SalesTrainerRegradeRunResponse,
} from "@/lib/api/types";

type NoticeState = {
    readonly type: "success" | "error";
    readonly text: string;
};

function numericSnapshotValue(
    snapshot: Record<string, unknown>,
    key: "total_score" | "max_score",
): string {
    const value = snapshot[key];
    return typeof value === "number" ? String(value) : "--";
}

function passedLabel(snapshot: Record<string, unknown>): string {
    const value = snapshot.passed;
    if (value === true) {
        return "通过";
    }
    if (value === false) {
        return "未通过";
    }
    return "待判定";
}

function regradePreviewFromRun(
    result: SalesTrainerRegradeRunResponse,
): SalesTrainerRegradePreviewResponse {
    return {
        target_type: result.target_type,
        target_id: result.target_id,
        target_revision_id: result.target_revision_id,
        impact_scope: result.impact_scope,
        before_snapshot: result.before_snapshot,
        after_snapshot: result.after_snapshot,
    };
}

export function QuizAttemptRegradePanel({ attempt }: { readonly attempt: SalesTrainerQuizAttempt }) {
    const [preview, setPreview] = useState<SalesTrainerRegradePreviewResponse | null>(null);
    const [reason, setReason] = useState("");
    const [notice, setNotice] = useState<NoticeState | null>(null);
    const [isPreviewing, setIsPreviewing] = useState(false);
    const [isRunning, setIsRunning] = useState(false);

    async function handlePreview() {
        setNotice(null);
        setIsPreviewing(true);
        try {
            const result = await api.admin.salesTrainer.previewQuizAttemptRegrade(
                attempt.attempt_id,
                {},
            );
            setPreview(result);
        } catch (error) {
            setNotice({ type: "error", text: getApiErrorMessage(error) });
        } finally {
            setIsPreviewing(false);
        }
    }

    async function handleRun() {
        const trimmedReason = reason.trim();
        if (!trimmedReason) {
            setNotice({ type: "error", text: "请填写重评原因。" });
            return;
        }
        setNotice(null);
        setIsRunning(true);
        try {
            const result = await api.admin.salesTrainer.runQuizAttemptRegrade(
                attempt.attempt_id,
                {
                    target_revision_id: preview?.target_revision_id ?? null,
                    reason: trimmedReason,
                },
            );
            setPreview(regradePreviewFromRun(result));
            setNotice({
                type: "success",
                text: `已生成重评记录，追踪号 ${result.trace_id}`,
            });
        } catch (error) {
            setNotice({ type: "error", text: getApiErrorMessage(error) });
        } finally {
            setIsRunning(false);
        }
    }

    return (
        <GlassCard className="space-y-4 border-orange-100 bg-orange-50/70 p-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="flex items-start gap-3">
                    <div className="rounded-full bg-orange-100 p-2 text-orange-700">
                        <AlertTriangle className="h-4 w-4" />
                    </div>
                    <div>
                        <h2 className="text-base font-bold text-slate-950">重新评分历史记录</h2>
                        <p className="mt-1 text-sm leading-6 text-slate-700">
                            先预览影响范围，确认后只追加重评记录，不覆盖原始成绩和题目快照。
                        </p>
                    </div>
                </div>
                <Button variant="outline" size="sm" onClick={() => void handlePreview()} isLoading={isPreviewing}>
                    <RefreshCw className="mr-2 h-3.5 w-3.5" />
                    预览重评影响
                </Button>
            </div>

            {preview ? (
                <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-lg border border-white/70 bg-white px-4 py-3">
                        <p className="text-xs text-slate-500">影响范围</p>
                        <p className="mt-1 text-sm font-semibold text-slate-900">
                            {preview.impact_scope.record_count} 条历史记录
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                            不影响后续配置，不覆盖历史成绩
                        </p>
                    </div>
                    <div className="rounded-lg border border-white/70 bg-white px-4 py-3">
                        <p className="text-xs text-slate-500">原始成绩</p>
                        <p className="mt-1 text-sm font-semibold text-slate-900">
                            {numericSnapshotValue(preview.before_snapshot, "total_score")} / {numericSnapshotValue(preview.before_snapshot, "max_score")}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">{passedLabel(preview.before_snapshot)}</p>
                    </div>
                    <div className="rounded-lg border border-white/70 bg-white px-4 py-3">
                        <p className="text-xs text-slate-500">重评预览</p>
                        <p className="mt-1 text-sm font-semibold text-slate-900">
                            {numericSnapshotValue(preview.after_snapshot, "total_score")} / {numericSnapshotValue(preview.after_snapshot, "max_score")}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">{passedLabel(preview.after_snapshot)}</p>
                    </div>
                </div>
            ) : null}

            <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="quiz-regrade-reason">重评原因</label>
                <textarea
                    id="quiz-regrade-reason"
                    className="min-h-20 w-full rounded-lg border border-orange-100 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-orange-300 focus:ring-2 focus:ring-orange-100"
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    placeholder="例如：正确答案或 AI 评分规则发布了新修订，需要追加一条可审计的历史重评记录。"
                />
            </div>

            {notice ? (
                <div className={`rounded-lg px-4 py-3 text-sm ${notice.type === "success" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                    {notice.text}
                </div>
            ) : null}

            <div className="flex justify-end">
                <Button
                    variant="danger"
                    onClick={() => void handleRun()}
                    disabled={!preview || isPreviewing}
                    isLoading={isRunning}
                >
                    确认重评
                </Button>
            </div>
        </GlassCard>
    );
}
