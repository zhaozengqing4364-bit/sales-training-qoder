"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { mapMicrophoneAccessError } from "@/hooks/use-audio-recorder";

export type BrowserAudioRecorderState = "idle" | "requesting" | "recording" | "ready" | "error";

function preferredMimeType(): string | undefined {
    if (typeof MediaRecorder === "undefined") return undefined;
    return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((type) => MediaRecorder.isTypeSupported(type));
}

function extensionFor(mimeType: string): string {
    return mimeType.includes("mp4") ? "m4a" : "webm";
}

export function useBrowserAudioRecorder() {
    const [state, setState] = useState<BrowserAudioRecorderState>("idle");
    const [durationSeconds, setDurationSeconds] = useState(0);
    const [audioFile, setAudioFile] = useState<File | null>(null);
    const [audioUrl, setAudioUrl] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const recorderRef = useRef<MediaRecorder | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const chunksRef = useRef<Blob[]>([]);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const audioUrlRef = useRef<string | null>(null);

    const releasePreview = useCallback(() => {
        if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
        setAudioUrl(null);
    }, []);

    const stopStream = useCallback(() => {
        streamRef.current?.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        if (timerRef.current) clearInterval(timerRef.current);
        timerRef.current = null;
    }, []);

    const reset = useCallback(() => {
        if (recorderRef.current?.state === "recording") recorderRef.current.stop();
        stopStream();
        releasePreview();
        recorderRef.current = null;
        chunksRef.current = [];
        setAudioFile(null);
        setDurationSeconds(0);
        setError(null);
        setState("idle");
    }, [releasePreview, stopStream]);

    const start = useCallback(async () => {
        releasePreview();
        setAudioFile(null);
        setDurationSeconds(0);
        setError(null);
        if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
            setState("error");
            setError("当前浏览器不支持直接录音，请使用下方的录音文件上传。 ");
            return;
        }
        setState("requesting");
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
            });
            streamRef.current = stream;
            chunksRef.current = [];
            const mimeType = preferredMimeType();
            const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
            recorderRef.current = recorder;
            recorder.ondataavailable = (event) => {
                if (event.data.size > 0) chunksRef.current.push(event.data);
            };
            recorder.onstop = () => {
                const resolvedType = recorder.mimeType || mimeType || "audio/webm";
                const blob = new Blob(chunksRef.current, { type: resolvedType });
                const file = new File([blob], `讲解录音.${extensionFor(resolvedType)}`, { type: resolvedType });
                const url = URL.createObjectURL(blob);
                audioUrlRef.current = url;
                setAudioFile(file);
                setAudioUrl(url);
                setState("ready");
                stopStream();
            };
            recorder.start();
            setState("recording");
            timerRef.current = setInterval(() => setDurationSeconds((value) => value + 1), 1000);
        } catch (cause) {
            stopStream();
            setState("error");
            setError(mapMicrophoneAccessError(cause));
        }
    }, [releasePreview, stopStream]);

    const stop = useCallback(() => {
        if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    }, []);

    useEffect(() => () => {
        if (recorderRef.current?.state === "recording") recorderRef.current.stop();
        stopStream();
        if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    }, [stopStream]);

    return { state, durationSeconds, audioFile, audioUrl, start, stop, reset, error };
}
