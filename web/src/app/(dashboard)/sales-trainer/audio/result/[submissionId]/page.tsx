"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowLeft, Download, Lightbulb, Play, RefreshCw, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { useSalesTrainerSubmissionPoll } from "@/hooks/use-sales-trainer-submission-poll";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerAudioSubmission } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import {
    getScoreFillClass,
    getScoreStrokeClass,
    getScoreTextColorClass,
} from "@/lib/sales-trainer/journey-presentation";
import {
    formatPassThresholdLine,
    getAudioPassThreshold,
    getSubmissionStatusLabel,
    isTerminalSubmissionStatus,
} from "@/lib/sales-trainer/learner-presenter";

import { SalesTrainerNextStepPanel } from "../../../next-step-panel";

const PASS_THRESHOLD_DIAGNOSTIC_TITLE = "评分标准配置不可用";

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
    if (submission.error_code === "[ASR_ACCOUNT_ARREARS]") {
        return "语音转写服务账户余额不足。请管理员充值或切换 ASR 配置后，在后台“学员录音”中重试转写。";
    }
    if (submission.error_code === "[ASR_AUTH_FAILED]" || submission.error_code === "[ASR_API_KEY_REQUIRED]") {
        return "语音转写服务鉴权失败。请管理员检查 DashScope API Key 配置后重试转写。";
    }
    if (submission.error_code === "[ASR_RATE_LIMITED]") {
        return "语音转写服务当前限流。请稍后刷新结果，或联系管理员在后台重试转写。";
    }
    if (submission.error_code === "[ASR_FILE_DOWNLOAD_FAILED]") {
        return "语音转写服务无法读取本次录音文件。请联系管理员检查对象存储签名、文件访问权限或重新上传录音。";
    }
    if (submission.error_code === "[ASR_TASK_SUBMIT_FAILED]") {
        return "语音转写任务提交失败。请稍后重试；如持续失败，请管理员检查 ASR 服务配置。";
    }
    if (submission.error_code === "[ASR_TASK_WAIT_FAILED]" || submission.error_code === "[ASR_TASK_FAILED]") {
        return "语音转写任务执行失败。请确认录音文件清晰可播放，或联系管理员查看 ASR 上游错误后重试。";
    }
    if (submission.error_code === "[ASR_PROVIDER_FAILED]") {
        return "语音转写服务异常。请稍后刷新；如仍未恢复，请管理员检查 ASR 服务日志。";
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

function getSnapshotItems(snapshot: Record<string, unknown> | null): Array<{
    name?: string;
    current_version?: { version_label?: string; title?: string };
}> {
    const items = snapshot?.items;
    return Array.isArray(items) ? items as Array<{
        name?: string;
        current_version?: { version_label?: string; title?: string };
    }> : [];
}

interface DimensionCriterion {
    key: string;
    label: string;
    description?: string | null;
    weight?: number | null;
}

interface DimensionDisplayItem {
    key: string;
    label: string;
    description: string | null;
    score: number | null;
    maxScore: number | null;
    comment: string | null;
}

function numberOrNull(value: unknown): number | null {
    if (typeof value === "number" && Number.isFinite(value)) {
        return value;
    }
    if (typeof value === "string" && value.trim()) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
}

function getLearnerRubricCriteria(snapshot: Record<string, unknown> | null): DimensionCriterion[] {
    const rubric = snapshot?.learner_rubric;
    if (!rubric || typeof rubric !== "object" || Array.isArray(rubric)) {
        return [];
    }
    const criteria = (rubric as Record<string, unknown>).criteria;
    if (!Array.isArray(criteria)) {
        return [];
    }
    return criteria
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item))
        .map((item) => ({
            key: String(item.key || ""),
            label: String(item.label || item.key || "评分维度"),
            description: typeof item.description === "string" ? item.description : null,
            weight: numberOrNull(item.weight),
        }))
        .filter((item) => item.key.length > 0);
}

