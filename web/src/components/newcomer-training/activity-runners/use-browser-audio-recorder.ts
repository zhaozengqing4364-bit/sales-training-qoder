"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { mapMicrophoneAccessError } from "@/hooks/use-audio-recorder";
import {
    appendBrowserAudioChunk,
    browserAudioDraftScope,
    cleanupExpiredBrowserAudioDrafts,
    createBrowserAudioDraft,
    createBrowserAudioDraftFromFile,
    createBrowserAudioPreviewBlob,
    deleteBrowserAudioDraft,
    loadBrowserAudioDraft,
    type BrowserAudioDraft,
    updateBrowserAudioDraft,
} from "./browser-audio-draft-store";

export type BrowserAudioRecorderState =
    | "restoring"
    | "idle"
    | "requesting"
    | "recording"
    | "paused"
    | "ready"
    | "error";

interface BrowserAudioRecorderOptions {
    ownerId?: string;
    activityId?: string;
    segmentId?: string;
    localDraftTtlSeconds?: number;
    maxDurationSeconds?: number;
    maxSizeBytes?: number;
    sourceChunkSizeBytes?: number;
}

const DEFAULT_LOCAL_DRAFT_TTL_SECONDS = 7 * 24 * 60 * 60;
const DEFAULT_MAX_DURATION_SECONDS = 30 * 60;
const DEFAULT_MAX_SIZE_BYTES = 100 * 1024 * 1024;
const DEFAULT_SOURCE_CHUNK_SIZE_BYTES = 5 * 1024 * 1024;

function preferredMimeType(): string | undefined {
    if (typeof MediaRecorder === "undefined") return undefined;
    return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((type) =>
        MediaRecorder.isTypeSupported(type),
    );
}

function extensionFor(mimeType: string): string {
    return mimeType.includes("mp4") ? "m4a" : "webm";
}

function stateForDraft(draft: BrowserAudioDraft): BrowserAudioRecorderState {
    return draft.state === "recording" ? "paused" : draft.state;
}

