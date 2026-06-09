"use client";

import { FileText, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import type { SalesTrainerMaterial } from "@/lib/api/types";

import {
    formatFileSize,
    MATERIAL_UPLOAD_ACCEPT,
    type VersionDraft,
} from "./material-page-model";

interface MaterialVersionUploadCardProps {
    readonly isSubmitting: boolean;
    readonly onFileSelected: (file: File) => void;
    readonly onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
    readonly selectedFile: File | null;
    readonly selectedMaterial: SalesTrainerMaterial;
    readonly setVersionDraft: React.Dispatch<React.SetStateAction<VersionDraft>>;
    readonly versionDraft: VersionDraft;
}

export function MaterialVersionUploadCard({
    isSubmitting,
    onFileSelected,
    onSubmit,
    selectedFile,
    selectedMaterial,
    setVersionDraft,
    versionDraft,
}: MaterialVersionUploadCardProps) {
    return (
        <GlassCard className="space-y-5 p-6">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-sky-600">上传新版本</p>
                    <h2 className="mt-1 text-lg font-bold text-slate-900">把文件传到材料库</h2>
                    <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
                        上传后先生成草稿版本；确认无误后再发布为最新版，只影响后续学员。
                    </p>
                </div>
                <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                    当前材料：{selectedMaterial.name}
                </div>
            </div>

            <form className="space-y-5" onSubmit={onSubmit}>
                <label
                    className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-8 text-center transition hover:border-slate-400 hover:bg-white"
                    htmlFor="material-version-file"
                >
                    <Upload className="h-8 w-8 text-slate-500" />
                    <span className="mt-3 text-sm font-bold text-slate-900">上传 PPT 或文档</span>
                    <span className="mt-1 text-xs leading-5 text-slate-500">
                        支持 PPT、PDF、Word、Markdown、图片等材料文件
                    </span>
                    <input
                        id="material-version-file"
                        type="file"
                        accept={MATERIAL_UPLOAD_ACCEPT}
                        aria-label="上传 PPT 或文档"
                        className="sr-only"
                        disabled={isSubmitting}
                        onChange={(event) => {
                            const file = event.target.files?.[0];
                            if (file) {
                                onFileSelected(file);
                            }
                        }}
                    />
                </label>

                {selectedFile ? (
                    <div className="flex flex-col gap-3 rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-950 md:flex-row md:items-center md:justify-between">
                        <div className="flex min-w-0 items-center gap-3">
                            <FileText className="h-5 w-5 shrink-0 text-emerald-700" />
                            <div className="min-w-0">
                                <p className="truncate font-bold">{selectedFile.name}</p>
                                <p className="text-xs text-emerald-700">{formatFileSize(selectedFile.size)}</p>
                            </div>
                        </div>
                        <span className="text-xs font-medium text-emerald-700">待上传为草稿版本</span>
                    </div>
                ) : null}

                <div className="grid gap-4 md:grid-cols-2">
                    <VersionInput
                        id="version-label"
                        label="版本号"
                        value={versionDraft.version_label}
                        disabled={isSubmitting}
                        onChange={(value) => setVersionDraft((current) => ({ ...current, version_label: value }))}
                        placeholder="v2026.06.04-1530"
                    />
                    <VersionInput
                        id="version-title"
                        label="版本标题"
                        value={versionDraft.title}
                        disabled={isSubmitting}
                        onChange={(value) => setVersionDraft((current) => ({ ...current, title: value }))}
                        placeholder={`${selectedMaterial.name} 最新版`}
                    />
                    <div className="space-y-2 md:col-span-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="version-release-notes">版本说明</label>
                        <textarea
                            id="version-release-notes"
                            value={versionDraft.release_notes ?? ""}
                            onChange={(event) => setVersionDraft((current) => ({ ...current, release_notes: event.target.value }))}
                            disabled={isSubmitting}
                            rows={3}
                            className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                            placeholder="例如：更新产品案例，修正文案，替换最新版公司介绍。"
                        />
                    </div>
                </div>

                <Button type="submit" disabled={isSubmitting || !selectedFile} className="rounded-full bg-slate-900 text-white">
                    上传并创建版本
                </Button>
            </form>
        </GlassCard>
    );
}

interface VersionInputProps {
    readonly disabled: boolean;
    readonly id: string;
    readonly label: string;
    readonly onChange: (value: string) => void;
    readonly placeholder?: string;
    readonly value: string;
}

function VersionInput({
    disabled,
    id,
    label,
    onChange,
    placeholder,
    value,
}: VersionInputProps) {
    return (
        <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor={id}>{label}</label>
            <Input
                id={id}
                value={value}
                onChange={(event) => onChange(event.target.value)}
                disabled={disabled}
                placeholder={placeholder}
            />
        </div>
    );
}
