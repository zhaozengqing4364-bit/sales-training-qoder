"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { Route } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { PathConfigCenter } from "@/components/admin/sales-trainer/path-config-center";
import { PathConfigAudioBindingEditor } from "@/components/admin/sales-trainer/path-config-audio-binding-editor";
import { PathConfigBusinessBindingEditor } from "@/components/admin/sales-trainer/path-config-business-binding-editor";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { buildNewcomerConfigCenter } from "@/lib/sales-trainer/config-center";
import type { NewcomerConfigModuleSummary } from "@/lib/sales-trainer/config-center";
import {
    audioBindingValueForModule,
    businessBindingValueForModule,
    isAudioEditableModuleKey,
    type PathBusinessBindingValue,
    type PathAudioBindingValue,
    updatePathBusinessBinding,
    updatePathAudioBinding,
} from "@/lib/sales-trainer/path-config-editing";
import {
    loadConfigCenterData,
    type ConfigCenterData,
} from "./page-data";

export default function SalesTrainerPathsPage() {
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const focusedModuleKey = searchParams.get("module");
    const [data, setData] = useState<ConfigCenterData | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isMutating, setIsMutating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [actionMessage, setActionMessage] = useState<string | null>(null);

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            setData(await loadConfigCenterData());
        } catch (loadError) {
            setData(null);
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    const updateAudioBinding = useCallback((
        moduleKey: "ppt_explanation" | "elevator_pitch",
        value: PathAudioBindingValue,
    ) => {
        setData((current) => {
            if (!current?.pathConfig) {
                return current;
            }
            return {
                ...current,
                pathConfig: {
                    ...current.pathConfig,
                    path: updatePathAudioBinding(current.pathConfig.path, moduleKey, value),
                },
            };
        });
    }, []);

    const updateBusinessBinding = useCallback((value: PathBusinessBindingValue) => {
        setData((current) => {
            if (!current?.pathConfig) {
                return current;
            }
            return {
                ...current,
                pathConfig: {
                    ...current.pathConfig,
                    path: updatePathBusinessBinding(current.pathConfig.path, value),
                },
            };
        });
    }, []);

    const saveCurrentRevision = useCallback(async () => {
        if (!data?.pathConfig) {
            setError("路径配置尚未加载完成。");
            return;
        }
        setIsMutating(true);
        setError(null);
        setActionMessage(null);
        try {
            await api.admin.newcomerTraining.savePathConfig({
                ...data.pathConfig.path,
                reason: "管理员从配置中心保存路径配置修订",
            });
            setActionMessage("已保存为待发布修订，发布后只影响后续学员。");
            await load();
        } catch (saveError) {
            setError(getApiErrorMessage(saveError));
        } finally {
            setIsMutating(false);
        }
    }, [data?.pathConfig, load]);

    const publishWorkingRevision = useCallback(async () => {
        setIsMutating(true);
        setError(null);
        setActionMessage(null);
        try {
            await api.admin.newcomerTraining.publishPathConfig({
                reason: "管理员从配置中心发布路径配置修订",
            });
            setActionMessage("路径配置已发布生效；历史学员记录不会被改写。");
            await load();
        } catch (publishError) {
            setError(getApiErrorMessage(publishError));
        } finally {
            setIsMutating(false);
        }
    }, [load]);

    const rollbackRevision = useCallback(async (revisionId: string, reason: string) => {
        setIsMutating(true);
        setError(null);
        setActionMessage(null);
        try {
            await api.admin.newcomerTraining.rollbackPathConfig({
                revision_id: revisionId,
                reason,
            });
            setActionMessage("路径配置已回滚；回滚只影响后续学员。");
            await load();
        } catch (rollbackError) {
            setError(getApiErrorMessage(rollbackError));
        } finally {
            setIsMutating(false);
        }
    }, [load]);

    const model = useMemo(
        () => data ? buildNewcomerConfigCenter(data) : null,
        [data],
    );

    const renderModuleEditor = useCallback((module: NewcomerConfigModuleSummary) => {
        if (!data?.pathConfig) {
            return null;
        }
        if (module.moduleKey === "business_skills") {
            return (
                <PathConfigBusinessBindingEditor
                    articles={data.articles}
                    disabled={isMutating}
                    moduleTitle={module.title}
                    papers={data.papers}
                    value={businessBindingValueForModule(data.pathConfig.path)}
                    onChange={updateBusinessBinding}
                />
            );
        }
        if (!isAudioEditableModuleKey(module.moduleKey)) {
            return null;
        }
        const moduleKey = module.moduleKey;
        return (
            <PathConfigAudioBindingEditor
                availableMaterials={data.materials}
                availablePrompts={data.scorePrompts}
                disabled={isMutating}
                moduleKey={moduleKey}
                moduleTitle={module.title}
                value={audioBindingValueForModule(data.pathConfig.path, moduleKey)}
                onChange={(value) => updateAudioBinding(moduleKey, value)}
            />
        );
    }, [
        data?.articles,
        data?.materials,
        data?.papers,
        data?.pathConfig,
        data?.scorePrompts,
        isMutating,
        updateAudioBinding,
        updateBusinessBinding,
    ]);

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="新人训练路径配置中心"
                    description="统一查看四个关卡的启用、绑定、缺失配置、学员端预览和运维诊断；管理员不需要再到模块单元编辑页理解抽象路径字段。"
                    icon={<Route className="h-7 w-7 text-slate-800" />}
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
                />
            )}
        >
            {error ? (
                <GlassCard className="border-red-100 bg-red-50 p-4 text-sm font-medium text-red-700">
                    新人训练路径配置加载失败：{error}
                </GlassCard>
            ) : null}
            {actionMessage ? (
                <GlassCard className="border-emerald-100 bg-emerald-50 p-4 text-sm font-medium text-emerald-700">
                    {actionMessage}
                </GlassCard>
            ) : null}

            {isLoading && !model ? (
                <GlassCard className="p-8 text-center text-sm text-slate-500">
                    正在加载新人训练路径配置...
                </GlassCard>
            ) : null}

            {model ? (
                <PathConfigCenter
                    model={model}
                    focusedModuleKey={focusedModuleKey}
                    isRefreshing={isLoading}
                    isMutating={isMutating}
                    onRefresh={() => void load()}
                    onSaveCurrentRevision={() => void saveCurrentRevision()}
                    onPublishWorkingRevision={() => void publishWorkingRevision()}
                    onRollbackRevision={(revisionId, reason) => void rollbackRevision(revisionId, reason)}
                    renderModuleEditor={renderModuleEditor}
                />
            ) : null}
        </AdminIndexShell>
    );
}
