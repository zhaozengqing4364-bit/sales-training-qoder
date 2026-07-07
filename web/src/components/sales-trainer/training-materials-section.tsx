"use client";

import { useEffect, useState } from "react";
import { BookOpen, Download, Eye } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { markdownComponents } from "@/components/sales-trainer/coo-markdown-components";
import { api } from "@/lib/api/client";
import type { SalesTrainerUnitBriefMaterial, SalesTrainerLearnerMaterialVersion } from "@/lib/api/types";

type MaterialPreviewState = {
    versionId: string;
    text: string;
    error: string | null;
};

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

interface TrainingMaterialsSectionProps {
    materials: SalesTrainerUnitBriefMaterial[];
    /** 区块标题，默认"训练材料"。 */
    title?: string;
    /** 空态文案，默认"本关暂无训练材料"。 */
    emptyHint?: string;
}

/**
 * 训练材料下载/预览区块。
 * 复用 audio/[unitId] 上传页同款下载/预览逻辑（getMaterialVersionFileUrl，
 * 文本类 inline 预览，audio/video/pdf inline 预览）。
 */
export function TrainingMaterialsSection({
    materials,
    title = "训练材料",
    emptyHint = "本关暂无训练材料",
}: TrainingMaterialsSectionProps) {
    const [activeMaterialVersionId, setActiveMaterialVersionId] = useState<string | null>(null);
    const [materialPreview, setMaterialPreview] = useState<MaterialPreviewState | null>(null);

    const activeMaterialVersion = activeMaterialVersionId
        ? materials
            .map((material) => material.current_version)
            .find((version) => version.version_id === activeMaterialVersionId) ?? null
        : null;

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

    if (materials.length === 0) {
        return (
            <GlassCard className="space-y-3 p-6">
                <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100">
                        <BookOpen className="h-4 w-4 text-violet-700" />
                    </div>
                    <h2 className="text-lg font-bold text-slate-900">{title}</h2>
                </div>
                <p className="text-sm text-slate-500">{emptyHint}</p>
            </GlassCard>
        );
    }

    return (
        <GlassCard className="space-y-4 p-6" data-testid="training-materials-section">
            <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100">
                    <BookOpen className="h-4 w-4 text-violet-700" />
                </div>
                <h2 className="text-lg font-bold text-slate-900">{title}</h2>
            </div>
            <div className="space-y-3">
                {materials.map((material) => {
                    const version = material.current_version;
                    if (!version) {
                        return null;
                    }
                    const fileUrl = api.salesTrainer.getMaterialVersionFileUrl(version.version_id);
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
                        </div>
                    );
                })}
            </div>
        </GlassCard>
    );
}
