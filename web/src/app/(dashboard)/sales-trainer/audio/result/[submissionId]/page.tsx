"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Download, Play, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { useSalesTrainerSubmissionPoll } from "@/hooks/use-sales-trainer-submission-poll";
import { api } from "@/lib/api/client";
import type { SalesTrainerAudioSubmission } from "@/lib/api/types";
import {
    formatPassThresholdLine,
    getAudioPassThreshold,
    getSubmissionStatusLabel,
    isTerminalSubmissionStatus,
} from "@/lib/sales-trainer/learner-presenter";

import { SalesTrainerNextStepPanel } from "../../../next-step-panel";

function formatFileSize(sizeBytes: number): string {
    if (sizeBytes >= 1024 * 1024) {
        return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    if (sizeBytes >= 1024) {
        return `${(sizeBytes / 1024).toFixed(1)} KB`;
    }
    return `${sizeBytes} B`;
}

function getFailureMessage(submission: SalesTrainerAudioSubmission): string | null {
    if (!submission.status.endsWith("failed")) {
        return null;
    }
    if (submission.error_code === "[DEUCATE_TIMEOUT]") {
        return "评分服务响应超时。转写已完成，请稍后刷新结果；如仍未恢复，请联系管理员在后台“学员录音”中重试评分。";
    }
    if (submission.error_code === "[SCORING_PROMPT_REQUIRED]") {
        return "当前训练单元缺少语音作业评分标准，请联系管理员补齐并重新评分。";
    }
    if (submission.error_code === "[SCORING_PROMPT_NOT_PUBLISHED]") {
        return "当前绑定的语音作业评分标准不存在或未发布，请联系管理员检查后重新评分。";
    }
    if (submission.error_code === "[TRANSCRIPT_EMPTY]") {
        return "语音转写结果为空，请确认音频内容是否清晰，或重新上传后再试。";
    }
    if (submission.error_code) {
        return `${submission.error_code}：处理失败，请稍后刷新；如仍未恢复，请联系管理员查看后台操作记录。`;
    }
    return submission.error_message || "处理失败，请稍后刷新；如仍未恢复，请联系管理员查看后台操作记录。";
}

function formatPassedLabel(submission: SalesTrainerAudioSubmission): string {
    if (submission.score_result?.error_code || submission.status.endsWith("failed")) {
        return "待重试";
    }
    if (submission.score_result?.passed === true) {
        return "是";
    }
    if (submission.score_result?.passed === false) {
        return "否";
    }
    return "--";
}

function formatFeedbackItem(item: string | Record<string, unknown>): string {
    if (typeof item === "string") {
        return item;
    }
    const title = item.title ?? item.label ?? item.dimension ?? item.name;
    const text = item.text ?? item.content ?? item.suggestion ?? item.description;
    if (typeof title === "string" && typeof text === "string") {
        return `${title}：${text}`;
    }
    if (typeof text === "string") {
        return text;
    }
    if (typeof title === "string") {
        return title;
    }
    return JSON.stringify(item);
}

export default function SalesTrainerAudioResultPage() {
    const params = useParams<{ submissionId: string }>();
    const {
        submission,
        isLoading,
        isPolling,
        error,
        refresh,
    } = useSalesTrainerSubmissionPoll(params.submissionId);
    const [passThreshold, setPassThreshold] = useState<number | null>(null);

    useEffect(() => {
        let isMounted = true;

        async function loadUnitThreshold() {
            if (!submission?.unit_id) {
                if (isMounted) {
                    setPassThreshold(null);
                }
                return;
            }

            try {
                const unit = await api.salesTrainer.getUnit(submission.unit_id);
                if (isMounted) {
                    setPassThreshold(getAudioPassThreshold(unit));
                }
            } catch {
                if (isMounted) {
                    setPassThreshold(70);
                }
            }
        }

        void loadUnitThreshold();

        return () => {
            isMounted = false;
        };
    }, [submission?.unit_id]);

    const fileUrl = useMemo(
        () => api.salesTrainer.getAudioSubmissionFileUrl(params.submissionId),
        [params.submissionId],
    );

    if (isLoading) {
        return <div className="py-12 text-center text-sm text-slate-500">正在加载语音作业反馈...</div>;
    }

    if (!submission) {
        return (
            <GlassCard className="space-y-4 p-6">
                <p className="text-sm text-red-700">{error || "语音作业结果不存在。"}</p>
                <Link href="/sales-trainer">
                    <Button className="rounded-full">返回销售训练</Button>
                </Link>
            </GlassCard>
        );
    }

    const failureMessage = getFailureMessage(submission);
    const statusLabel = getSubmissionStatusLabel(submission.status);
    const isProcessing = !isTerminalSubmissionStatus(submission.status);
    const improvements = (
        submission.score_result?.improvements
            ?.filter(Boolean)
            .map(formatFeedbackItem) ?? []
    );
    const showImprovements = submission.score_result?.passed === false && improvements.length > 0;

    return (
        <div className="space-y-6 pb-20">
            <div className="space-y-4">
                <Link
                    href="/sales-trainer"
                    className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
                >
                    <ArrowLeft className="h-4 w-4" />
                    返回销售训练
                </Link>
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                        <h1 className="text-3xl font-black tracking-tight text-slate-900">语音作业反馈</h1>
                        <p className="mt-1 text-sm text-slate-500">{submission.original_filename}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Badge className="bg-slate-100 text-slate-700">
                            <span className="sr-only">{submission.status}</span>
                            {statusLabel}
                        </Badge>
                        <Button variant="outline" className="rounded-full" onClick={() => void refresh()}>
                            <RefreshCw className="mr-2 h-4 w-4" />
                            刷新
                        </Button>
                    </div>
                </div>
            </div>

            {isProcessing ? (
                <div className="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
                    转写与评分通常需要 1–3 分钟，页面会自动更新{isPolling ? "中" : ""}。
                </div>
            ) : null}

            {passThreshold !== null ? (
                <GlassCard className="p-5">
                    <p className="text-sm text-slate-600">{formatPassThresholdLine(passThreshold)}</p>
                </GlassCard>
            ) : null}

            <GlassCard className="grid gap-4 p-6 md:grid-cols-3">
                <div>
                    <p className="text-xs text-slate-500">文件大小</p>
                    <p className="mt-1 text-lg font-bold text-slate-900">{formatFileSize(submission.size_bytes)}</p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">上传时间</p>
                    <p className="mt-1 text-lg font-bold text-slate-900">{new Date(submission.created_at).toLocaleString()}</p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">处理状态</p>
                    <StatusIndicator
                        status={
                            submission.status === "scored"
                                ? "success"
                                : submission.status.endsWith("failed")
                                    ? "error"
                                    : "loading"
                        }
                        message={statusLabel}
                    />
                </div>
            </GlassCard>

            {failureMessage ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {failureMessage}
                </div>
            ) : null}

            {submission.unit_id ? (
                <SalesTrainerNextStepPanel unitId={submission.unit_id} />
            ) : null}

            <GlassCard className="space-y-4 p-6">
                <div className="flex flex-wrap gap-3">
                    <a href={fileUrl} target="_blank" rel="noreferrer">
                        <Button className="rounded-full bg-slate-900 text-white">
                            <Play className="mr-2 h-4 w-4" />
                            授权播放
                        </Button>
                    </a>
                    <a href={fileUrl} target="_blank" rel="noreferrer" download>
                        <Button variant="outline" className="rounded-full">
                            <Download className="mr-2 h-4 w-4" />
                            下载语音
                        </Button>
                    </a>
                </div>
                <p className="text-xs text-slate-500">
                    页面通过授权端点读取音频，不直接暴露 storage_key。
                </p>
            </GlassCard>

            <GlassCard className="space-y-3 p-6">
                <h2 className="text-lg font-bold text-slate-900">转写结果</h2>
                <p className="text-sm text-slate-600">
                    {submission.transcript?.transcript_text || "转写尚未完成。"}
                </p>
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-lg font-bold text-slate-900">评分结果</h2>
                {submission.score_result ? (
                    <div className="space-y-3">
                        <div className="grid gap-4 md:grid-cols-3">
                            <div>
                                <p className="text-xs text-slate-500">总分</p>
                                <p className="mt-1 text-2xl font-black text-slate-900">{submission.score_result.total_score ?? "--"}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">通过</p>
                                <p className="mt-1 text-2xl font-black text-slate-900">{formatPassedLabel(submission)}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">模型</p>
                                <p className="mt-1 text-lg font-bold text-slate-900">{submission.score_result.deucate_model || "--"}</p>
                            </div>
                        </div>
                        <p className="text-sm text-slate-600">{submission.score_result.summary || "暂无评分总结。"}</p>
                        {showImprovements ? (
                            <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3">
                                <p className="text-sm font-semibold text-amber-900">改进建议</p>
                                <ul className="mt-2 space-y-1 text-sm text-amber-800">
                                    {improvements.slice(0, 2).map((item) => (
                                        <li key={item}>{item}</li>
                                    ))}
                                </ul>
                            </div>
                        ) : null}
                    </div>
                ) : (
                    <p className="text-sm text-slate-500">评分尚未完成。</p>
                )}
            </GlassCard>
        </div>
    );
}