export function useBrowserAudioRecorder(options: BrowserAudioRecorderOptions = {}) {
    const ownerId = options.ownerId ?? "current-session";
    const activityId = options.activityId ?? "unknown-activity";
    const segmentId = options.segmentId ?? "primary";
    const localDraftTtlSeconds = options.localDraftTtlSeconds ?? DEFAULT_LOCAL_DRAFT_TTL_SECONDS;
    const maxDurationSeconds = options.maxDurationSeconds ?? DEFAULT_MAX_DURATION_SECONDS;
    const maxSizeBytes = options.maxSizeBytes ?? DEFAULT_MAX_SIZE_BYTES;
    const sourceChunkSizeBytes = options.sourceChunkSizeBytes ?? DEFAULT_SOURCE_CHUNK_SIZE_BYTES;
    const scopeKey = browserAudioDraftScope(ownerId, activityId, segmentId);
    const [state, setState] = useState<BrowserAudioRecorderState>("restoring");
    const [draft, setDraft] = useState<BrowserAudioDraft | null>(null);
    const [durationSeconds, setDurationSeconds] = useState(0);
    const [audioUrl, setAudioUrl] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [restored, setRestored] = useState(false);
    const recorderRef = useRef<MediaRecorder | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const draftRef = useRef<BrowserAudioDraft | null>(null);
    const durationRef = useRef(0);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const audioUrlRef = useRef<string | null>(null);
    const writeChainRef = useRef<Promise<void>>(Promise.resolve());
    const writeErrorRef = useRef<string | null>(null);
    const discardingRef = useRef(false);
    const mountedRef = useRef(true);
    const unmountingRef = useRef(false);

    const releasePreview = useCallback(() => {
        if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
        if (mountedRef.current) setAudioUrl(null);
    }, []);

    const stopTimer = useCallback(() => {
        if (timerRef.current) clearInterval(timerRef.current);
        timerRef.current = null;
    }, []);

    const stopStream = useCallback(() => {
        streamRef.current?.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        stopTimer();
    }, [stopTimer]);

    const applyDraft = useCallback((next: BrowserAudioDraft | null) => {
        draftRef.current = next;
        durationRef.current = next?.durationSeconds ?? 0;
        if (mountedRef.current) {
            setDraft(next);
            setDurationSeconds(next?.durationSeconds ?? 0);
        }
    }, []);

    const fail = useCallback((message: string) => {
        writeErrorRef.current = message;
        if (mountedRef.current) {
            setError(message);
            setState("error");
        }
        const recorder = recorderRef.current;
        if (recorder && recorder.state !== "inactive") recorder.stop();
    }, []);

    useEffect(() => {
        mountedRef.current = true;
        unmountingRef.current = false;
        let active = true;
        releasePreview();
        applyDraft(null);
        setRestored(false);
        setState("restoring");
        void Promise.all([
            cleanupExpiredBrowserAudioDrafts(),
            loadBrowserAudioDraft(scopeKey),
        ]).then(async ([, restored]) => {
            if (!active) return;
            let resolved = restored;
            if (resolved?.state === "recording") {
                resolved = await updateBrowserAudioDraft(resolved.draftId, { state: "paused" });
            }
            if (!active) return;
            applyDraft(resolved);
            setRestored(resolved !== null);
            setState(resolved ? stateForDraft(resolved) : "idle");
        }).catch((cause) => {
            if (!active) return;
            setError(cause instanceof Error ? cause.message : "本地录音草稿恢复失败，请重新录制。");
            setState("error");
        });
        return () => {
            active = false;
        };
    }, [applyDraft, releasePreview, scopeKey]);

    const enqueueChunk = useCallback((blob: Blob) => {
        if (blob.size === 0 || !draftRef.current || discardingRef.current) return;
        const draftId = draftRef.current.draftId;
        const observedDuration = durationRef.current;
        writeChainRef.current = writeChainRef.current.then(async () => {
            const updated = await appendBrowserAudioChunk({
                draftId,
                blob,
                durationSeconds: observedDuration,
                maxSizeBytes,
                maxDurationSeconds,
            });
            applyDraft(updated);
        }).catch((cause) => {
            fail(cause instanceof Error ? cause.message : "录音写入本地草稿失败，请重新录制。");
        });
    }, [applyDraft, fail, maxDurationSeconds, maxSizeBytes]);

    const start = useCallback(async () => {
        if (state === "requesting" || state === "recording") return;
        releasePreview();
        setError(null);
        writeErrorRef.current = null;
        discardingRef.current = false;
        if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
            setState("error");
            setError("当前浏览器不支持直接录音，请改用录音文件上传。");
            return;
        }
        setState("requesting");
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
            });
            streamRef.current = stream;
            const previous = draftRef.current;
            const mimeType = preferredMimeType();
            const resolvedMimeType = mimeType ?? "audio/webm";
            const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
            const created = await createBrowserAudioDraft({
                scopeKey,
                activityId,
                segmentId,
                source: "browser",
                filename: `讲解录音.${extensionFor(resolvedMimeType)}`,
                mimeType: resolvedMimeType,
                ttlSeconds: localDraftTtlSeconds,
            });
            if (previous) {
                try {
                    await deleteBrowserAudioDraft(previous.draftId);
                } catch (cause) {
                    await deleteBrowserAudioDraft(created.draftId).catch(() => undefined);
                    throw cause;
                }
            }
            applyDraft(created);
            setRestored(false);
            recorderRef.current = recorder;
            recorder.ondataavailable = (event) => enqueueChunk(event.data);
            recorder.onstop = () => {
                void writeChainRef.current.then(async () => {
                    if (discardingRef.current) return;
                    const current = draftRef.current;
                    if (!current) return;
                    const nextState = unmountingRef.current ? "paused" : "ready";
                    const updated = await updateBrowserAudioDraft(current.draftId, {
                        state: nextState,
                        durationSeconds: durationRef.current,
                    });
                    applyDraft(updated);
                    if (mountedRef.current && !writeErrorRef.current) setState(nextState);
                }).catch((cause) => {
                    fail(cause instanceof Error ? cause.message : "录音草稿保存失败，请重新录制。");
                }).finally(stopStream);
            };
            recorder.start(1_000);
            setState("recording");
            timerRef.current = setInterval(() => {
                const next = Math.min(maxDurationSeconds, durationRef.current + 1);
                durationRef.current = next;
                if (mountedRef.current) setDurationSeconds(next);
                if (next >= maxDurationSeconds && recorder.state !== "inactive") {
                    recorder.requestData();
                    recorder.stop();
                }
            }, 1_000);
        } catch (cause) {
            stopStream();
            setState("error");
            setError(
                cause instanceof DOMException
                    ? mapMicrophoneAccessError(cause)
                    : cause instanceof Error
                      ? cause.message
                      : "无法开始录音，请检查麦克风和浏览器存储权限。",
            );
        }
    }, [
        activityId,
        applyDraft,
        enqueueChunk,
        fail,
        localDraftTtlSeconds,
        maxDurationSeconds,
        releasePreview,
        scopeKey,
        segmentId,
        state,
        stopStream,
    ]);

    const pause = useCallback(() => {
        const recorder = recorderRef.current;
        const current = draftRef.current;
        if (!recorder || !current || recorder.state !== "recording") return;
        recorder.requestData();
        recorder.pause();
        stopTimer();
        setState("paused");
        writeChainRef.current = writeChainRef.current.then(async () => {
            applyDraft(await updateBrowserAudioDraft(current.draftId, {
                state: "paused",
                durationSeconds: durationRef.current,
            }));
        }).catch((cause) => {
            fail(cause instanceof Error ? cause.message : "录音草稿保存失败，请重新录制。");
        });
    }, [applyDraft, fail, stopTimer]);

    const resume = useCallback(() => {
        const recorder = recorderRef.current;
        const current = draftRef.current;
        if (!recorder || !current || recorder.state !== "paused") return;
        recorder.resume();
        setState("recording");
        writeChainRef.current = writeChainRef.current.then(async () => {
            applyDraft(await updateBrowserAudioDraft(current.draftId, { state: "recording" }));
        }).catch((cause) => {
            fail(cause instanceof Error ? cause.message : "录音草稿保存失败，请重新录制。");
        });
        timerRef.current = setInterval(() => {
            const next = Math.min(maxDurationSeconds, durationRef.current + 1);
            durationRef.current = next;
            if (mountedRef.current) setDurationSeconds(next);
            if (next >= maxDurationSeconds && recorder.state !== "inactive") {
                recorder.requestData();
                recorder.stop();
            }
        }, 1_000);
    }, [applyDraft, fail, maxDurationSeconds]);

    const stop = useCallback(() => {
        const recorder = recorderRef.current;
        if (recorder && recorder.state !== "inactive") {
            recorder.requestData();
            recorder.stop();
        }
    }, []);

    const finish = useCallback(async () => {
        const recorder = recorderRef.current;
        if (recorder && recorder.state !== "inactive") {
            recorder.requestData();
            recorder.stop();
            return;
        }
        const current = draftRef.current;
        if (!current) return;
        try {
            const updated = await updateBrowserAudioDraft(current.draftId, {
                state: "ready",
                durationSeconds: durationRef.current,
            });
            applyDraft(updated);
            setState("ready");
        } catch (cause) {
            fail(cause instanceof Error ? cause.message : "录音草稿保存失败，请重新录制。");
        }
    }, [applyDraft, fail]);

    const reset = useCallback(async () => {
        const recorder = recorderRef.current;
        discardingRef.current = true;
        recorderRef.current = null;
        if (recorder && recorder.state !== "inactive") recorder.stop();
        stopStream();
        releasePreview();
        const current = draftRef.current;
        await writeChainRef.current.catch(() => undefined);
        if (current) await deleteBrowserAudioDraft(current.draftId);
        applyDraft(null);
        writeErrorRef.current = null;
        discardingRef.current = false;
        setRestored(false);
        setError(null);
        setState("idle");
    }, [applyDraft, releasePreview, stopStream]);

    const preview = useCallback(async () => {
        const current = draftRef.current;
        if (!current) return;
        releasePreview();
        try {
            const blob = await createBrowserAudioPreviewBlob(current);
            const url = URL.createObjectURL(blob);
            audioUrlRef.current = url;
            setAudioUrl(url);
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : "录音试听准备失败，请重试。");
        }
    }, [releasePreview]);

    const importFile = useCallback(async (file: File, fileDurationSeconds: number) => {
        if (state === "recording" || state === "requesting") return;
        releasePreview();
        setError(null);
        try {
            const current = draftRef.current;
            if (current) await deleteBrowserAudioDraft(current.draftId);
            const imported = await createBrowserAudioDraftFromFile({
                scopeKey,
                activityId,
                segmentId,
                file,
                durationSeconds: fileDurationSeconds,
                ttlSeconds: localDraftTtlSeconds,
                chunkSizeBytes: sourceChunkSizeBytes,
                maxSizeBytes,
                maxDurationSeconds,
            });
            applyDraft(imported);
            setRestored(false);
            setState("ready");
        } catch (cause) {
            setState("error");
            setError(cause instanceof Error ? cause.message : "录音文件保存失败，请重新选择。");
        }
    }, [
        activityId,
        applyDraft,
        localDraftTtlSeconds,
        maxDurationSeconds,
        maxSizeBytes,
        releasePreview,
        scopeKey,
        segmentId,
        sourceChunkSizeBytes,
        state,
    ]);

    useEffect(() => () => {
        mountedRef.current = false;
        unmountingRef.current = true;
        releasePreview();
        const recorder = recorderRef.current;
        if (recorder && recorder.state !== "inactive") {
            recorder.requestData();
            recorder.stop();
        } else {
            stopStream();
        }
    }, [releasePreview, stopStream]);

    return {
        state,
        draft,
        durationSeconds,
        audioUrl,
        start,
        pause,
        resume,
        stop,
        finish,
        reset,
        preview,
        importFile,
        restored,
        canResume: recorderRef.current?.state === "paused",
        error,
    };
}
