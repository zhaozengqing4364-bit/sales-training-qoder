"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Download, Eye, Upload } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { markdownComponents } from "@/components/sales-trainer/coo-markdown-components";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    SalesTrainerLearnerRubric,
    SalesTrainerPath,
    SalesTrainerUnit,
    SalesTrainerUnitBrief,
    SalesTrainerMaterialVersion,
} from "@/lib/api/types";
import {
    findLevelForUnit,
    formatPassThresholdLine,
    getAudioPassThreshold,
} from "@/lib/sales-trainer/learner-presenter";

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

function getBriefText(brief: Record<string, unknown> | null | undefined, key: string): string {
    const value = brief?.[key];
    return typeof value === "string" ? value : "";
}

function getBriefList(brief: Record<string, unknown> | null | undefined, key: string): string[] {
    const value = brief?.[key];
    return Array.isArray(value)
        ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
        : [];
}

function getRubric(brief: SalesTrainerUnitBrief | null): SalesTrainerLearnerRubric | null {
    const rubric = brief?.score_scheme?.learner_rubric;
    if (!rubric || typeof rubric !== "object" || Array.isArray(rubric)) {
        return null;
    }
    return rubric as SalesTrainerLearnerRubric;
}

function isTextPreview(version: SalesTrainerMaterialVersion): boolean {
    const type = version.content_type.toLowerCase();
    return type.includes("markdown") || type.startsWith("text/");
}

function isAudioPreview(version: SalesTrainerMaterialVersion): boolean {
    return version.content_type.toLowerCase().startsWith("audio/");
}

function isVideoPreview(version: SalesTrainerMaterialVersion): boolean {
    return version.content_type.toLowerCase().startsWith("video/");
}

function isPdfPreview(version: SalesTrainerMaterialVersion): boolean {
    return version.content_type.toLowerCase() === "application/pdf";
}

function canPreviewInline(version: SalesTrainerMaterialVersion): boolean {
    return isTextPreview(version) || isAudioPreview(version) || isVideoPreview(version) || isPdfPreview(version);
}

export default function SalesTrainerAudioUploadPage() {
    const params = useParams<{ unitId: string }>();
    const router = useRouter();
    const [unit, setUnit] = useState<SalesTrainerUnit | null>(null);
    const [brief, setBrief] = useState<SalesTrainerUnitBrief | null>(null);
    const [paths, setPaths] = useState<SalesTrainerPath[]>([]);
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
                const [briefResult, pathResult] = await Promise.all([
                    api.salesTrainer.getUnitBrief(params.unitId),
                    api.salesTrainer.listPaths(),
                ]);
                setBrief(briefResult);
                setUnit(briefResult.unit);
                setPaths(pathResult.items);
            } catch (loadError) {
                setBrief(null);
                setUnit(null);
                setPaths([]);
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
    const levelContext = useMemo(
        () => findLevelForUnit(paths, params.unitId),
        [paths, params.unitId],
    );
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

    const pageTitle = getBriefText(brief?.task_brief, "title")
        || levelContext?.level.level_title
        || unit?.name
        || "语音作业";
    const pageDescription = getBriefText(brief?.task_brief, "purpose")
        || levelContext?.level.level_description
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
            ...getBriefList(brief?.task_brief, "common_mistakes"),
        ]),
    );
    const canUpload = !isUploading
        && Boolean(selectedFile)
        && (!requiredMaterial || confirmedMaterialVersionId === requiredMaterial.current_version.version_id);

    async function handleUpload() {
        if (!selectedFile || !unit) {
            setError("请先选择一个音频文件。");
            return;
        }
        if (requiredMaterial && confirmedMaterialVersionId !== requiredMaterial.current_version.version_id) {
            setError("请先下载并确认当前最新版训练材料。");
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
        return <div className="py-12 text-center text-sm text-slate-500">正在加载语音作业...</div>;
    }

    if (!unit || unit.unit_type !== "audio_scoring") {
        return (
            <GlassCard className="space-y-4 p-6">
                <p className="text-sm text-red-700">{error || "该训练单元不存在，或不是语音作业单元。"}</p>
                <Button asChild className="rounded-full">
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
                <h2 className="text-lg font-bold text-slate-900">任务简报</h2>
                {getBriefText(brief?.task_brief, "scenario") ? (
                    <p className="text-sm leading-6 text-slate-600">{getBriefText(brief?.task_brief, "scenario")}</p>
                ) : null}
                {getBriefList(brief?.task_brief, "instructions").length ? (
                    <ul className="space-y-2 text-sm leading-6 text-slate-600">
                        {getBriefList(brief?.task_brief, "instructions").map((item) => (
                            <li key={item}>{item}</li>
                        ))}
                    </ul>
                ) : null}
                {getBriefText(brief?.task_brief, "upload_guidance") ? (
                    <p className="text-sm leading-6 text-slate-600">{getBriefText(brief?.task_brief, "upload_guidance")}</p>
                ) : null}
            </GlassCard>

            <GlassCard className="space-y-3 p-6">
                <h2 className="text-lg font-bold text-slate-900">评分标准</h2>
                <p className="text-sm leading-6 text-slate-600">{formatPassThresholdLine(passThreshold)}</p>
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
                    <div>
                        <h2 className="text-lg font-bold text-slate-900">训练材料</h2>
                        <p className="mt-1 text-sm text-slate-500">请使用当前版本完成录音；提交时会冻结你确认的材料版本。</p>
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
                                                    className="rounded-full"
                                                    onClick={() => setActiveMaterialVersionId(
                                                        isActivePreview ? null : version.version_id,
                                                    )}
                                                >
                                                    <Eye className="mr-2 h-4 w-4" />
                                                    {isActivePreview ? "收起材料" : "查看材料"}
                                                </Button>
                                            ) : (
                                                <a href={inlineFileUrl} target="_blank" rel="noreferrer">
                                                    <Button variant="outline" className="rounded-full">
                                                        <Eye className="mr-2 h-4 w-4" />
                                                        新窗口打开
                                                    </Button>
                                                </a>
                                            )}
                                            <a href={fileUrl} target="_blank" rel="noreferrer" download>
                                                <Button variant="outline" className="rounded-full">
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
                                        <label className="mt-4 flex items-start gap-2 text-sm text-slate-700">
                                            <input
                                                type="checkbox"
                                                checked={confirmedMaterialVersionId === version.version_id}
                                                onChange={(event) => setConfirmedMaterialVersionId(event.target.checked ? version.version_id : null)}
                                                disabled={isUploading}
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
                        disabled={!canUpload}
                    >
                        <Upload className="mr-2 h-4 w-4" />
                        {isUploading ? "上传中..." : "上传并开始评分"}
                    </Button>
                </div>
            </GlassCard>
        </div>
    );
}
