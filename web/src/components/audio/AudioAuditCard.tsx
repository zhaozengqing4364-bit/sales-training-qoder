"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Headphones, Play, Square } from "lucide-react";

import type { AudioAuditPayload } from "@/lib/api/types";
import { api } from "@/lib/api/client";
import { GlassCard } from "@/components/ui/glass-card";
import { cn } from "@/lib/utils";

interface AudioAuditCardProps {
    audioAudit: AudioAuditPayload | null | undefined;
    sessionId: string;
}

const DEGRADED_REASON_COPY: Record<string, string> = {
    upload_failed: "部分音频片段上传失败",
    segments_pending: "部分片段尚未上传完成",
};

const SEGMENT_PLAYBACK_ERROR_COPY: Record<string, string> = {
    SEGMENT_NOT_UPLOADED: "该片段未成功上传",
    SEGMENT_NOT_FOUND: "片段记录不存在",
    SIGNING_FAILED: "获取播放地址失败",
};

function resolveLearnerStatus(
    summary: AudioAuditPayload["summary"] | null | undefined,
): "available" | "partial" | "missing" {
    const status = summary?.learner_status ?? summary?.status;
    return status === "available" || status === "partial" ? status : "missing";
}

function formatDurationMs(ms: number | null | undefined): string {
    if (typeof ms !== "number" || ms <= 0) return "未知时长";
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function formatTotalDurationMs(ms: number): string {
    if (ms <= 0) return "0:00";
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function resolvePlaybackErrorMessage(error: unknown): string {
    const code = error instanceof Error ? error.message : "";
    return SEGMENT_PLAYBACK_ERROR_COPY[code] ?? "加载失败";
}

function SegmentPlayer({
    segment,
    sessionId,
}: {
    segment: AudioAuditPayload["segments"][number];
    sessionId: string;
}) {
    const [playing, setPlaying] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const blobUrlRef = useRef<string | null>(null);

    useEffect(() => {
        return () => {
            if (blobUrlRef.current) {
                URL.revokeObjectURL(blobUrlRef.current);
                blobUrlRef.current = null;
            }
            if (audioRef.current) {
                audioRef.current.pause();
                audioRef.current.src = "";
                audioRef.current = null;
            }
        };
    }, []);

    const handlePlay = useCallback(async () => {
        if (playing) {
            audioRef.current?.pause();
            setPlaying(false);
            return;
        }

        if (error) setError(null);

        if (!audioRef.current) {
            setLoading(true);
            try {
                const url = await api.sessions.getSegmentAudioBlobUrl(
                    sessionId,
                    segment.segment_sequence,
                );
                blobUrlRef.current = url;
                const audio = new Audio(url);
                audioRef.current = audio;

                audio.addEventListener("ended", () => setPlaying(false));
                audio.addEventListener("error", () => {
                    setPlaying(false);
                    setError("加载失败");
                });

                await audio.play();
                setPlaying(true);
            } catch (playbackError) {
                setError(resolvePlaybackErrorMessage(playbackError));
            } finally {
                setLoading(false);
            }
        } else {
            try {
                await audioRef.current.play();
                setPlaying(true);
            } catch {
                setError("播放失败");
            }
        }
    }, [playing, error, sessionId, segment.segment_sequence]);

    const isPlayable = segment.upload_status === "uploaded" && Boolean(segment.playback_path);
    const label = `片段 ${segment.segment_sequence + 1}`;
    const failedUploadMessage =
        segment.upload_status === "failed" && segment.error_message
            ? segment.error_message
            : null;

    return (
        <div className="flex items-center gap-3 rounded-xl bg-zinc-50 p-3">
            <button
                type="button"
                onClick={isPlayable ? handlePlay : undefined}
                disabled={!isPlayable || loading}
                className={cn(
                    "flex items-center justify-center w-9 h-9 rounded-full transition-colors flex-shrink-0",
                    isPlayable
                        ? playing
                            ? "bg-blue-600 text-white hover:bg-blue-700"
                            : "bg-blue-100 text-blue-700 hover:bg-blue-200"
                        : "bg-zinc-200 text-zinc-400 cursor-not-allowed",
                )}
                aria-label={playing ? `暂停 ${label}` : `播放 ${label}`}
            >
                {loading ? (
                    <span className="block w-3.5 h-3.5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                ) : playing ? (
                    <Square className="w-3.5 h-3.5" />
                ) : (
                    <Play className="w-3.5 h-3.5 ml-0.5" />
                )}
            </button>
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-zinc-800">{label}</p>
                    <span className={cn(
                        "text-xs px-2 py-0.5 rounded-full",
                        segment.upload_status === "uploaded"
                            ? "bg-emerald-100 text-emerald-700"
                            : segment.upload_status === "failed"
                                ? "bg-rose-100 text-rose-700"
                                : "bg-zinc-100 text-zinc-600",
                    )}>
                        {segment.upload_status === "uploaded"
                            ? "已上传"
                            : segment.upload_status === "failed"
                                ? "上传失败"
                                : "待上传"}
                    </span>
                </div>
                <p className="text-xs text-zinc-500 mt-0.5">
                    {formatDurationMs(segment.duration_ms)}
                    {typeof segment.size_bytes === "number" && segment.size_bytes > 0
                        ? ` · ${(segment.size_bytes / 1024).toFixed(0)} KB`
                        : ""}
                </p>
                {failedUploadMessage ? (
                    <p className="text-xs text-rose-600 mt-0.5">{failedUploadMessage}</p>
                ) : null}
                {error && <p className="text-xs text-rose-600 mt-0.5">{error}</p>}
            </div>
        </div>
    );
}

export function AudioAuditCardWithSession({ audioAudit, sessionId }: AudioAuditCardProps) {
    const learnerStatus = resolveLearnerStatus(audioAudit?.summary);

    if (!audioAudit || learnerStatus === "missing") {
        return (
            <GlassCard className="p-6 mb-6 border border-slate-200 bg-slate-50/70" data-testid="audio-audit-card">
                <div className="flex items-center gap-3 mb-2">
                    <Headphones className="w-5 h-5 text-slate-400" />
                    <h2 className="text-lg font-semibold text-zinc-900">原始录音</h2>
                </div>
                <p className="text-sm text-slate-600">本次训练未录制原始音频</p>
                <p className="text-xs text-slate-500 mt-1">
                    原始录音用于回听训练过程中的实际表达，未录制时不影响评分与建议。
                </p>
            </GlassCard>
        );
    }

    const { summary, segments } = audioAudit;
    const totalDurationMs = segments.reduce(
        (sum, s) => sum + (typeof s.duration_ms === "number" ? s.duration_ms : 0),
        0,
    );
    const isPartial = learnerStatus === "partial";
    const degradedReasons = (summary.degraded_reasons ?? [])
        .map((reason) => DEGRADED_REASON_COPY[reason] ?? reason)
        .filter(Boolean);

    return (
        <GlassCard className="p-6 mb-6" data-testid="audio-audit-card">
            <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
                <div className="flex items-center gap-3">
                    <Headphones className="w-5 h-5 text-blue-600" />
                    <h2 className="text-lg font-semibold text-zinc-900">原始录音</h2>
                </div>
                <span className={cn(
                    "text-xs font-semibold px-3 py-1 rounded-full border",
                    isPartial
                        ? "text-amber-700 bg-amber-50 border-amber-200"
                        : "text-emerald-700 bg-emerald-50 border-emerald-200",
                )}>
                    {isPartial ? "部分" : "完整"}
                </span>
            </div>

            <p className="text-sm text-zinc-600 mb-4">
                共 {segments.length} 个片段 · 总时长 {formatTotalDurationMs(totalDurationMs)}
            </p>

            {isPartial && degradedReasons.length > 0 ? (
                <ul className="mb-4 list-disc space-y-1 pl-5 text-sm text-amber-700">
                    {degradedReasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                    ))}
                </ul>
            ) : null}

            {segments.length > 0 && (
                <div className="space-y-2">
                    {segments.map((segment) => (
                        <SegmentPlayer
                            key={segment.segment_sequence}
                            segment={segment}
                            sessionId={sessionId}
                        />
                    ))}
                </div>
            )}
        </GlassCard>
    );
}
