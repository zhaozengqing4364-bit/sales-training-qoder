"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
    ArrowLeft,
    BookOpen,
    Download,
    Eye,
    FileText,
    Target,
    Upload,
    UploadCloud,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { GlassCard } from "@/components/ui/glass-card";
import { markdownComponents } from "@/components/sales-trainer/coo-markdown-components";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    SalesTrainerLearnerMaterialVersion,
    SalesTrainerLearnerRubric,
    SalesTrainerUnit,
    SalesTrainerUnitBrief,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";
import {
    formatPassThresholdLine,
    getAudioPassThreshold,
} from "@/lib/sales-trainer/learner-presenter";

const PASS_THRESHOLD_DIAGNOSTIC_TITLE = "评分标准配置缺失";

type MaterialPreviewState = {
    versionId: string;
    text: string;
    error: string | null;
};

function getAudioPurpose(unit: SalesTrainerUnit): string {
    const rawPurpose = unit.config.audio?.purpose;
    return typeof rawPurpose === "string" && rawPurpose.trim()
        ? rawPurpose
        : "general_audio_scoring";
}

function getRubric(brief: SalesTrainerUnitBrief | null): SalesTrainerLearnerRubric | null {
    const rubric = brief?.score_scheme?.learner_rubric;
    if (!rubric || typeof rubric !== "object" || Array.isArray(rubric)) {
        return null;
    }
    return rubric as SalesTrainerLearnerRubric;
}

function isTextPreview(version: SalesTrainerLearnerMaterialVersion): boolean {
    const type = version.content_type.toLowerCase();
    return type.includes("markdown") || type.startsWith("text/");
}

function isAudioPreview(version: SalesTrainerLearnerMaterialVersion): boolean {
    return version.content_type.toLowerCase().startsWith("audio/");
}

function isVideoPreview(version: SalesTrainerLearnerMaterialVersion): boolean {
    return version.content_type.toLowerCase().startsWith("video/");
}

function isPdfPreview(version: SalesTrainerLearnerMaterialVersion): boolean {
    return version.content_type.toLowerCase() === "application/pdf";
}

function canPreviewInline(version: SalesTrainerLearnerMaterialVersion): boolean {
    return isTextPreview(version) || isAudioPreview(version) || isVideoPreview(version) || isPdfPreview(version);
}

