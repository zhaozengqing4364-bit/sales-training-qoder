"use client";

import { useRef, useState } from "react";
import { FileAudio, Mic, RotateCcw, Square } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";
import { AudioPreparationPack } from "./audio-preparation-pack";
import type { ActivityRunnerProps } from "./types";
import { useBrowserAudioRecorder } from "./use-browser-audio-recorder";

function durationLabel(seconds: number): string {
    return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export function AudioAssessmentRunner({ detail, onRefresh }: ActivityRunnerProps) {
    const runner = detail.runner.type === "audio_assessment" ? detail.runner : null;
    const recorder = useBrowserAudioRecorder();
    const [fallbackFile, setFallbackFile] = useState<File | null>(null);
    const [confirmed, setConfirmed] = useState(false);
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const tokenStore = useRef(createIdempotencyTokenStore());
    const file = recorder.audioFile ?? fallbackFile;
    const materialUrl = runner?.material_version_id
        ? api.salesTrainer.getMaterialVersionFileUrl(runner.material_version_id, {
            disposition: "inline",
        })
        : null;

    async function submit() {
        if (!file) {
            setError("请先完成录音，或选择已有录音文件。");
            return;
        }
        if (!confirmed) {
            setError("请先看完并确认材料、评分重点和讲解示例。");
            return;
        }
        setPending(true);
        setError(null);
        const inputKey = [
            detail.activity.activity_id,
            file.name,
            file.size,
            file.lastModified,
            runner?.material_version_id ?? "",
            runner?.scoring_rubric_revision_id ?? "",
        ].join(":");
        try {
            const updated = await api.newcomerTraining.submitAudio(
                detail.activity.activity_id,
                {
                    file,
                    client_token: tokenStore.current.tokenFor(inputKey),
                    confirmed_material_version_id: runner?.material_version_id,
                    confirmed_scoring_rubric_revision_id:
                        runner?.scoring_rubric_revision_id,
                },
            );
            tokenStore.current.complete(inputKey);
            onRefresh?.(updated);
        } catch (cause) {
            setError(getApiErrorMessage(cause));
        } finally {
            setPending(false);
        }
    }

    if (!runner) return null;

    return (
        <div className="space-y-5">
            <AudioPreparationPack
                runner={runner}
                materialUrl={materialUrl}
                confirmed={confirmed}
                disabled={pending || recorder.state === "recording"}
                onConfirmedChange={setConfirmed}
            />

            <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5 text-center">
                {recorder.state === "recording" ? (
                    <>
                        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-red-700">
                            <Mic className="h-7 w-7 animate-pulse" />
                        </div>
                        <p className="mt-3 font-semibold text-slate-900">
                            正在录音 {durationLabel(recorder.durationSeconds)}
                        </p>
                        <Button type="button" className="mt-4" onClick={recorder.stop}>
                            <Square className="mr-2 h-4 w-4" />结束录音
                        </Button>
                    </>
                ) : recorder.audioUrl ? (
                    <>
                        <audio className="w-full" controls src={recorder.audioUrl}>
                            你的浏览器不支持录音试听。
                        </audio>
                        <div className="mt-4 flex justify-center gap-2">
                            <Button type="button" variant="outline" onClick={recorder.reset}>
                                <RotateCcw className="mr-2 h-4 w-4" />重新录音
                            </Button>
                            <Button type="button" onClick={() => void submit()} isLoading={pending} disabled={!confirmed}>
                                提交录音评分
                            </Button>
                        </div>
                    </>
                ) : (
                    <>
                        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-blue-100 text-blue-700">
                            <Mic className="h-7 w-7" />
                        </div>
                        <h2 className="mt-3 font-semibold text-slate-900">
                            确认准备内容后，直接在这里录音
                        </h2>
                        <p className="mt-1 text-sm text-slate-500">
                            录完可先试听，不满意可以重录。
                        </p>
                        <Button
                            type="button"
                            className="mt-4"
                            onClick={() => void recorder.start()}
                            isLoading={recorder.state === "requesting"}
                            disabled={!confirmed}
                        >
                            开始录音
                        </Button>
                    </>
                )}
            </section>

            <details className="rounded-xl border border-slate-200 bg-white p-4">
                <summary className="cursor-pointer text-sm font-medium text-slate-700">
                    无法使用麦克风？上传已有录音
                </summary>
                <label className="mt-3 flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border border-dashed border-slate-300 px-3 text-sm text-slate-600">
                    <FileAudio className="h-4 w-4" />
                    <span>{fallbackFile?.name ?? "选择录音文件"}</span>
                    <input
                        type="file"
                        aria-label="选择录音文件"
                        accept="audio/*"
                        className="sr-only"
                        onChange={(event) => setFallbackFile(event.target.files?.[0] ?? null)}
                    />
                </label>
                {fallbackFile && !recorder.audioFile ? (
                    <Button
                        type="button"
                        className="mt-3"
                        onClick={() => void submit()}
                        isLoading={pending}
                        disabled={!confirmed}
                    >
                        提交录音评分
                    </Button>
                ) : null}
            </details>
            {recorder.error || error ? (
                <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">
                    {error ?? recorder.error}
                </p>
            ) : null}
        </div>
    );
}
