"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerPath, SalesTrainerUnit } from "@/lib/api/types";
import {
    findLevelForUnit,
    formatPassThresholdLine,
    getAudioPassThreshold,
} from "@/lib/sales-trainer/learner-presenter";

function getAudioPurpose(unit: SalesTrainerUnit): string {
    const rawPurpose = unit.config.audio?.purpose;
    return typeof rawPurpose === "string" && rawPurpose.trim()
        ? rawPurpose
        : "general_audio_scoring";
}

export default function SalesTrainerAudioUploadPage() {
    const params = useParams<{ unitId: string }>();
    const router = useRouter();
    const [unit, setUnit] = useState<SalesTrainerUnit | null>(null);
    const [paths, setPaths] = useState<SalesTrainerPath[]>([]);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function loadData() {
            setIsLoading(true);
            setError(null);
            try {
                const [unitResult, pathResult] = await Promise.all([
                    api.salesTrainer.getUnit(params.unitId),
                    api.salesTrainer.listPaths(),
                ]);
                setUnit(unitResult);
                setPaths(pathResult.items);
            } catch (loadError) {
                setUnit(null);
                setPaths([]);
                setError(getApiErrorMessage(loadError));
            } finally {
                setIsLoading(false);
            }
        }
        void loadData();
    }, [params.unitId]);

    useEffect(() => {
        if (!selectedFile) {
            setPreviewUrl(null);
            return;
        }

        const objectUrl = URL.createObjectURL(selectedFile);
        setPreviewUrl(objectUrl);

        return () => {
            URL.revokeObjectURL(objectUrl);
        };
    }, [selectedFile]);

    const levelContext = useMemo(
        () => findLevelForUnit(paths, params.unitId),
        [paths, params.unitId],
    );
    const pageTitle = levelContext?.level.level_title || unit?.name || "语音作业";
    const pageDescription = levelContext?.level.level_description
        || unit?.description
        || "上传本次语音作业，系统会完成转写和评分。";
    const passThreshold = getAudioPassThreshold(unit);

    async function handleUpload() {
        if (!selectedFile || !unit) {
            setError("请先选择一个音频文件。");
            return;
        }
        setIsUploading(true);
        setError(null);
        try {
            const result = await api.salesTrainer.uploadAudioSubmissionDirect({
                file: selectedFile,
                unit_id: unit.unit_id,
                purpose: getAudioPurpose(unit),
                source_page: "sales_trainer_audio_upload",
            });
            router.push(`/sales-trainer/audio/result/${result.submission_id}`);
        } catch (uploadError) {
            setError(getApiErrorMessage(uploadError));
            setIsUploading(false);
        }
    }

    if (isLoading) {
        return <div className="py-12 text-center text-sm text-slate-500">正在加载语音作业...</div>;
    }

    if (!unit || unit.unit_type !== "audio_scoring") {
        return (
            <GlassCard className="space-y-4 p-6">
                <p className="text-sm text-red-700">{error || "该训练单元不存在，或不是语音作业单元。"}</p>
                <Link href="/sales-trainer">
                    <Button className="rounded-full">返回销售训练</Button>
                </Link>
            </GlassCard>
        );
    }

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
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">{pageTitle}</h1>
                    <p className="mt-1 text-sm text-slate-500">{pageDescription}</p>
                </div>
            </div>

            <GlassCard className="space-y-3 p-6">
                <h2 className="text-lg font-bold text-slate-900">作业说明</h2>
                <p className="text-sm leading-6 text-slate-600">
                    建议先用手机录音 App 录好语音，再回到本页上传。常见音频格式如 MP3、M4A、WAV 等，具体能否上传以后端校验为准。
                </p>
            </GlassCard>

            <GlassCard className="space-y-3 p-6">
                <h2 className="text-lg font-bold text-slate-900">通过标准</h2>
                <p className="text-sm leading-6 text-slate-600">{formatPassThresholdLine(passThreshold)}</p>
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <div className="space-y-2">
                    <h2 className="text-lg font-bold text-slate-900">选择音频文件</h2>
                    <p className="text-sm text-slate-500">
                        不做固定时长限制。若格式或大小不符合后端配置，页面会直接展示后端错误。
                    </p>
                </div>

                <input
                    aria-label="选择音频文件"
                    type="file"
                    accept="audio/*"
                    onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                    className="block w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                    disabled={isUploading}
                />

                {selectedFile ? (
                    <div className="space-y-3 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                        <p>已选择：{selectedFile.name}（{selectedFile.type || "未知格式"}）</p>
                        {previewUrl ? (
                            <audio controls src={previewUrl} className="w-full">
                                您的浏览器不支持音频预览。
                            </audio>
                        ) : null}
                    </div>
                ) : null}

                {error ? (
                    <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                        {error}
                    </div>
                ) : null}

                {isUploading ? (
                    <p className="text-sm text-slate-500">正在上传，请勿关闭页面。</p>
                ) : null}

                <div className="flex justify-end">
                    <Button
                        className="rounded-full bg-slate-900 text-white"
                        onClick={() => void handleUpload()}
                        disabled={isUploading}
                    >
                        <Upload className="mr-2 h-4 w-4" />
                        {isUploading ? "上传中..." : "上传并开始评分"}
                    </Button>
                </div>
            </GlassCard>
        </div>
    );
}
