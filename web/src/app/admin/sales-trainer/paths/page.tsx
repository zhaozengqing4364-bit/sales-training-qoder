"use client";

import { useCallback } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { Route } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { PathConfigCenter } from "@/components/admin/sales-trainer/path-config-center";
import { PathConfigAudioBindingEditor } from "@/components/admin/sales-trainer/path-config-audio-binding-editor";
import { PathConfigBusinessBindingEditor } from "@/components/admin/sales-trainer/path-config-business-binding-editor";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { GlassCard } from "@/components/ui/glass-card";
import type { NewcomerConfigModuleSummary } from "@/lib/sales-trainer/config-center";
import {
    audioBindingValueForModule,
    businessBindingValueForModule,
    isAudioEditableModuleKey,
} from "@/lib/sales-trainer/path-config-editing";
import { usePathConfigCenterWorkflow } from "./use-path-config-center-workflow";

export default function SalesTrainerPathsPage() {
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const focusedModuleKey = searchParams.get("module");
    const {
        actionMessage,
        changeReason,
        data,
        error,
        isLoading,
        isMutating,
        load,
        model,
        publishWorkingRevision,
        rollbackRevision,
        saveCurrentRevision,
        setChangeReason,
        updateAudioBinding,
        updateBusinessBinding,
    } = usePathConfigCenterWorkflow();

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
    }, [data, isMutating, updateAudioBinding, updateBusinessBinding]);

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
                    changeReason={changeReason}
                    onChangeReason={setChangeReason}
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
