"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
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
import { audioEvaluationScenarioForSlug } from "@/lib/sales-trainer/audio-evaluation-scenarios";
import { useSalesTrainerAdminRouteAccess } from "@/lib/sales-trainer/use-admin-route-access";

export default function SalesTrainerMaterialsPage() {
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const toast = useToast();
    const toastError = toast.error;
    const toastSuccess = toast.success;
    const scenario = audioEvaluationScenarioForSlug(searchParams.get("scenario"));
    const moduleKey = scenario?.moduleKey ?? searchParams.get("module");
    const purposeFromQuery = scenario?.purposeKey ?? searchParams.get("purpose");
    const [items, setItems] = useState<SalesTrainerMaterial[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [selectedMaterialId, setSelectedMaterialId] = useState<string | null>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [materialDraft, setMaterialDraft] = useState<SalesTrainerMaterialCreateRequest>(
        createEmptyMaterialDraft(purposeFromQuery),
    );
    const [versionDraft, setVersionDraft] = useState<VersionDraft>(createEmptyVersionDraft());
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);

    const selectedMaterial = useMemo(
        () => firstSelectedMaterial(items, selectedMaterialId),
        [items, selectedMaterialId],
    );

    const loadMaterials = useCallback(async () => {
        setIsLoading(true);
        setLoadError(null);
        try {
            const result = await api.admin.salesTrainer.listMaterials({
                include_archived: true,
                limit: 100,
            });
            setItems(result.items);
            setSelectedMaterialId((current) => current ?? result.items[0]?.material_id ?? null);
        } catch (loadError) {
            const message = getApiErrorMessage(loadError);
            setItems([]);
            setSelectedMaterialId(null);
            setLoadError(message);
            toastError(message);
        } finally {
            setIsLoading(false);
        }
    }, [toastError]);

    useEffect(() => {
        if (routeAccess.isLoading) {
            return;
        }
        if (!routeAccess.canAccess) {
            setItems([]);
            setSelectedMaterialId(null);
            setIsLoading(false);
            setLoadError(null);
            return;
        }
        void loadMaterials();
    }, [loadMaterials, routeAccess.canAccess, routeAccess.isLoading]);

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
            toastError("材料标识和名称不能为空。");
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
            toastSuccess("训练材料已创建");
            setMaterialDraft(createEmptyMaterialDraft(purposeFromQuery));
            setSelectedMaterialId(created.material_id);
            await loadMaterials();
        } catch (createError) {
            toastError(getApiErrorMessage(createError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function uploadVersion(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!selectedMaterial) {
            toastError("请先创建或选择训练材料。");
            return;
        }
        if (!selectedFile) {
            toastError("请先上传 PPT 或文档文件。");
            return;
        }
        if (!versionDraft.version_label.trim() || !versionDraft.title.trim()) {
            toastError("版本号和版本标题不能为空。");
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
            toastSuccess("材料文件已上传，版本已创建为草稿");
            setSelectedFile(null);
            setVersionDraft(createEmptyVersionDraft());
            await loadMaterials();
        } catch (createError) {
            toastError(getApiErrorMessage(createError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function publishVersion(versionId: string) {
        setIsSubmitting(true);
        try {
            await api.admin.salesTrainer.publishMaterialVersion(versionId);
            toastSuccess("材料版本已发布为最新版");
            await loadMaterials();
        } catch (publishError) {
            toastError(getApiErrorMessage(publishError));
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
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={routeAccess.capabilities} />}
                />
            )}
        >
            {routeAccess.denialMessage ? (
                <AdminLoadErrorCard
                    title="页面访问受限"
                    description="当前页不会在能力接口失败或权限不足时继续加载材料库，避免把不可访问状态伪装成空数据。"
                    message={routeAccess.denialMessage}
                    retryLabel="重新检查权限"
                    onRetry={routeAccess.reloadCapabilities}
                />
            ) : (
                <MaterialSetupGuide moduleKey={moduleKey} />
            )}
            {!routeAccess.denialMessage && loadError ? (
                <AdminLoadErrorCard
                    title="材料库加载失败"
                    description="当前页不会把接口异常伪装成空材料库。请核对权限、筛选条件或后端服务状态后重试。"
                    message={loadError}
                    retryLabel="重新加载材料"
                    onRetry={() => void loadMaterials()}
                />
            ) : !routeAccess.denialMessage ? (
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
            ) : null}
        </AdminIndexShell>
    );
}
