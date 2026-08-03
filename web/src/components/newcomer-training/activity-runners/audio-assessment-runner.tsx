"use client";

import { useEffect, useRef, useState } from "react";
import {
    CheckCircle2,
    CircleAlert,
    FileAudio,
    Mic,
    Pause,
    Play,
    RotateCcw,
    Square,
    Trash2,
    UploadCloud,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useCurrentUser } from "@/hooks/use-current-user";
import { api } from "@/lib/api/client";
import type {
    FoundationActivityWorkspace,
    FoundationAudioRunner,
} from "@/lib/api/types/newcomer-training";
import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";
import { trackFoundationUxEvent } from "@/lib/newcomer-training/ux-events";
import { getFoundationUserErrorMessage } from "@/lib/newcomer-training/errors";

import {
    uploadBrowserAudioDraft,
    type BrowserAudioUploadProgress,
} from "./browser-audio-uploader";
import type { ActivityRunnerProps } from "./types";
import { useBrowserAudioRecorder } from "./use-browser-audio-recorder";

const PROCESSING_STATES = new Set([
    "uploaded",
    "validating",
    "normalizing",
    "transcribing",
    "transcript_ready",
    "scoring",
    "reconciling",
]);

const STATE_LABELS: Record<string, string> = {
    draft: "待录制",
    uploading: "正在上传",
    uploaded: "已提交，等待校验",
    validating: "正在校验录音",
    normalizing: "正在准备音频",
    transcribing: "正在转写内容",
    transcript_ready: "转写已完成",
    scoring: "正在评估表现",
    reconciling: "正在同步结果",
    completed: "已完成",
    partially_completed: "部分结果已完成",
    failed_recoverable: "处理暂时失败",
    failed_terminal: "录音无法处理",
    needs_review: "等待人工处理",
    cancelled: "已取消",
    invalidated: "结果已失效",
    expired: "上传已过期",
};

const QUALITY_LABELS: Record<string, string> = {
    low_asr_confidence: "转写置信度偏低",
    insufficient_speech: "有效语音较少",
    excessive_silence: "静音时段较多",
    audio_clipping: "录音存在削波失真",
    clipping_detected: "录音存在削波失真",
    volume_too_low: "录音音量偏低",
    low_volume: "录音音量偏低",
    language_mismatch: "录音语言与任务要求不符",
    no_speech: "未检测到有效语音",
};

