"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { MaterialCreateCard } from "@/components/admin/sales-trainer/material-create-card";
import { MaterialDetailPanel } from "@/components/admin/sales-trainer/material-detail-panel";
import { MaterialListCard } from "@/components/admin/sales-trainer/material-list-card";
import {
    applyFileToVersionDraft,
    createEmptyMaterialDraft,
    createEmptyVersionDraft,
    firstSelectedMaterial,
    type VersionDraft,
} from "@/components/admin/sales-trainer/material-page-model";
import { MaterialSetupGuide } from "@/components/admin/sales-trainer/material-setup-guide";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    SalesTrainerMaterial,
    SalesTrainerMaterialCreateRequest,
} from "@/lib/api/types";

export default function SalesTrainerMaterialsPage() {
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const toast = useToast();
    const moduleKey = searchParams.get("module");
    const purposeFromQuery = searchParams.get("purpose");
    const [items, setItems] = useState<SalesTrainerMaterial[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [selectedMaterialId, setSelectedMaterialId] = useState<string | null>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [materialDraft, setMaterialDraft] = useState<SalesTrainerMaterialCreateRequest>(
        createEmptyMaterialDraft(purposeFromQuery),
    );
    const [versionDraft, setVersionDraft] = useState<VersionDraft>(createEmptyVersionDraft());

    const selectedMaterial = useMemo(
        () => firstSelectedMaterial(items, selectedMaterialId),
        [items, selectedMaterialId],
    );

    async function loadMaterials() {
        setIsLoading(true);
        try {
            const result = await api.admin.salesTrainer.listMaterials({
                include_archived: true,
                limit: 100,
            });
            setItems(result.items);
            setSelectedMaterialId((current) => current ?? result.items[0]?.material_id ?? null);
        } catch (loadError) {
            setItems([]);
            toast.error(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }

    useEffect(() => {
        void loadMaterials();
    }, []);

    useEffect(() => {
        if (!purposeFromQuery) {
            return;
        }
        setMaterialDraft((current) => ({ ...current, purpose: purposeFromQuery }));
    }, [purposeFromQuery]);

    useEffect(() => {
        setSelectedFile(null);
        setVersionDraft(createEmptyVersionDraft());
    }, [selectedMaterial?.material_id]);

    function handleFileSelected(file: File) {
        setSelectedFile(file);
        setVersionDraft((current) => (
            applyFileToVersionDraft(current, file, selectedMaterial?.name ?? "训练材料")
        ));
    }

    async function createMaterial(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!materialDraft.material_key.trim() || !materialDraft.name.trim()) {
            toast.error("材料标识和名称不能为空。");
            return;
        }
        setIsSubmitting(true);
        try {
            const created = await api.admin.salesTrainer.createMaterial({
                ...materialDraft,
                material_key: materialDraft.material_key.trim(),
                name: materialDraft.name.trim(),
                description: materialDraft.description?.trim() || null,
                purpose: materialDraft.purpose?.trim() || "ppt_pitch",
            });
            toast.success("训练材料已创建");
            setMaterialDraft(createEmptyMaterialDraft(purposeFromQuery));
            setSelectedMaterialId(created.material_id);
            await loadMaterials();
        } catch (createError) {
            toast.error(getApiErrorMessage(createError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function uploadVersion(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!selectedMaterial) {
            toast.error("请先创建或选择训练材料。");
            return;
        }
        if (!selectedFile) {
            toast.error("请先上传 PPT 或文档文件。");
            return;
        }
        if (!versionDraft.version_label.trim() || !versionDraft.title.trim()) {
            toast.error("版本号和版本标题不能为空。");
            return;
        }
        setIsSubmitting(true);
        try {
            await api.admin.salesTrainer.uploadMaterialVersion(selectedMaterial.material_id, {
                file: selectedFile,
                version_label: versionDraft.version_label.trim(),
                title: versionDraft.title.trim(),
                release_notes: versionDraft.release_notes?.trim() || null,
            });
            toast.success("材料文件已上传，版本已创建为草稿");
            setSelectedFile(null);
            setVersionDraft(createEmptyVersionDraft());
            await loadMaterials();
        } catch (createError) {
            toast.error(getApiErrorMessage(createError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function publishVersion(versionId: string) {
        setIsSubmitting(true);
        try {
            await api.admin.salesTrainer.publishMaterialVersion(versionId);
            toast.success("材料版本已发布为最新版");
            await loadMaterials();
        } catch (publishError) {
            toast.error(getApiErrorMessage(publishError));
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="新人训练路径材料库"
                    description="单独管理新人训练路径 PPT、逐字稿和附件版本；训练任务只绑定这里的已发布材料。"
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
                />
            )}
        >
            <MaterialSetupGuide moduleKey={moduleKey} />
            <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
                <div className="space-y-6">
                    <MaterialCreateCard
                        isSubmitting={isSubmitting}
                        materialDraft={materialDraft}
                        onSubmit={createMaterial}
                        setMaterialDraft={setMaterialDraft}
                    />
                    <MaterialListCard
                        isLoading={isLoading}
                        items={items}
                        onSelect={setSelectedMaterialId}
                    />
                </div>

                <div className="space-y-6">
                    <MaterialDetailPanel
                        isSubmitting={isSubmitting}
                        onFileSelected={handleFileSelected}
                        onPublishVersion={(versionId) => void publishVersion(versionId)}
                        onUploadVersion={uploadVersion}
                        selectedFile={selectedFile}
                        selectedMaterial={selectedMaterial}
                        setVersionDraft={setVersionDraft}
                        versionDraft={versionDraft}
                    />
                </div>
            </div>
        </AdminIndexShell>
    );
}
