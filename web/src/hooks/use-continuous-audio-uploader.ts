"use client";

import { useCallback, useRef, useState } from "react";
import { debug } from "@/lib/debug";

export type UploadStatus = "idle" | "uploading" | "error" | "stopped";

export interface UseContinuousAudioUploaderOptions {
    sessionId: string;
    /** When false, startUpload is a no-op */
    enabled: boolean;
}

export interface ContinuousAudioUploaderState {
    isUploading: boolean;
    segmentCount: number;
    lastError: string | null;
    uploadStatus: UploadStatus;
    startUpload: () => Promise<void>;
    stopUpload: () => Promise<void>;
}

const SEGMENT_TIMESLICE_MS = 15_000;
const WEBM_OPUS_MIME = "audio/webm;codecs=opus";
const WEBM_MIME = "audio/webm";

/**
 * Select the best available MediaRecorder mime type.
 * Prefers webm/opus, falls back to plain webm, then empty string.
 */
function selectMimeType(): string {
    if (typeof MediaRecorder === "undefined") return "";
    if (MediaRecorder.isTypeSupported(WEBM_OPUS_MIME)) return WEBM_OPUS_MIME;
    if (MediaRecorder.isTypeSupported(WEBM_MIME)) return WEBM_MIME;
    return "";
}

/**
 * Hook that continuously captures browser microphone audio via MediaRecorder,
 * splits it into ~15-second segments, uploads each directly to Alibaba Cloud OSS
 * using presigned PUT URLs from the backend, and registers segment metadata.
 *
 * This runs alongside `useAudioRecorder` (which handles real-time PCM → WebSocket
 * for ASR).  This hook creates durable audio-audit-trail segments on OSS.
 */
export function useContinuousAudioUploader(
    options: UseContinuousAudioUploaderOptions,
): ContinuousAudioUploaderState {
    const { sessionId, enabled } = options;

    const [isUploading, setIsUploading] = useState(false);
    const [segmentCount, setSegmentCount] = useState(0);
    const [lastError, setLastError] = useState<string | null>(null);
    const [uploadStatus, setUploadStatus] = useState<UploadStatus>("idle");

    // Refs to persist across renders without triggering re-renders
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const segmentSequenceRef = useRef(0);
    const isStoppingRef = useRef(false);
    const isUploadingRef = useRef(false);

    const resetState = useCallback(() => {
        segmentSequenceRef.current = 0;
        isStoppingRef.current = false;
        isUploadingRef.current = false;
        setSegmentCount(0);
        setLastError(null);
        setUploadStatus("idle");
        setIsUploading(false);
    }, []);

    const cleanupStream = useCallback(() => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach((t) => t.stop());
            streamRef.current = null;
        }
        mediaRecorderRef.current = null;
    }, []);

    /**
     * Upload a single segment blob to OSS via presigned URL + register metadata.
     * Failures are caught and surfaced via lastError — they don't crash the loop.
     */
    const uploadSegment = useCallback(
        async (blob: Blob, sequence: number) => {
            const contentType = blob.type || WEBM_MIME;

            try {
                // Step 1: Request presigned PUT URL from backend
                const signRes = await fetch(
                    `/api/v1/practice/sessions/${sessionId}/audio-upload-urls`,
                    {
                        method: "POST",
                        credentials: "include",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            segment_sequence: sequence,
                            content_type: contentType,
                        }),
                    },
                );

                if (!signRes.ok) {
                    const body = await signRes.json().catch(() => ({}));
                    const msg =
                        body?.error || body?.message || `签名请求失败 (${signRes.status})`;
                    throw new Error(`segment ${sequence}: ${msg}`);
                }

                const signData = await signRes.json();
                const { url, object_key } = signData.data ?? signData;

                // Step 2: PUT blob directly to OSS
                const putRes = await fetch(url, {
                    method: "PUT",
                    headers: { "Content-Type": contentType },
                    body: blob,
                });

                if (!putRes.ok) {
                    throw new Error(
                        `segment ${sequence}: OSS PUT 失败 (${putRes.status})`,
                    );
                }

                // Step 3: Register segment metadata with backend
                const regRes = await fetch(
                    `/api/v1/practice/sessions/${sessionId}/audio-segments`,
                    {
                        method: "POST",
                        credentials: "include",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            segment_sequence: sequence,
                            object_key,
                            size_bytes: blob.size,
                        }),
                    },
                );

                if (!regRes.ok) {
                    const body = await regRes.json().catch(() => ({}));
                    const msg =
                        body?.error || body?.message || `元数据登记失败 (${regRes.status})`;
                    throw new Error(`segment ${sequence}: ${msg}`);
                }

                debug.log(
                    `[ContinuousAudioUploader] segment ${sequence} uploaded (${blob.size} bytes)`,
                );
                setSegmentCount(sequence + 1);
            } catch (err) {
                const message =
                    err instanceof Error
                        ? err.message
                        : `segment ${sequence}: 未知上传错误`;
                debug.warn(
                    `[ContinuousAudioUploader] upload failed: ${message}`,
                );
                setLastError(message);
            }
        },
        [sessionId],
    );

    const startUpload = useCallback(async () => {
        if (!enabled) return;
        if (isUploadingRef.current) return;

        try {
            debug.log("[ContinuousAudioUploader] requesting microphone…");

            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });

            streamRef.current = stream;
            isUploadingRef.current = true;
            setIsUploading(true);
            setUploadStatus("uploading");
            setLastError(null);
            segmentSequenceRef.current = 0;
            setSegmentCount(0);

            const mimeType = selectMimeType();
            const recorderOptions: MediaRecorderOptions = {};
            if (mimeType) recorderOptions.mimeType = mimeType;

            const recorder = new MediaRecorder(stream, recorderOptions);
            mediaRecorderRef.current = recorder;

            recorder.ondataavailable = (event: BlobEvent) => {
                if (event.data.size === 0) return;

                const seq = isStoppingRef.current
                    ? segmentSequenceRef.current // final segment uses same seq
                    : segmentSequenceRef.current++;

                // Fire-and-forget; errors surfaced via lastError
                void uploadSegment(event.data, seq);
            };

            recorder.onerror = () => {
                setLastError("MediaRecorder 运行错误");
                setUploadStatus("error");
            };

            recorder.start(SEGMENT_TIMESLICE_MS);

            debug.log(
                `[ContinuousAudioUploader] recording started (mime=${mimeType || "default"}, timeslice=${SEGMENT_TIMESLICE_MS}ms)`,
            );
        } catch (err) {
            const message =
                err instanceof Error ? err.message : "无法启动音频录制";
            setLastError(message);
            setUploadStatus("error");
            setIsUploading(false);
            isUploadingRef.current = false;
            cleanupStream();
        }
    }, [enabled, uploadSegment, cleanupStream]);

    const stopUpload = useCallback(async () => {
        if (!isUploadingRef.current) return;

        isStoppingRef.current = true;

        const recorder = mediaRecorderRef.current;
        if (recorder && recorder.state !== "inactive") {
            // Request final blob then stop
            recorder.stop();
        }

        // Give a tick for the final ondataavailable to fire
        await new Promise((resolve) => setTimeout(resolve, 100));

        isUploadingRef.current = false;
        setIsUploading(false);
        setUploadStatus("stopped");
        isStoppingRef.current = false;
        cleanupStream();

        debug.log("[ContinuousAudioUploader] recording stopped");
    }, [cleanupStream]);

    return {
        isUploading,
        segmentCount,
        lastError,
        uploadStatus,
        startUpload,
        stopUpload,
    };
}