function durationLabel(seconds: number): string {
    const safe = Math.max(0, Math.floor(seconds));
    return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

function sizeLabel(bytes: number): string {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function uploadLabel(progress: BrowserAudioUploadProgress): string {
    if (progress.stage === "preparing") return "正在准备分片…";
    if (progress.stage === "finalizing") return "正在校验并提交…";
    return `正在上传 ${progress.completedParts} / ${progress.totalParts}`;
}

function audioRunner(detail: FoundationActivityWorkspace): FoundationAudioRunner | null {
    return detail.runner.kind === "audio_assessment" || detail.runner.kind === "assignment"
        ? detail.runner
        : null;
}

function currentSegmentIndex(runner: FoundationAudioRunner): number {
    const index = runner.segments.findIndex((segment) => segment.state !== "completed");
    return index < 0 ? Math.max(0, runner.segments.length - 1) : index;
}

async function readAudioDuration(file: File): Promise<number> {
    if (typeof document === "undefined") return 0;
    const url = URL.createObjectURL(file);
    try {
        return await new Promise<number>((resolve, reject) => {
            const audio = document.createElement("audio");
            const timeout = window.setTimeout(() => reject(new Error("读取录音时长超时，请重新选择文件。")), 10_000);
            audio.preload = "metadata";
            audio.onloadedmetadata = () => {
                window.clearTimeout(timeout);
                const duration = Number.isFinite(audio.duration) ? Math.ceil(audio.duration) : 0;
                if (duration > 0) resolve(duration);
                else reject(new Error("无法识别录音时长，请选择完整音频文件。"));
            };
            audio.onerror = () => {
                window.clearTimeout(timeout);
                reject(new Error("无法读取录音文件，请选择完整的 MP3、M4A、WAV 或 WebM 音频。"));
            };
            audio.src = url;
        });
    } finally {
        URL.revokeObjectURL(url);
    }
}

function ResultDetails({ runner }: { runner: FoundationAudioRunner }) {
    const completed = runner.segments.filter(
        (segment) => segment.result !== null || segment.transcript !== null,
    );
    if (completed.length === 0) return null;
    return (
        <section aria-label="录音评估结果" className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
            <div>
                <h2 className="font-semibold text-slate-950">表现明细</h2>
                <p className="mt-1 text-sm leading-6 text-slate-600">评分反馈由系统生成，建议结合任务要求自行复盘。</p>
            </div>
            {completed.map((segment) => {
                const result = segment.result;
                return (
                    <article key={segment.segment_id} className="rounded-xl bg-slate-50 p-4">
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                            <h3 className="font-medium text-slate-900">{segment.title}</h3>
                            {result ? <p className="text-lg font-semibold text-slate-950">{result.score.toFixed(1)} 分</p> : <p className="text-sm text-slate-500">文字稿已保存，评分待确认</p>}
                        </div>
                        {segment.transcript ? (
                            <details className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
                                <summary className="cursor-pointer text-sm font-medium text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">查看录音文字稿</summary>
                                <div className="mt-3 text-sm leading-7 text-slate-700">
                                    <p className="text-xs text-slate-500">转写语言：{segment.transcript.language} · 置信度 {Math.round(segment.transcript.confidence * 100)}%</p>
                                    {segment.transcript.segments.length > 0 ? (
                                        <ol className="mt-3 space-y-2">
                                            {segment.transcript.segments.map((item) => (
                                                <li key={`${item.sequence}-${item.start_ms}`} className="grid gap-1 sm:grid-cols-[5rem_minmax(0,1fr)]">
                                                    <span className="text-xs text-slate-500">{durationLabel(item.start_ms / 1000)}</span>
                                                    <span className="break-words whitespace-pre-wrap">{item.text}</span>
                                                </li>
                                            ))}
                                        </ol>
                                    ) : (
                                        <p className="mt-3 break-words whitespace-pre-wrap">{segment.transcript.text}</p>
                                    )}
                                </div>
                            </details>
                        ) : null}
                        {result ? <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                            {result.dimension_scores.map((dimension, index) => (
                                <div key={dimension.dimension_key} className="flex items-center justify-between rounded-lg bg-white px-3 py-2 text-sm">
                                    <dt className="text-slate-600">{dimension.label ?? `评分维度 ${index + 1}`}</dt>
                                    <dd className="font-medium text-slate-900">{dimension.score.toFixed(1)}</dd>
                                </div>
                            ))}
                        </dl> : null}
                        {result && result.feedback.length > 0 ? (
                            <div className="mt-4">
                                <h4 className="text-sm font-medium text-slate-900">反馈</h4>
                                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-600">
                                    {result.feedback.map((item) => <li key={item}>{item}</li>)}
                                </ul>
                            </div>
                        ) : null}
                        {result && result.evidence_spans.length > 0 ? (
                            <div className="mt-4">
                                <h4 className="text-sm font-medium text-slate-900">表达依据</h4>
                                <div className="mt-2 space-y-2">
                                    {result.evidence_spans.map((item, index) => (
                                        <blockquote key={`${item.dimension_key}-${index}`} className="border-l-2 border-blue-300 pl-3 text-sm leading-6 text-slate-600">
                                            “{item.quote}”<span className="block text-xs text-slate-500">{item.rationale}</span>
                                        </blockquote>
                                    ))}
                                </div>
                            </div>
                        ) : null}
                        {result && result.remediation.length > 0 ? (
                            <div className="mt-4 rounded-lg bg-amber-50 p-3">
                                <h4 className="text-sm font-medium text-amber-950">下一步补练</h4>
                                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6 text-amber-900">
                                    {result.remediation.map((item) => <li key={item}>{item}</li>)}
                                </ul>
                            </div>
                        ) : null}
                    </article>
                );
            })}
        </section>
    );
}

export function AudioAssessmentRunner({ detail, onRefresh }: ActivityRunnerProps) {
    const runner = audioRunner(detail);
    const user = useCurrentUser();
    const segmentIndex = runner ? currentSegmentIndex(runner) : 0;
    const segment = runner?.segments[segmentIndex] ?? null;
    const recorder = useBrowserAudioRecorder({
        ownerId: user.data?.user_id ?? "loading-session",
        activityId: detail.activity.id,
        segmentId: segment?.segment_id ?? "primary",
        localDraftTtlSeconds: runner?.rules.local_draft_ttl_seconds,
        maxDurationSeconds: runner?.rules.max_duration_seconds,
        maxSizeBytes: runner?.rules.max_size_bytes,
        sourceChunkSizeBytes: runner?.rules.part_size_bytes,
    });
    const tokenStore = useRef(createIdempotencyTokenStore());
    const uploadAbortRef = useRef<AbortController | null>(null);
    const [pending, setPending] = useState(false);
    const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
    const [uploadProgress, setUploadProgress] = useState<BrowserAudioUploadProgress | null>(null);
    const [error, setError] = useState<string | null>(null);
    const restoredDraftTracked = useRef(false);
    const savedDraftIdTracked = useRef<string | null>(null);

    useEffect(() => {
        if (!recorder.restored || restoredDraftTracked.current) return;
        restoredDraftTracked.current = true;
        trackFoundationUxEvent("draft_restored", detail.activity.type);
    }, [detail.activity.type, recorder.restored]);

    useEffect(() => {
        if (recorder.draft?.state !== "ready" || savedDraftIdTracked.current === recorder.draft.draftId) return;
        savedDraftIdTracked.current = recorder.draft.draftId;
        trackFoundationUxEvent("progress_saved", detail.activity.type);
    }, [detail.activity.type, recorder.draft]);

    async function startActivity() {
        setPending(true);
        setError(null);
        const inputKey = `start:${detail.activity.id}:${detail.enrollment_version}`;
        try {
            const next = await api.newcomerTraining.executeCommand(
                detail.activity.id,
                {
                    command_type: "start",
                    attempt_id: null,
                    expected_enrollment_version: detail.enrollment_version,
                    expected_attempt_version: null,
                    payload: { relearn_of_detail_id: null },
                },
                tokenStore.current.tokenFor(inputKey),
            );
            tokenStore.current.complete(inputKey);
            trackFoundationUxEvent("activity_started", detail.activity.type);
            onRefresh?.(next);
        } catch (cause) {
            setError(getFoundationUserErrorMessage(cause));
        } finally {
            setPending(false);
        }
    }

    async function chooseFile(file: File | undefined) {
        if (!file) return;
        setPending(true);
        setError(null);
        try {
            const duration = await readAudioDuration(file);
            await recorder.importFile(file, duration);
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : "录音文件读取失败，请重新选择。");
        } finally {
            setPending(false);
        }
    }

    async function submitDraft() {
        if (!runner || !segment || !recorder.draft || recorder.draft.state !== "ready") {
            setError("请先完成录音，再开始上传。");
            return;
        }
        const controller = new AbortController();
        uploadAbortRef.current = controller;
        setPending(true);
        setError(null);
        try {
            const next = await uploadBrowserAudioDraft({
                activityId: detail.activity.id,
                workspace: detail,
                segmentId: segment.segment_id,
                draft: recorder.draft,
                signal: controller.signal,
                onProgress: setUploadProgress,
            });
            await recorder.reset();
            onRefresh?.(next);
        } catch (cause) {
            trackFoundationUxEvent("upload_interrupted", detail.activity.type);
            if (cause instanceof DOMException && cause.name === "AbortError") {
                setError("上传已暂停，本地草稿和已完成分片都已保留，可继续上传。");
            } else {
                setError(getFoundationUserErrorMessage(cause));
            }
        } finally {
            uploadAbortRef.current = null;
            setUploadProgress(null);
            setPending(false);
        }
    }

    async function retryStage() {
        if (!detail.attempt || !runner || !segment) return;
        setPending(true);
        setError(null);
        const inputKey = `retry:${segment.submission_id}:${segment.version}`;
        try {
            const next = await api.newcomerTraining.executeCommand(
                detail.activity.id,
                {
                    command_type: "retry_stage",
                    attempt_id: detail.attempt.attempt_id,
                    expected_enrollment_version: null,
                    expected_attempt_version: runner.version,
                    payload: { submission_id: segment.submission_id },
                },
                tokenStore.current.tokenFor(inputKey),
            );
            tokenStore.current.complete(inputKey);
            onRefresh?.(next);
        } catch (cause) {
            setError(getFoundationUserErrorMessage(cause));
        } finally {
            setPending(false);
        }
    }

    async function cancelRun() {
        if (!detail.attempt || !runner) return;
        setPending(true);
        setError(null);
        const inputKey = `cancel:${runner.run_id}:${runner.version}`;
        try {
            const next = await api.newcomerTraining.executeCommand(
                detail.activity.id,
                {
                    command_type: "cancel",
                    attempt_id: detail.attempt.attempt_id,
                    expected_enrollment_version: null,
                    expected_attempt_version: runner.version,
                    payload: {},
                },
                tokenStore.current.tokenFor(inputKey),
            );
            tokenStore.current.complete(inputKey);
            onRefresh?.(next);
        } catch (cause) {
            setError(getFoundationUserErrorMessage(cause));
        } finally {
            setCancelDialogOpen(false);
            setPending(false);
        }
    }

    if (!detail.attempt || !runner) {
        return (
            <section className="rounded-2xl border border-blue-100 bg-blue-50 p-5">
                <h2 className="font-semibold text-blue-950">准备好后开始任务</h2>
                <p className="mt-1 text-sm leading-6 text-blue-900/80">开始后会固定本次题目、录音规则和评分标准，后续规则更新不会改变本次任务。</p>
                <Button className="mt-4" isLoading={pending} onClick={() => void startActivity()}>开始录音任务</Button>
                {error ? <p role="alert" className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
            </section>
        );
    }

    if (!segment) {
        return <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">录音任务内容暂不可用，请刷新后重试。</p>;
    }

    const processing = PROCESSING_STATES.has(segment.state);
    const missingUploadDraft = Boolean(
        segment.state === "uploading"
        && runner.active_upload
        && recorder.state !== "restoring"
        && !recorder.draft,
    );
    const canRecord = ["draft", "uploading", "expired"].includes(segment.state)
        && !processing
        && !missingUploadDraft;
    const canRetry = segment.state === "failed_recoverable" && detail.available_commands.includes("retry_stage");
    const maxMinutes = Math.round(runner.rules.max_duration_seconds / 60);
    const completedSegments = runner.segments.filter((item) => item.state === "completed").length;

    return (
        <div className="space-y-5">
            <ConfirmDialog
                open={cancelDialogOpen}
                onOpenChange={setCancelDialogOpen}
                title="取消当前录音任务？"
                description="已上传录音的后续处理会停止，本地草稿仍保留在此设备，可稍后重新开始。"
                confirmText="取消录音任务"
                variant="warning"
                onConfirm={() => void cancelRun()}
                isLoading={pending}
            />
            {runner.kind === "assignment" ? (
                <section aria-label="场景进度" className="rounded-2xl border border-slate-200 bg-white p-4">
                    <p className="text-sm font-medium text-slate-900">场景回答进度 {completedSegments} / {runner.segments.length}</p>
                    <ol className="mt-3 grid gap-2 sm:grid-cols-3">
                        {runner.segments.map((item, index) => (
                            <li key={item.segment_id} className={`rounded-xl border px-3 py-2 text-sm ${index === segmentIndex ? "border-blue-300 bg-blue-50 text-blue-950" : item.state === "completed" ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-slate-200 text-slate-500"}`}>
                                <span className="font-medium">{index + 1}. {item.title}</span>
                                <span className="mt-0.5 block text-xs">{STATE_LABELS[item.state] ?? "等待开始"}</span>
                            </li>
                        ))}
                    </ol>
                </section>
            ) : null}

            <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                        <p className="text-sm font-medium text-blue-700">{runner.kind === "assignment" ? `第 ${segmentIndex + 1} 段` : "本次讲解"}</p>
                        <h2 className="mt-1 text-lg font-semibold text-slate-950">{segment.title}</h2>
                    </div>
                    <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600">{STATE_LABELS[segment.state] ?? "处理中"}</span>
                </div>
                {segment.customer_context ? <p className="mt-3 rounded-xl bg-white p-3 text-sm leading-6 text-slate-600"><span className="font-medium text-slate-900">客户背景：</span>{segment.customer_context}</p> : null}
                <p className="mt-3 text-base leading-7 text-slate-800">{segment.prompt}</p>
                {segment.preparation_hints.length > 0 ? (
                    <div className="mt-4">
                        <h3 className="text-sm font-medium text-slate-900">准备提示</h3>
                        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-600">
                            {segment.preparation_hints.map((hint) => <li key={hint}>{hint}</li>)}
                        </ul>
                    </div>
                ) : null}
                <p className="mt-4 text-xs text-slate-500">支持浏览器录音或音频文件；最长 {maxMinutes} 分钟，最大 {sizeLabel(runner.rules.max_size_bytes)}。评分完成前可以离开此页。</p>
            </section>

            {segment.quality && !segment.quality.scorable ? (
                <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                    <div className="flex gap-3">
                        <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
                        <div>
                            <h2 className="font-medium text-amber-950">这份录音暂时无法评分</h2>
                            <p className="mt-1 text-sm leading-6 text-amber-900">这不是能力未达标，也不会按零分记录。{segment.quality.flags.map((flag) => QUALITY_LABELS[flag] ?? "录音质量需要复核").join("；")}。</p>
                            <p className="mt-1 text-sm leading-6 text-amber-900">可以结束本次后重新录制，或等待培训负责人处理。</p>
                            {detail.available_commands.includes("cancel") ? (
                                <Button type="button" variant="outline" className="mt-3" isLoading={pending} onClick={() => setCancelDialogOpen(true)}>结束本次，返回重录</Button>
                            ) : null}
                        </div>
                    </div>
                </section>
            ) : null}

            {processing ? (
                <section aria-live="polite" className="rounded-2xl border border-blue-200 bg-blue-50 p-5">
                    <h2 className="font-semibold text-blue-950">{STATE_LABELS[segment.state] ?? "正在处理录音"}</h2>
                    <p className="mt-1 text-sm leading-6 text-blue-900/80">录音已经安全提交。可以返回训练路径，完成后这里会自动显示结果。</p>
                    <Button type="button" variant="outline" className="mt-4" isLoading={pending} onClick={() => setCancelDialogOpen(true)}>取消处理</Button>
                </section>
            ) : null}

            {canRetry ? (
                <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                    <h2 className="font-medium text-amber-950">{segment.error?.message ?? "录音处理暂时失败。"}</h2>
                    <p className="mt-1 text-sm leading-6 text-amber-900">已上传录音和已完成步骤都已保留，可以从失败位置继续。</p>
                    <Button className="mt-3" isLoading={pending} onClick={() => void retryStage()}><RotateCcw className="mr-2 h-4 w-4" />继续处理</Button>
                </section>
            ) : null}

            {segment.state === "failed_terminal" ? (
                <section className="rounded-2xl border border-red-200 bg-red-50 p-4">
                    <h2 className="font-medium text-red-950">这份录音无法继续处理</h2>
                    <p className="mt-1 text-sm leading-6 text-red-900">{segment.error?.message ?? "录音文件可能为空、损坏或格式不受支持。"}</p>
                    <p className="mt-1 text-sm leading-6 text-red-900">当前上传记录已经保留。请结束本次任务后重新录制，或选择一份完整音频文件。</p>
                    {detail.available_commands.includes("cancel") ? (
                        <Button type="button" variant="outline" className="mt-3" isLoading={pending} onClick={() => setCancelDialogOpen(true)}>结束本次，重新录制</Button>
                    ) : null}
                </section>
            ) : null}

            {missingUploadDraft ? (
                <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                    <h2 className="font-medium text-amber-950">此设备没有找到待续传的录音草稿</h2>
                    <p className="mt-1 text-sm leading-6 text-amber-900">服务器已保留完成的上传分片，但不能用另一份录音替换当前会话。请回到原设备继续上传，或结束本次任务后重新录制。</p>
                    {detail.available_commands.includes("cancel") ? (
                        <Button type="button" variant="outline" className="mt-3" isLoading={pending} onClick={() => setCancelDialogOpen(true)}>结束本次，重新录制</Button>
                    ) : null}
                </section>
            ) : null}

            {canRecord ? (
                <section className="rounded-2xl border border-slate-200 bg-white p-5">
                    {recorder.state === "restoring" ? <p role="status" className="text-sm text-slate-500">正在恢复此设备上的录音草稿…</p> : null}
                    {recorder.draft ? (
                        <div className="rounded-xl border border-blue-100 bg-blue-50 p-4">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                    <p className="font-medium text-blue-950">{recorder.restored ? "已恢复本地录音草稿" : "本地录音草稿"}</p>
                                    <p className="mt-1 text-sm text-blue-900/80">{recorder.draft.filename} · {durationLabel(recorder.durationSeconds)} · {sizeLabel(recorder.draft.sizeBytes)}</p>
                                    <p className="mt-1 text-xs text-blue-800">仅保存在此设备，尚未上传。</p>
                                </div>
                                <Button type="button" variant="ghost" size="sm" disabled={pending || recorder.state === "recording"} onClick={() => void recorder.reset()}><Trash2 className="mr-1.5 h-4 w-4" />删除</Button>
                            </div>
                        </div>
                    ) : null}

                    <div className="mt-4 rounded-2xl bg-slate-50 p-5 text-center">
                        {recorder.state === "recording" ? (
                            <>
                                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-red-100 text-red-700"><Mic className="h-6 w-6" /></div>
                                <p className="mt-3 font-semibold text-slate-900">正在录音 {durationLabel(recorder.durationSeconds)}</p>
                                <div className="mt-4 flex flex-wrap justify-center gap-2">
                                    <Button type="button" variant="outline" onClick={recorder.pause}><Pause className="mr-2 h-4 w-4" />暂停</Button>
                                    <Button type="button" onClick={recorder.stop}><Square className="mr-2 h-4 w-4" />结束录音</Button>
                                </div>
                            </>
                        ) : recorder.state === "paused" ? (
                            <>
                                <p className="font-semibold text-slate-900">录音已暂停 {durationLabel(recorder.durationSeconds)}</p>
                                <div className="mt-4 flex flex-wrap justify-center gap-2">
                                    {recorder.canResume ? <Button type="button" variant="outline" onClick={recorder.resume}><Play className="mr-2 h-4 w-4" />继续录音</Button> : null}
                                    <Button type="button" onClick={() => void recorder.finish()}><Square className="mr-2 h-4 w-4" />完成录音</Button>
                                </div>
                            </>
                        ) : recorder.draft?.state === "ready" ? (
                            <>
                                {recorder.audioUrl ? <audio controls className="w-full" src={recorder.audioUrl}>你的浏览器不支持录音试听。</audio> : null}
                                <div className="mt-4 flex flex-wrap justify-center gap-2">
                                    <Button type="button" variant="outline" disabled={pending} onClick={() => void recorder.preview()}><Play className="mr-2 h-4 w-4" />试听</Button>
                                    <Button type="button" isLoading={pending} onClick={() => void submitDraft()}><UploadCloud className="mr-2 h-4 w-4" />继续上传</Button>
                                </div>
                            </>
                        ) : (
                            <>
                                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-blue-100 text-blue-700"><Mic className="h-6 w-6" /></div>
                                <h2 className="mt-3 font-semibold text-slate-900">在这里完成录音</h2>
                                <p className="mt-1 text-sm text-slate-500">录制过程会分块保存在当前设备，可暂停后继续。</p>
                                <Button type="button" className="mt-4" isLoading={recorder.state === "requesting"} disabled={!user.data || pending || recorder.state === "restoring"} onClick={() => void recorder.start()}>开始录音</Button>
                            </>
                        )}
                    </div>

                    <details className="mt-4 rounded-xl border border-slate-200 p-4">
                        <summary className="cursor-pointer text-sm font-medium text-slate-700">无法使用麦克风？选择已有录音</summary>
                        <label className="mt-3 flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border border-dashed border-slate-300 px-3 text-sm text-slate-600">
                            <FileAudio className="h-4 w-4" /><span>选择录音文件</span>
                            <input type="file" aria-label="选择录音文件" accept={runner.rules.allowed_content_types.join(",")} className="sr-only" disabled={pending || recorder.state === "recording"} onChange={(event) => void chooseFile(event.target.files?.[0])} />
                        </label>
                    </details>

                    {uploadProgress ? (
                        <div role="status" aria-live="polite" className="mt-4 rounded-xl bg-blue-50 p-3 text-sm text-blue-900">
                            <p>{uploadLabel(uploadProgress)}</p>
                            {uploadProgress.totalParts > 0 ? <progress className="mt-2 w-full" max={uploadProgress.totalParts} value={uploadProgress.completedParts} aria-label="录音上传进度" /> : null}
                            <Button type="button" variant="ghost" size="sm" className="mt-2" onClick={() => uploadAbortRef.current?.abort()}>暂停上传</Button>
                        </div>
                    ) : null}
                </section>
            ) : null}

            {segment.state === "completed" ? <div className="flex items-center gap-2 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900"><CheckCircle2 className="h-4 w-4" />本段结果已保存。</div> : null}
            <ResultDetails runner={runner} />
            {recorder.error || error ? <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error ?? recorder.error}</p> : null}
        </div>
    );
}