export default function SalesTrainerAudioUploadPage() {
    const params = useParams<{ unitId: string }>();
    const router = useRouter();
    const [unit, setUnit] = useState<SalesTrainerUnit | null>(null);
    const [brief, setBrief] = useState<SalesTrainerUnitBrief | null>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [confirmedMaterialVersionId, setConfirmedMaterialVersionId] = useState<string | null>(null);
    const [activeMaterialVersionId, setActiveMaterialVersionId] = useState<string | null>(null);
    const [materialPreview, setMaterialPreview] = useState<MaterialPreviewState | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function loadData() {
            setIsLoading(true);
            setError(null);
            try {
                const briefResult = await api.salesTrainer.getUnitBrief(params.unitId);
                setBrief(briefResult);
                setUnit(briefResult.unit);
            } catch (loadError) {
                setBrief(null);
                setUnit(null);
                setError(getApiErrorMessage(loadError));
            } finally {
                setIsLoading(false);
            }
        }
        void loadData();
    }, [params.unitId]);

    const previewUrl = useMemo(
        () => selectedFile ? URL.createObjectURL(selectedFile) : null,
        [selectedFile],
    );

    useEffect(() => {
        if (!previewUrl) {
            return;
        }

        return () => {
            URL.revokeObjectURL(previewUrl);
        };
    }, [previewUrl]);

    const materials = useMemo(() => brief?.materials ?? [], [brief?.materials]);
    const activeMaterialVersion = useMemo(() => {
        if (!activeMaterialVersionId) {
            return null;
        }
        return materials
            .map((material) => material.current_version)
            .find((version) => version.version_id === activeMaterialVersionId) ?? null;
    }, [activeMaterialVersionId, materials]);

    useEffect(() => {
        let isMounted = true;

        if (!activeMaterialVersion || !isTextPreview(activeMaterialVersion)) {
            return () => {
                isMounted = false;
            };
        }
        const previewVersion = activeMaterialVersion;

        async function loadMaterialPreview() {
            try {
                const response = await fetch(
                    api.salesTrainer.getMaterialVersionFileUrl(
                        previewVersion.version_id,
                        { disposition: "inline" },
                    ),
                    { credentials: "include" },
                );
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const text = await response.text();
                if (isMounted) {
                    setMaterialPreview({
                        versionId: previewVersion.version_id,
                        text,
                        error: null,
                    });
                }
            } catch {
                if (isMounted) {
                    setMaterialPreview({
                        versionId: previewVersion.version_id,
                        text: "",
                        error: "材料预览加载失败，请使用“下载材料”或“新窗口打开”。",
                    });
                }
            }
        }

        void loadMaterialPreview();

        return () => {
            isMounted = false;
        };
    }, [activeMaterialVersion]);
    const activeMaterialPreview = activeMaterialVersion
        && materialPreview?.versionId === activeMaterialVersion.version_id
        ? materialPreview
        : null;

    const pageTitle = brief?.task_brief.title
        || unit?.name
        || "语音作业";
    const pageDescription = brief?.task_brief.purpose
        || unit?.description
        || "上传本次语音作业，系统会完成转写和评分。";
    const passThreshold = brief?.score_scheme?.pass_threshold ?? getAudioPassThreshold(unit);
    const requiredMaterial = materials.find(
        (material) => material.required && material.confirmation_required,
    ) ?? null;
    const rubric = getRubric(brief);
    const commonMistakes = Array.from(
        new Set([
            ...(rubric?.common_mistakes ?? []),
            ...(brief?.task_brief.common_mistakes ?? []),
        ]),
    );
    const canUpload = !isUploading
        && Boolean(selectedFile)
        && passThreshold !== null
        && (!requiredMaterial || confirmedMaterialVersionId === requiredMaterial.current_version.version_id);
    const requiredMaterialConfirmationLabel = requiredMaterial
        ? `我已下载并确认使用 ${requiredMaterial.current_version.version_label} 版本进行本次录音。`
        : null;
    const uploadReadiness = (() => {
        if (!selectedFile) {
            return null;
        }
        if (passThreshold === null) {
            return {
                tone: "warning",
                message: "当前评分标准配置缺失，请联系管理员补齐后再上传。",
            } as const;
        }
        if (requiredMaterial && confirmedMaterialVersionId !== requiredMaterial.current_version.version_id) {
            return {
                tone: "warning",
                message: `下一步：勾选上方“${requiredMaterialConfirmationLabel}”，然后上传评分。`,
            } as const;
        }
        return {
            tone: "success",
            message: requiredMaterial
                ? "录音与材料版本已确认，可以上传并开始评分。"
                : "录音已选择，可以上传并开始评分。",
        } as const;
    })();

    async function handleUpload() {
        if (!selectedFile || !unit) {
            setError("请先选择一个音频文件。");
            return;
        }
        if (requiredMaterial && confirmedMaterialVersionId !== requiredMaterial.current_version.version_id) {
            setError("请先下载并确认当前最新版训练材料。");
            return;
        }
        if (passThreshold === null) {
            setError("当前训练单元缺少语音作业通过线配置，请联系管理员补齐评分标准后重试。");
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
                confirmed_material_version_id: confirmedMaterialVersionId,
            });
            router.push(`/sales-trainer/audio/result/${result.submission_id}`);
        } catch (uploadError) {
            setError(getApiErrorMessage(uploadError));
            setIsUploading(false);
        }
    }

    if (isLoading) {
        return (
            <div className="space-y-6 pb-20">
                <div className="h-40 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
                <div className="h-64 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
            </div>
        );
    }

    if (!unit || unit.unit_type !== "audio_scoring") {
        return (
            <GlassCard className="space-y-4 p-6">
                <p className="text-sm text-red-700">{error || "该训练单元不存在，或不是语音作业单元。"}</p>
                <Button asChild variant="primary">
                    <Link href="/sales-trainer">返回新人训练路径</Link>
                </Button>
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
                    返回新人训练路径
                </Link>
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">{pageTitle}</h1>
                    <p className="mt-1 text-sm text-slate-500">{pageDescription}</p>
                </div>
            </div>

            <GlassCard className="space-y-3 p-6">
                <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100">
                        <FileText className="h-4 w-4 text-blue-700" />
                    </div>
                    <h2 className="text-lg font-bold text-slate-900">任务简报</h2>
                </div>
                {brief?.task_brief.scenario ? (
                    <p className="text-sm leading-6 text-slate-600">{brief.task_brief.scenario}</p>
                ) : null}
                {brief?.task_brief.instructions.length ? (
                    <ul className="space-y-2 text-sm leading-6 text-slate-600">
                        {brief.task_brief.instructions.map((item) => (
                            <li key={item}>{item}</li>
                        ))}
                    </ul>
                ) : null}
                {brief?.task_brief.upload_guidance ? (
                    <p className="text-sm leading-6 text-slate-600">{brief.task_brief.upload_guidance}</p>
                ) : null}
            </GlassCard>

            <GlassCard className="space-y-3 p-6">
                <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100">
                        <Target className="h-4 w-4 text-amber-700" />
                    </div>
                    <h2 className="text-lg font-bold text-slate-900">评分标准</h2>
                </div>
                {passThreshold !== null ? (
                    <p className="text-sm leading-6 text-slate-600">{formatPassThresholdLine(passThreshold)}</p>
                ) : (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                        <p className="font-semibold text-amber-900">{PASS_THRESHOLD_DIAGNOSTIC_TITLE}</p>
                        <p className="mt-1">
                            当前训练单元缺少语音作业通过线配置。页面不会使用默认分数兜底，请联系管理员补齐评分标准后再上传。
                        </p>
                    </div>
                )}
                {rubric?.criteria?.length ? (
                    <div className="grid gap-3 md:grid-cols-2">
                        {rubric.criteria.map((item) => (
                            <div key={item.key} className="rounded-2xl border border-slate-100 bg-white p-4">
                                <div className="flex items-center justify-between gap-2">
                                    <p className="font-semibold text-slate-900">{item.label}</p>
                                    {item.weight != null ? (
                                        <span className="text-xs text-slate-500">{item.weight}%</span>
                                    ) : null}
                                </div>
                                {item.description ? (
                                    <p className="mt-2 text-sm leading-6 text-slate-600">{item.description}</p>
                                ) : null}
                            </div>
                        ))}
                    </div>
                ) : null}
                {commonMistakes.length ? (
                    <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3">
                        <p className="text-sm font-semibold text-amber-900">常见扣分点</p>
                        <ul className="mt-2 space-y-1 text-sm text-amber-800">
                            {commonMistakes.map((item) => (
                                <li key={item}>{item}</li>
                            ))}
                        </ul>
                    </div>
                ) : null}
            </GlassCard>

            {materials.length ? (
                <GlassCard className="space-y-4 p-6">
                    <div className="space-y-1">
                        <div className="flex items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100">
                                <BookOpen className="h-4 w-4 text-violet-700" />
                            </div>
                            <h2 className="text-lg font-bold text-slate-900">训练材料</h2>
                        </div>
                        <p className="text-sm text-slate-500">请使用当前版本完成录音；提交时会冻结你确认的材料版本。</p>
                    </div>
                    <div className="space-y-3">
                        {materials.map((material) => {
                            const version = material.current_version;
                            const fileUrl = api.salesTrainer.getMaterialVersionFileUrl(
                                version.version_id,
                            );
                            const inlineFileUrl = api.salesTrainer.getMaterialVersionFileUrl(
                                version.version_id,
                                { disposition: "inline" },
                            );
                            const isActivePreview = activeMaterialVersionId === version.version_id;
                            return (
                                <div key={`${material.material_id}-${version.version_id}`} className="rounded-2xl border border-slate-100 bg-white p-4">
                                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                                        <div>
                                            <p className="font-semibold text-slate-900">{material.name}</p>
                                            <p className="mt-1 text-sm text-slate-500">
                                                {version.version_label} · {version.title}
                                            </p>
                                            {material.learner_note ? (
                                                <p className="mt-2 text-sm text-slate-600">{material.learner_note}</p>
                                            ) : null}
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                            {canPreviewInline(version) ? (
                                                <Button
                                                    variant="outline"
                                                    onClick={() => setActiveMaterialVersionId(
                                                        isActivePreview ? null : version.version_id,
                                                    )}
                                                >
                                                    <Eye className="mr-2 h-4 w-4" />
                                                    {isActivePreview ? "收起材料" : "查看材料"}
                                                </Button>
                                            ) : (
                                                <a href={inlineFileUrl} target="_blank" rel="noreferrer">
                                                    <Button variant="outline">
                                                        <Eye className="mr-2 h-4 w-4" />
                                                        新窗口打开
                                                    </Button>
                                                </a>
                                            )}
                                            <a href={fileUrl} target="_blank" rel="noreferrer" download>
                                                <Button variant="outline">
                                                    <Download className="mr-2 h-4 w-4" />
                                                    下载材料
                                                </Button>
                                            </a>
                                        </div>
                                    </div>
                                    {isActivePreview ? (
                                        <div className="mt-4 overflow-hidden rounded-2xl border border-slate-100 bg-slate-50">
                                            {isTextPreview(version) ? (
                                                <div className="max-h-[32rem] overflow-y-auto px-5 py-4">
                                                    {!activeMaterialPreview ? (
                                                        <p className="text-sm text-slate-500">正在加载材料预览...</p>
                                                    ) : activeMaterialPreview.error ? (
                                                        <p className="text-sm text-red-700">{activeMaterialPreview.error}</p>
                                                    ) : (
                                                        <ReactMarkdown
                                                            remarkPlugins={[remarkGfm]}
                                                            components={markdownComponents}
                                                        >
                                                            {activeMaterialPreview.text}
                                                        </ReactMarkdown>
                                                    )}
                                                </div>
                                            ) : null}
                                            {isAudioPreview(version) ? (
                                                <div className="p-4">
                                                    <audio controls src={inlineFileUrl} className="w-full">
                                                        您的浏览器不支持音频播放。
                                                    </audio>
                                                </div>
                                            ) : null}
                                            {isVideoPreview(version) ? (
                                                <video controls src={inlineFileUrl} className="max-h-[32rem] w-full bg-black">
                                                    您的浏览器不支持视频播放。
                                                </video>
                                            ) : null}
                                            {isPdfPreview(version) ? (
                                                <iframe
                                                    title={version.title}
                                                    src={inlineFileUrl}
                                                    className="h-[32rem] w-full"
                                                />
                                            ) : null}
                                        </div>
                                    ) : null}
                                    {material.confirmation_required ? (
                                        <label className="mt-4 flex items-start gap-3 text-sm text-slate-700">
                                            <Checkbox
                                                checked={confirmedMaterialVersionId === version.version_id}
                                                onCheckedChange={(checked) =>
                                                    setConfirmedMaterialVersionId(
                                                        checked ? version.version_id : null,
                                                    )
                                                }
                                                disabled={isUploading}
                                                className="mt-0.5"
                                            />
                                            <span>我已下载并确认使用 {version.version_label} 版本进行本次录音。</span>
                                        </label>
                                    ) : null}
                                </div>
                            );
                        })}
                    </div>
                </GlassCard>
            ) : null}

            <GlassCard className="space-y-4 p-6">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100">
                            <UploadCloud className="h-4 w-4 text-emerald-700" />
                        </div>
                        <h2 className="text-lg font-bold text-slate-900">选择音频文件</h2>
                    </div>
                    <p className="text-sm text-slate-500">
                        不做固定时长限制。若格式或大小不符合后端配置，页面会直接展示后端错误。
                    </p>
                </div>

                <label
                    className={cn(
                        "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors",
                        selectedFile
                            ? "border-emerald-300 bg-emerald-50/40"
                            : "border-slate-300 bg-slate-50/50 hover:border-slate-400 hover:bg-slate-50",
                        isUploading && "pointer-events-none opacity-60",
                    )}
                    onDragOver={(event) => {
                        event.preventDefault();
                    }}
                    onDrop={(event) => {
                        event.preventDefault();
                        const file = event.dataTransfer.files?.[0];
                        if (file) {
                            setSelectedFile(file);
                        }
                    }}
                >
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 text-white">
                        <UploadCloud className="h-7 w-7" />
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-slate-900">
                            点击或拖拽音频文件到此处
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                            支持常见音频格式，提交后系统会自动转写并评分
                        </p>
                    </div>
                    <input
                        aria-label="选择音频文件"
                        type="file"
                        accept="audio/*"
                        onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                        className="sr-only"
                        disabled={isUploading}
                    />
                </label>

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

                {uploadReadiness ? (
                    <div
                        id="sales-trainer-audio-upload-readiness"
                        aria-live="polite"
                        className={cn(
                            "rounded-2xl border px-4 py-3 text-sm",
                            uploadReadiness.tone === "success"
                                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                                : "border-amber-200 bg-amber-50 text-amber-800",
                        )}
                    >
                        {uploadReadiness.message}
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
                        variant="primary"
                        onClick={() => void handleUpload()}
                        disabled={!canUpload}
                        isLoading={isUploading}
                        aria-describedby={uploadReadiness ? "sales-trainer-audio-upload-readiness" : undefined}
                        title={!canUpload && uploadReadiness ? uploadReadiness.message : undefined}
                    >
                        <Upload className="mr-2 h-4 w-4" />
                        {isUploading ? "上传中..." : "上传并开始评分"}
                    </Button>
                </div>
            </GlassCard>
        </div>
    );
}