function readDimensionScore(
    value: unknown,
    criterion: DimensionCriterion | undefined,
): Omit<DimensionDisplayItem, "key" | "label" | "description"> {
    if (typeof value === "number" || typeof value === "string") {
        return {
            score: numberOrNull(value),
            maxScore: criterion?.weight ?? null,
            comment: null,
        };
    }
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return {
            score: null,
            maxScore: criterion?.weight ?? null,
            comment: null,
        };
    }
    const payload = value as Record<string, unknown>;
    const comment = payload.comment ?? payload.feedback ?? payload.reason ?? payload.description;
    return {
        score: numberOrNull(payload.score ?? payload.value),
        maxScore: numberOrNull(payload.max_score ?? payload.maxScore) ?? criterion?.weight ?? null,
        comment: typeof comment === "string" && comment.trim() ? comment : null,
    };
}

function buildDimensionItems(submission: SalesTrainerAudioSubmission): DimensionDisplayItem[] {
    const dimensionScores = submission.score_result?.dimension_scores;
    if (!dimensionScores || typeof dimensionScores !== "object" || Array.isArray(dimensionScores)) {
        return [];
    }
    const criteria = getLearnerRubricCriteria(submission.score_scheme_snapshot);
    const criterionByKey = new Map(criteria.map((criterion) => [criterion.key, criterion]));
    const rows = criteria.map((criterion) => ({
        key: criterion.key,
        label: criterion.label,
        description: criterion.description ?? null,
        ...readDimensionScore(dimensionScores[criterion.key], criterion),
    }));
    const extraRows = Object.entries(dimensionScores)
        .filter(([key]) => !criterionByKey.has(key))
        .map(([key, value]) => ({
            key,
            label: key,
            description: null,
            ...readDimensionScore(value, undefined),
        }));
    return [...rows, ...extraRows].filter(
        (item) => item.score !== null || item.comment || item.description,
    );
}

function formatDimensionScore(item: DimensionDisplayItem): string {
    if (item.score === null) {
        return "--";
    }
    const score = Number.isInteger(item.score) ? String(item.score) : item.score.toFixed(1);
    if (item.maxScore === null) {
        return score;
    }
    const maxScore = Number.isInteger(item.maxScore) ? String(item.maxScore) : item.maxScore.toFixed(1);
    return `${score} / ${maxScore}`;
}

function ScoreRing({ score, size = 120 }: { score: number; size?: number }) {
    const clamped = Math.max(0, Math.min(100, score));
    const strokeWidth = 8;
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (clamped / 100) * circumference;
    return (
        <div className="relative shrink-0" style={{ width: size, height: size }}>
            <svg className="h-full w-full -rotate-90" viewBox={`0 0 ${size} ${size}`}>
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    strokeWidth={strokeWidth}
                    className="stroke-slate-200"
                />
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    className={cn("transition-all duration-700", getScoreStrokeClass(clamped))}
                />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span
                    className={cn(
                        "text-3xl font-black tabular-nums",
                        getScoreTextColorClass(clamped),
                    )}
                >
                    {score}
                </span>
                <span className="text-xs font-medium text-slate-500">总分</span>
            </div>
        </div>
    );
}

