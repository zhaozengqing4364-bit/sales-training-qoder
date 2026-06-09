"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import type { SalesTrainerMaterial } from "@/lib/api/types";
import {
    formatAdminStatus,
    formatTrainingPurpose,
} from "@/lib/sales-trainer/admin-display";

import {
    formatFileSize,
    MATERIAL_TYPE_LABELS,
    type VersionDraft,
} from "./material-page-model";
import { MaterialVersionUploadCard } from "./material-version-upload-card";

interface MaterialDetailPanelProps {
    readonly isSubmitting: boolean;
    readonly onFileSelected: (file: File) => void;
    readonly onPublishVersion: (versionId: string) => void;
    readonly onUploadVersion: (event: React.FormEvent<HTMLFormElement>) => void;
    readonly selectedFile: File | null;
    readonly selectedMaterial: SalesTrainerMaterial | null;
    readonly setVersionDraft: React.Dispatch<React.SetStateAction<VersionDraft>>;
    readonly versionDraft: VersionDraft;
}

export function MaterialDetailPanel({
    isSubmitting,
    onFileSelected,
    onPublishVersion,
    onUploadVersion,
    selectedFile,
    selectedMaterial,
    setVersionDraft,
    versionDraft,
}: MaterialDetailPanelProps) {
    if (!selectedMaterial) {
        return (
            <GlassCard className="p-6 text-sm text-slate-500">请选择或创建一个训练材料。</GlassCard>
        );
    }

    return (
        <>
            <MaterialOverviewCard selectedMaterial={selectedMaterial} />
            <MaterialVersionUploadCard
                isSubmitting={isSubmitting}
                onFileSelected={onFileSelected}
                onSubmit={onUploadVersion}
                selectedFile={selectedFile}
                selectedMaterial={selectedMaterial}
                setVersionDraft={setVersionDraft}
                versionDraft={versionDraft}
            />
            <MaterialVersionList
                isSubmitting={isSubmitting}
                onPublishVersion={onPublishVersion}
                selectedMaterial={selectedMaterial}
            />
        </>
    );
}

function MaterialOverviewCard({ selectedMaterial }: { readonly selectedMaterial: SalesTrainerMaterial }) {
    return (
        <GlassCard className="space-y-4 p-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                    <h2 className="text-xl font-black text-slate-900">{selectedMaterial.name}</h2>
                    <p className="mt-1 text-sm text-slate-500">{selectedMaterial.description || "未填写材料说明"}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Badge className="bg-slate-100 text-slate-700">
                        {MATERIAL_TYPE_LABELS[selectedMaterial.material_type]}
                    </Badge>
                    <Badge className="bg-slate-100 text-slate-700">
                        {formatTrainingPurpose(selectedMaterial.purpose)}
                    </Badge>
                </div>
            </div>
            {selectedMaterial.current_version ? (
                <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                    当前生效版本：{selectedMaterial.current_version.version_label} · {selectedMaterial.current_version.title}
                </div>
            ) : (
                <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    该材料还没有发布版本，不能绑定到学员 PPT 演练任务。
                </div>
            )}
        </GlassCard>
    );
}

interface MaterialVersionListProps {
    readonly isSubmitting: boolean;
    readonly onPublishVersion: (versionId: string) => void;
    readonly selectedMaterial: SalesTrainerMaterial;
}

function MaterialVersionList({
    isSubmitting,
    onPublishVersion,
    selectedMaterial,
}: MaterialVersionListProps) {
    return (
        <GlassCard className="overflow-hidden p-0">
            <div className="border-b border-slate-100 px-6 py-4">
                <h2 className="text-lg font-bold text-slate-900">版本列表</h2>
            </div>
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b border-slate-100 text-left text-slate-500">
                        <th className="px-6 py-4">版本</th>
                        <th className="px-6 py-4">文件</th>
                        <th className="px-6 py-4">状态</th>
                        <th className="px-6 py-4">操作</th>
                    </tr>
                </thead>
                <tbody>
                    {selectedMaterial.versions.length === 0 ? (
                        <tr><td colSpan={4} className="px-6 py-10 text-center text-slate-500">暂无版本</td></tr>
                    ) : selectedMaterial.versions.map((version) => (
                        <tr key={version.version_id} className="border-b border-slate-100 last:border-b-0">
                            <td className="px-6 py-4">
                                <p className="font-medium text-slate-900">{version.version_label}</p>
                                <p className="mt-1 text-xs text-slate-500">{version.title}</p>
                            </td>
                            <td className="px-6 py-4">
                                <p>{version.file_name}</p>
                                <p className="mt-1 text-xs text-slate-500">{formatFileSize(version.file_size_bytes)}</p>
                            </td>
                            <td className="px-6 py-4">
                                <Badge className="bg-slate-100 text-slate-700">{formatAdminStatus(version.status)}</Badge>
                            </td>
                            <td className="px-6 py-4">
                                {version.status !== "published" ? (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        disabled={isSubmitting}
                                        onClick={() => onPublishVersion(version.version_id)}
                                    >
                                        发布为最新版
                                    </Button>
                                ) : (
                                    <span className="text-xs text-slate-500">当前发布</span>
                                )}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </GlassCard>
    );
}
