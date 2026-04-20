"use client";

import { useCallback, useRef, useState } from "react";
import { ApiRequestError, api, getApiErrorMessage } from "@/lib/api/client";
import { debug } from "@/lib/debug";

export type UploadStatus = "idle" | "uploading" | "error" | "stopped";
export type AudioEvidenceFlushStatus = "completed" | "failed" | "timed_out" | "not_started";

export interface AudioEvidenceFlushResult {
    status: AudioEvidenceFlushStatus;
    pendingUploads: number;
    error: string | null;
}

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
    pendingUploads: number;
    lastError: string | null;
    uploadStatus: UploadStatus;
    pendingUploads: number;
    startUpload: () => Promise<void>;
    stopUpload: () => Promise<void>;
    flushAndStop: (options?: { timeoutMs?: number }) => Promise<AudioEvidenceFlushResult>;
}

const SEGMENT_TIMESLICE_MS = 15_000;
const FINAL_SEGMENT_SETTLE_MS = 100;
const DEFAULT_FLUSH_TIMEOUT_MS = 5_000;
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
    const [pendingUploads, setPendingUploads] = useState(0);
    const [lastError, setLastError] = useState<string | null>(null);
    const [uploadStatus, setUploadStatus] = useState<UploadStatus>("idle");
    const [pendingUploads, setPendingUploads] = useState(0);

    // Refs to persist across renders without triggering re-renders
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const ownsStreamRef = useRef(false);
    const segmentSequenceRef = useRef(0);
    const isStoppingRef = useRef(false);
    const isUploadingRef = useRef(false);
    const pendingUploadPromisesRef = useRef<Set<Promise<void>>>(new Set());
    const pendingUploadCountRef = useRef(0);
    const uploadErrorRef = useRef<string | null>(null);

    const resetState = useCallback(() => {
        segmentSequenceRef.current = 0;
        isStoppingRef.current = false;
        isUploadingRef.current = false;
        pendingUploadPromisesRef.current.clear();
        pendingUploadCountRef.current = 0;
        uploadErrorRef.current = null;
        setSegmentCount(0);
        setPendingUploads(0);
        setLastError(null);
        setPendingUploads(0);
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

    const trackUpload = useCallback((uploadPromise: Promise<void>) => {
        pendingUploadCountRef.current += 1;
        setPendingUploads(pendingUploadCountRef.current);

        const trackedPromise = uploadPromise.finally(() => {
            pendingUploadPromisesRef.current.delete(trackedPromise);
            pendingUploadCountRef.current = Math.max(0, pendingUploadCountRef.current - 1);
            setPendingUploads(pendingUploadCountRef.current);
        });

        pendingUploadPromisesRef.current.add(trackedPromise);
    }, []);

    const waitForPendingUploads = useCallback(async (timeoutMs: number): Promise<"completed" | "timed_out"> => {
        const deadline = Date.now() + timeoutMs;

        while (pendingUploadPromisesRef.current.size > 0) {
            const remainingMs = deadline - Date.now();
            if (remainingMs <= 0) {
                return "timed_out";
            }

            const currentBatch = Array.from(pendingUploadPromisesRef.current);
            await Promise.race([
                Promise.allSettled(currentBatch),
                new Promise((resolve) => setTimeout(resolve, remainingMs)),
            ]);
        }

        return "completed";
    }, []);

    /**
     * Upload a single segment blob to OSS via presigned URL + register metadata.
     * Failures are caught and surfaced via lastError — they don't crash the loop.
     */
    const uploadSegment = useCallback(
        async (blob: Blob, sequence: number): Promise<boolean> => {
            const contentType = blob.type || WEBM_MIME;

            const registerFailure = async (
                errorToken: AudioUploadFailureToken,
            ) => {
                try {
                    await api.practice.audioSegments.registerFailure(sessionId, {
                        segment_sequence: sequence,
                        error_token: errorToken,
                    });
                } catch (failureError) {
                    debug.warn(
                        `[ContinuousAudioUploader] failure registration failed for segment ${sequence}: ${getUploadErrorMessage(failureError)}`,
                    );
                }
            };

            try {
                // Step 1: Request presigned PUT URL from backend
                let uploadUrl: string;
                let objectKey: string;
                try {
                    const signedUpload = await api.practice.audioSegments.createUploadUrl(
                        sessionId,
                        {
                            segment_sequence: sequence,
                            content_type: contentType,
                        },
                    );
                    uploadUrl = signedUpload.url;
                    objectKey = signedUpload.object_key;
                } catch (signError) {
                    const errorToken = getNetworkAwareToken(
                        signError,
                        "signing_failed",
                    );
                    await registerFailure(errorToken);
                    throw new AudioSegmentUploadError(
                        `segment ${sequence}: ${getUploadErrorMessage(signError)}`,
                        errorToken,
                    );
                }

                // Step 2: PUT blob directly to OSS
                try {
                    const putRes = await fetch(uploadUrl, {
                        method: "PUT",
                        headers: { "Content-Type": contentType },
                        body: blob,
                    });

                    if (!putRes.ok) {
                        throw new Error(
                            `OSS PUT 失败 (${putRes.status})`,
                        );
                    }
                } catch (putError) {
                    const errorToken = getNetworkAwareToken(
                        putError,
                        "oss_put_failed",
                    );
                    await registerFailure(errorToken);
                    throw new AudioSegmentUploadError(
                        `segment ${sequence}: ${getUploadErrorMessage(putError)}`,
                        errorToken,
                    );
                }

                // Step 3: Register segment metadata with backend
                try {
                    await api.practice.audioSegments.register(sessionId, {
                        segment_sequence: sequence,
                        object_key: objectKey,
                        size_bytes: blob.size,
                    });
                } catch (registerError) {
                    const errorToken = getNetworkAwareToken(
                        registerError,
                        "register_failed",
                    );
                    await registerFailure(errorToken);
                    throw new AudioSegmentUploadError(
                        `segment ${sequence}: ${getUploadErrorMessage(registerError)}`,
                        errorToken,
                    );
                }

                debug.log(
                    `[ContinuousAudioUploader] segment ${sequence} uploaded (${blob.size} bytes)`,
                );
                setSegmentCount(sequence + 1);
                return true;
            } catch (err) {
                const message =
                    err instanceof Error && err.message.trim()
                        ? err.message
                        : `segment ${sequence}: 未知上传错误`;
                debug.warn(
                    `[ContinuousAudioUploader] upload failed: ${message}`,
                );
                uploadErrorRef.current = message;
                setLastError(message);
                return false;
            }
        },
        [sessionId],
    );

    const trackSegmentUpload = useCallback((blob: Blob, sequence: number) => {
        const pending = uploadSegment(blob, sequence);
        pendingUploadsRef.current.add(pending);
        setPendingUploads(pendingUploadsRef.current.size);
        void pending.finally(() => {
            pendingUploadsRef.current.delete(pending);
            setPendingUploads(pendingUploadsRef.current.size);
        });
    }, [uploadSegment]);

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
            uploadFailureRef.current = null;
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

                // Uploads remain backgrounded during recording, but tracked so
                // end-of-session can wait for the durable evidence trail.
                trackUpload(uploadSegment(event.data, seq));
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
    }, [enabled, mediaStream, uploadSegment, cleanupStream, trackUpload]);

    const flushAndStop = useCallback(async (
        options: { timeoutMs?: number } = {},
    ): Promise<AudioEvidenceFlushResult> => {
        const timeoutMs = options.timeoutMs ?? DEFAULT_FLUSH_TIMEOUT_MS;
        if (!isUploadingRef.current) {
            return {
                status: lastError ? "failed" : "not_started",
                pendingUploads: pendingUploadCountRef.current,
                error: lastError,
            };
        }

        isStoppingRef.current = true;
        setUploadStatus("flushing");
        const recorder = mediaRecorderRef.current;
        if (recorder && recorder.state !== "inactive") {
            // Request final blob then stop
            recorder.stop();
        }

        // Give a tick for the final ondataavailable to fire and be tracked.
        await new Promise((resolve) => setTimeout(resolve, FINAL_SEGMENT_SETTLE_MS));

        const waitResult = await waitForPendingUploads(timeoutMs);
        const error = uploadErrorRef.current || lastError;
        const status: AudioEvidenceFlushStatus = waitResult === "timed_out"
            ? "timed_out"
            : error
            ? "failed"
            : "completed";

        isUploadingRef.current = false;
        setIsUploading(false);
        setUploadStatus(status === "failed" ? "error" : "stopped");
        isStoppingRef.current = false;
        cleanupStream();

        debug.log(`[ContinuousAudioUploader] recording stopped with evidence status=${status}`);

        return {
            status,
            pendingUploads: pendingUploadCountRef.current,
            error,
        };
    }, [cleanupStream, lastError, waitForPendingUploads]);

    const stopUpload = useCallback(async () => {
        await flushAndStop({ timeoutMs: DEFAULT_FLUSH_TIMEOUT_MS });
    }, [flushAndStop]);

    const stopUpload = useCallback(async () => {
        await flushAndStop();
    }, [flushAndStop]);

    return {
        isUploading,
        segmentCount,
        pendingUploads,
        lastError,
        uploadStatus,
        pendingUploads,
        startUpload,
        stopUpload,
        flushAndStop,
    };
}