export default function SalesTrainerAudioResultPage() {
    const params = useParams<{ submissionId: string }>();
    const searchParams = useSearchParams();
    const isAdminContext = searchParams.get("from") === "admin";
    const {
        submission,
        isLoading,
        isPolling,
        error,
        timedOut,
        refresh,
    } = useSalesTrainerSubmissionPoll(params.submissionId, {
        isAdminContext,
    });
    const [passThreshold, setPassThreshold] = useState<number | null>(null);
    const [passThresholdError, setPassThresholdError] = useState<string | null>(null);
    const [showAllImprovements, setShowAllImprovements] = useState(false);

    useEffect(() => {
        let isMounted = true;

        async function loadUnitThreshold() {
            if (!submission?.unit_id) {
                if (isMounted) {
                    setPassThreshold(null);
                    setPassThresholdError(null);
                }
                return;
            }

            try {
                const unit = await api.salesTrainer.getUnit(submission.unit_id);
                if (isMounted) {
                    const threshold = getAudioPassThreshold(unit);
                    setPassThreshold(threshold);
                    setPassThresholdError(
                        threshold === null
                            ? "训练单元缺少语音作业通过线配置，页面不会使用默认分数兜底。"
                            : null,
                    );
                }
            } catch (loadError) {
                if (isMounted) {
                    setPassThreshold(null);
                    setPassThresholdError(getApiErrorMessage(loadError));
                }
            }
        }

        void loadUnitThreshold();

        return () => {
            isMounted = false;
        };
    }, [submission?.unit_id]);

    const fileUrl = useMemo(
        () => isAdminContext
            ? api.admin.salesTrainer.getAudioSubmissionFileUrl(params.submissionId)
            : api.salesTrainer.getAudioSubmissionFileUrl(params.submissionId),
        [params.submissionId, isAdminContext],
    );

    if (isLoading) {
        return (
            <div className="space-y-6 pb-20">
                <div className="h-40 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
                <div className="h-64 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
            </div>
        );
    }

    if (error && !submission) {
        return (
            <GlassCard className="space-y-4 p-6">
                <div>
                    <h1 className="text-lg font-bold text-red-900">语音作业结果加载失败</h1>
                    <p className="mt-2 text-sm text-red-700">{error}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Button type="button" variant="primary" onClick={() => void refresh()}>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        重新加载结果
                    </Button>
                    <Button asChild variant="outline">
                        <Link href="/sales-trainer">返回新人训练路径</Link>
                    </Button>
                </div>
            </GlassCard>
        );
    }

    if (!submission) {
        return (
            <GlassCard className="space-y-4 p-6">
                <p className="text-sm text-red-700">语音作业结果不存在。</p>
                <Button asChild variant="primary">
                    <Link href="/sales-trainer">返回新人训练路径</Link>
                </Button>
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
    const strengths = (
        submission.score_result?.strengths
            ?.filter(Boolean)
            .map(formatFeedbackItem) ?? []
    );
    const showImprovements = improvements.length > 0;
    const showStrengths = strengths.length > 0;
    const dimensionItems = buildDimensionItems(submission);

    return (
        <div className="space-y-6 pb-20">
            <div className="space-y-4">
                <Link
                    href="/sales-trainer"
                    className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
                >
                    <ArrowLeft className="h-4 w-4" />
                    返回新人训练路径
                </Link>
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                        <h1 className="text-3xl font-black tracking-tight text-slate-900">语音作业反馈</h1>
                        <p className="mt-1 text-sm text-slate-500">{submission.original_filename}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Badge variant="gray">
                            <span className="sr-only">{submission.status}</span>
                            {statusLabel}
                        </Badge>
                        <Button variant="outline" onClick={() => void refresh()}>
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

            {timedOut ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    <p className="font-semibold text-amber-900">评分耗时较长</p>
                    <p className="mt-1">
                        已等待较久仍未完成，可能是评分队列繁忙。请稍后点击刷新重试；如长时间未恢复，请联系管理员查看后台处理记录。
                    </p>
                    <div className="mt-2">
                        <Button variant="outline" onClick={() => void refresh()}>
                            <RefreshCw className="mr-2 h-4 w-4" />
                            刷新
                        </Button>
                    </div>
                </div>
            ) : null}

            {passThreshold !== null ? (
                <GlassCard className="p-5">
                    <p className="text-sm text-slate-600">{formatPassThresholdLine(passThreshold)}</p>
                </GlassCard>
            ) : null}

            {passThresholdError ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    <p className="font-semibold text-amber-900">{PASS_THRESHOLD_DIAGNOSTIC_TITLE}</p>
                    <p className="mt-1">
                        语音结果已加载，但本关通过线不可用：{passThresholdError}
                    </p>
                </div>
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

            {submission.material_snapshot || submission.score_scheme_snapshot || submission.task_brief_snapshot ? (
                <GlassCard className="space-y-4 p-6">
                    <h2 className="text-lg font-bold text-slate-900">本次训练快照</h2>
                    {submission.task_brief_snapshot ? (
                        <div>
                            <p className="text-xs text-slate-500">任务</p>
                            <p className="mt-1 text-sm text-slate-900">
                                {String(submission.task_brief_snapshot.title || submission.task_brief_snapshot.purpose || "--")}
                            </p>
                        </div>
                    ) : null}
                    {getSnapshotItems(submission.material_snapshot).length ? (
                        <div>
                            <p className="text-xs text-slate-500">材料版本</p>
                            <div className="mt-2 space-y-2">
                                {getSnapshotItems(submission.material_snapshot).map((item) => (
                                    <p key={`${item.name}-${item.current_version?.version_label}`} className="text-sm text-slate-900">
                                        {item.name || "训练材料"} · {item.current_version?.version_label || "--"} · {item.current_version?.title || "--"}
                                    </p>
                                ))}
                            </div>
                        </div>
                    ) : null}
                    {submission.score_scheme_snapshot ? (
                        <div>
                            <p className="text-xs text-slate-500">评分方案</p>
                            <p className="mt-1 text-sm text-slate-900">
                                {String(submission.score_scheme_snapshot.name || "--")} · v{String(submission.score_scheme_snapshot.version || "--")}
                            </p>
                        </div>
                    ) : null}
                </GlassCard>
            ) : null}

            {failureMessage ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {failureMessage}
                </div>
            ) : null}

            {submission.unit_id ? (
                <SalesTrainerNextStepPanel unitId={submission.unit_id} />
            ) : null}

            <GlassCard className="space-y-4 p-6">
                <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100">
                        <Play className="h-4 w-4 text-emerald-700" />
                    </div>
                    <h2 className="text-lg font-bold text-slate-900">录音回放</h2>
                </div>
                <audio
                    controls
                    src={fileUrl}
                    data-testid="audio-playback"
                    className="w-full"
                >
                    您的浏览器不支持音频播放。
                </audio>
                <div className="flex flex-wrap gap-3">
                    <a href={fileUrl} target="_blank" rel="noreferrer" download>
                        <Button variant="outline">
                            <Download className="mr-2 h-4 w-4" />
                            下载语音
                        </Button>
                    </a>
                </div>
                <p className="text-xs text-slate-500">
                    页面通过授权端点读取音频，不直接暴露文件存储地址。
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
                    <div className="space-y-4">
                        <div className="flex flex-col items-center gap-4 md:flex-row md:items-center md:gap-6">
                            {typeof submission.score_result.total_score === "number" ? (
                                <ScoreRing score={submission.score_result.total_score} />
                            ) : (
                                <div className="flex h-[120px] w-[120px] shrink-0 flex-col items-center justify-center rounded-full border-2 border-slate-200">
                                    <span className="text-3xl font-black tabular-nums text-slate-400">--</span>
                                    <span className="text-xs font-medium text-slate-500">总分</span>
                                </div>
                            )}
                            <div className="flex-1 space-y-3">
                                <div className="flex flex-wrap gap-6">
                                    <div>
                                        <p className="text-xs text-slate-500">通过</p>
                                        <p
                                            className={cn(
                                                "mt-1 text-lg font-bold",
                                                submission.score_result.passed === true
                                                    ? "text-emerald-600"
                                                    : submission.score_result.passed === false
                                                      ? "text-rose-600"
                                                      : "text-slate-900",
                                            )}
                                        >
                                            {formatPassedLabel(submission)}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-slate-500">评分模型</p>
                                        <p className="mt-1 text-sm font-bold text-slate-900">
                                            {submission.score_result.deucate_model || "--"}
                                        </p>
                                    </div>
                                </div>
                                <p className="text-sm leading-6 text-slate-600">
                                    {submission.score_result.summary || "暂无评分总结。"}
                                </p>
                            </div>
                        </div>
                        {dimensionItems.length ? (
                            <div className="space-y-3">
                                <p className="text-sm font-semibold text-slate-900">分项评分</p>
                                <div className="grid gap-3 md:grid-cols-2">
                                    {dimensionItems.map((item) => {
                                        const scorePercent =
                                            item.score !== null && item.maxScore !== null && item.maxScore > 0
                                                ? (item.score / item.maxScore) * 100
                                                : null;
                                        return (
                                            <div key={item.key} className="rounded-2xl border border-slate-100 bg-white px-4 py-3">
                                                <div className="flex items-start justify-between gap-3">
                                                    <div>
                                                        <p className="text-sm font-semibold text-slate-900">{item.label}</p>
                                                        {item.description ? (
                                                            <p className="mt-1 text-xs leading-5 text-slate-500">{item.description}</p>
                                                        ) : null}
                                                    </div>
                                                    <span
                                                        className={cn(
                                                            "shrink-0 rounded-full bg-slate-50 px-3 py-1 text-xs font-semibold tabular-nums",
                                                            scorePercent !== null
                                                                ? getScoreTextColorClass(scorePercent)
                                                                : "text-slate-600",
                                                        )}
                                                    >
                                                        {formatDimensionScore(item)}
                                                    </span>
                                                </div>
                                                {scorePercent !== null ? (
                                                    <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                                                        <div
                                                            className={cn(
                                                                "h-full rounded-full transition-all duration-500",
                                                                getScoreFillClass(scorePercent),
                                                            )}
                                                            style={{ width: `${Math.min(100, Math.max(0, scorePercent))}%` }}
                                                        />
                                                    </div>
                                                ) : null}
                                                {item.comment ? (
                                                    <p className="mt-2 text-sm leading-6 text-slate-600">{item.comment}</p>
                                                ) : null}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        ) : null}
                        {showStrengths ? (
                            <div className="rounded-2xl bg-emerald-50/50 px-4 py-3">
                                <p className="flex items-center gap-2 text-sm font-semibold text-emerald-900">
                                    <Sparkles className="h-4 w-4 text-emerald-600" />
                                    优点
                                </p>
                                <ul className="mt-2 space-y-1.5 text-sm text-slate-600">
                                    {strengths.map((item, index) => (
                                        <li key={`${index}-${item}`} className="flex items-start gap-2">
                                            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-emerald-500" />
                                            <span>{item}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ) : null}
                        {showImprovements ? (
                            <div className="rounded-2xl bg-amber-50/50 px-4 py-3">
                                <p className="flex items-center gap-2 text-sm font-semibold text-amber-900">
                                    <Lightbulb className="h-4 w-4 text-amber-600" />
                                    改进建议
                                </p>
                                <ul className="mt-2 space-y-1.5 text-sm text-slate-600">
                                    {improvements
                                        .slice(0, showAllImprovements ? undefined : 2)
                                        .map((item) => (
                                            <li key={item} className="flex items-start gap-2">
                                                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-amber-500" />
                                                <span>{item}</span>
                                            </li>
                                        ))}
                                </ul>
                                {improvements.length > 2 ? (
                                    <button
                                        type="button"
                                        className="mt-2 text-xs font-medium text-amber-700 hover:text-amber-900"
                                        onClick={() => setShowAllImprovements((current) => !current)}
                                    >
                                        {showAllImprovements
                                            ? "收起"
                                            : `查看全部 ${improvements.length} 条`}
                                    </button>
                                ) : null}
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
