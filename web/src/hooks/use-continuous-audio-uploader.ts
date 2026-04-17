"use client";

import { useCallback, useRef, useState } from "react";
import {
    api,
    ApiRequestError,
    getApiErrorMessage,
    type AudioSegmentFailureToken,
} from "@/lib/api/client";
import { debug } from "@/lib/debug";

export type UploadStatus = "idle" | "uploading" | "error" | "stopped";

export interface UseContinuousAudioUploaderOptions {
    sessionId: string;
    /** When false, startUpload is a no-op */
    enabled: boolean;
    /** Optional microphone stream owned by the main recorder to avoid a second permission prompt. */
    mediaStream?: MediaStream | null;
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
type AudioUploadFailureToken =
    | "signing_failed"
    | "oss_put_failed"
    | "register_failed"
    | "network_error"
    | "unknown";

class AudioSegmentUploadError extends Error {
    readonly errorToken: AudioUploadFailureToken;

    constructor(message: string, errorToken: AudioUploadFailureToken) {
        super(message);
        this.name = "AudioSegmentUploadError";
        this.errorToken = errorToken;
    }
}

type AudioUploadFailureToken =
    | "signing_failed"
    | "oss_put_failed"
    | "register_failed"
    | "network_error"
    | "unknown";

class AudioSegmentUploadError extends Error {
    readonly errorToken: AudioUploadFailureToken;

    constructor(message: string, errorToken: AudioUploadFailureToken) {
        super(message);
        this.name = "AudioSegmentUploadError";
        this.errorToken = errorToken;
    }
}

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

function getUploadErrorMessage(error: unknown): string {
    if (error instanceof ApiRequestError) {
        return getApiErrorMessage(error);
    }

    if (error instanceof Error && error.message.trim()) {
        return error.message;
    }

    return "未知上传错误";
}

function getNetworkAwareToken(
    error: unknown,
    fallback: AudioUploadFailureToken,
): AudioUploadFailureToken {
    if (error instanceof ApiRequestError && error.status === 0) {
        return "network_error";
    }

    if (error instanceof TypeError) {
        return "network_error";
    }

    return fallback;
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
    const { sessionId, enabled, mediaStream } = options;

    const [isUploading, setIsUploading] = useState(false);
    const [segmentCount, setSegmentCount] = useState(0);
    const [lastError, setLastError] = useState<string | null>(null);
    const [uploadStatus, setUploadStatus] = useState<UploadStatus>("idle");

    // Refs to persist across renders without triggering re-renders
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const ownsStreamRef = useRef(false);
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
        if (streamRef.current && ownsStreamRef.current) {
            streamRef.current.getTracks().forEach((t) => t.stop());
        }
        streamRef.current = null;
        ownsStreamRef.current = false;
        mediaRecorderRef.current = null;
    }, []);

    const registerSegmentFailure = useCallback(
        async (sequence: number, errorToken: AudioSegmentFailureToken) => {
            try {
                await api.audioSegments.registerFailure(sessionId, {
                    segment_sequence: sequence,
                    error_token: errorToken,
                });
            } catch (err) {
                debug.warn(
                    `[ContinuousAudioUploader] failure registration failed for segment ${sequence}: ${getApiErrorMessage(err)}`,
                );
            }
        },
        [sessionId],
    );

    /**
     * Upload a single segment blob to OSS via presigned URL + register metadata.
     * Failures are caught and surfaced via lastError — they don't crash the loop.
     */
    const uploadSegment = useCallback(
        async (blob: Blob, sequence: number) => {
            const contentType = blob.type || WEBM_MIME;
            let failureToken: AudioSegmentFailureToken = "unknown";

            try {
                // Step 1: Request presigned PUT URL from backend
                failureToken = "signing_failed";
                const { url, object_key } = await api.audioSegments.createUploadUrl(
                    sessionId,
                    {
                        segment_sequence: sequence,
                        content_type: contentType,
                    },
                );

                // Step 2: PUT blob directly to OSS
                failureToken = "oss_put_failed";
                const putRes = await fetch(url, {
                    method: "PUT",
                    headers: { "Content-Type": contentType },
                    body: blob,
                });

                if (!putRes.ok) {
                    throw new AudioSegmentUploadError(
                        `segment ${sequence}: OSS PUT 失败 (${putRes.status})`,
                        "oss_put_failed",
                    );
                }

                // Step 3: Register segment metadata with backend
                failureToken = "register_failed";
                await api.audioSegments.register(sessionId, {
                    segment_sequence: sequence,
                    object_key,
                    size_bytes: blob.size,
                });

                debug.log(
                    `[ContinuousAudioUploader] segment ${sequence} uploaded (${blob.size} bytes)`,
                );
                setSegmentCount(sequence + 1);
            } catch (err) {
                const errorToken =
                    err instanceof TypeError ||
                    (err instanceof ApiRequestError && err.status === 0)
                        ? "network_error"
                        : failureToken;
                const message =
                    err instanceof TypeError
                        ? `segment ${sequence}: 网络连接失败`
                        : err instanceof Error
                        ? `segment ${sequence}: ${getApiErrorMessage(err)}`
                        : `segment ${sequence}: 未知上传错误`;
                debug.warn(
                    `[ContinuousAudioUploader] upload failed: ${message}`,
                );
                setLastError(message);
                await registerSegmentFailure(sequence, errorToken);
            }
        },
        [sessionId, registerSegmentFailure],
    );

    const startUpload = useCallback(async () => {
        if (!enabled) return;
        if (isUploadingRef.current) return;

        try {
            const stream = mediaStream ?? await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });

            streamRef.current = stream;
            ownsStreamRef.current = !mediaStream;
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
    }, [enabled, mediaStream, uploadSegment, cleanupStream]);

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
