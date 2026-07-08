"use client";

import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { Mic } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { GlassCard } from "@/components/ui/glass-card";
import {
    audioEvaluationScenarioForPurpose,
    audioEvaluationScenarioForSlug,
    type AudioEvaluationScenarioDefinition,
    type AudioEvaluationModuleKey,
} from "@/lib/sales-trainer/audio-evaluation-scenarios";
import type { SalesTrainerUnit } from "@/lib/api/types";
import {
    audioScenarioValueForModule,
    type PathAudioScenarioValue,
} from "@/lib/sales-trainer/path-config-editing";
import { useSalesTrainerAdminRouteAccess } from "@/lib/sales-trainer/use-admin-route-access";
import { usePathConfigCenterWorkflow } from "../../paths/use-path-config-center-workflow";

function paramValue(value: string | string[] | undefined): string {
    return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function unitMatchesScenario(
    unit: SalesTrainerUnit,
    scenario: AudioEvaluationScenarioDefinition,
): boolean {
    const audio = unit.config.audio;
    const path = unit.config.path;
    const scenarioKey = audio?.scenario_key ?? path?.scenario_key;
    if (scenarioKey) {
        return scenarioKey === scenario.scenarioKey;
    }
    const moduleKey = path?.module_key;
    if (moduleKey) {
        return moduleKey === scenario.moduleKey;
    }
    return audioEvaluationScenarioForPurpose(audio?.purpose)?.scenarioKey === scenario.scenarioKey;
}

export default function SalesTrainerTrainingTaskDetailPage() {
    const params = useParams<{ scenarioSlug: string }>();
    const pathname = usePathname();
    const router = useRouter();
    const scenario = audioEvaluationScenarioForSlug(paramValue(params.scenarioSlug));
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);
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
        saveCurrentRevision,
        setChangeReason,
        updateAudioScenario,
    } = usePathConfigCenterWorkflow({ enabled: routeAccess.canAccess && Boolean(scenario) });

    if (!scenario) {
        return (
            <AdminIndexShell
                header={<AdminPageHeader title="训练任务不存在" description="未找到对应的训练任务场景。" />}
            >
                <AdminLoadErrorCard
                    title="训练任务不存在"
                    description="请从训练任务列表进入已配置的治理入口。"
                    message="未知训练任务场景。"
                    retryLabel="返回训练任务"
                    onRetry={() => router.push("/admin/sales-trainer/training-tasks")}
                />
            </AdminIndexShell>
        );
    }

    const moduleKey: AudioEvaluationModuleKey = scenario.moduleKey;
    const canManageTask = routeAccess.canAccess && !routeAccess.isLoading;
    const path = data?.pathConfig?.path ?? null;
    const value = canManageTask && path ? audioScenarioValueForModule(path, moduleKey) : null;
    const moduleSummary = model?.modules.find((module) => module.moduleKey === moduleKey) ?? null;
    const audioUnits = data?.units.filter((unit) => (
        canManageTask
            && unit.status === "published"
            && unit.unit_type === "audio_scoring"
            && unitMatchesScenario(unit, scenario)
    )) ?? [];
    const materials = data?.materials.filter((material) => (
        material.status === "published" && Boolean(material.current_version_id)
    )) ?? [];
    const prompts = data?.scorePrompts.filter((prompt) => prompt.status === "published") ?? [];

    function updateValue(next: PathAudioScenarioValue) {
        if (!canManageTask) {
            return;
        }
        updateAudioScenario(moduleKey, next);
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title={scenario.title}
                    description="在当前任务里完成单元、材料、录音评测标准和发布状态治理；底层继续复用路径 working revision、发布和回滚机制。"
                    icon={<Mic className="h-7 w-7 text-slate-800" />}
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={routeAccess.capabilities} />}
                />
            )}
        >
            {routeAccess.denialMessage ? (
                <AdminLoadErrorCard
                    title="训练任务不可访问"
                    description="当前账号没有配置新人训练任务的权限。"
                    message={routeAccess.denialMessage}
                    retryLabel="重新检查权限"
                    onRetry={routeAccess.reloadCapabilities}
                />
            ) : null}
            {canManageTask && isLoading && !value ? (
                <GlassCard className="p-8 text-center text-sm text-slate-500">
                    正在加载训练任务配置...
                </GlassCard>
            ) : null}
            {canManageTask && error ? (
                <GlassCard className="border-red-100 bg-red-50 p-4 text-sm font-medium text-red-700">
                    训练任务配置加载失败：{error}
                </GlassCard>
            ) : null}
            {canManageTask && actionMessage ? (
                <GlassCard className="border-emerald-100 bg-emerald-50 p-4 text-sm font-medium text-emerald-700">
                    {actionMessage}
                </GlassCard>
            ) : null}

            {value ? (
                <>
                    <GlassCard className="space-y-4 p-5">
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div>
                                <p className="text-sm font-semibold text-slate-500">场景策略</p>
                                <h2 className="mt-1 text-lg font-black text-slate-950">{scenario.title}</h2>
                                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                                    {scenario.description}
                                </p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                                    {scenario.materialRequired ? "材料必须确认" : "材料选配"}
                                </span>
                                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                                    发布只影响后续学员
                                </span>
                            </div>
                        </div>
                        {moduleSummary?.issues.length ? (
                            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                                <p className="text-sm font-bold text-amber-950">当前缺失配置</p>
                                <ul className="mt-2 space-y-1 text-sm text-amber-800">
                                    {moduleSummary.issues.map((issue) => (
                                        <li key={issue.code}>{issue.message}</li>
                                    ))}
                                </ul>
                            </div>
                        ) : (
                            <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-4 text-sm font-medium text-emerald-700">
                                当前任务没有阻断发布的配置缺口。
                            </div>
                        )}
                    </GlassCard>

                    <GlassCard className="space-y-5 p-5">
                        <div>
                            <h2 className="text-base font-bold text-slate-900">任务绑定</h2>
                            <p className="text-sm text-slate-500">
                                选择已发布训练单元、材料和录音评测标准。缺资源时可以先快速进入对应管理页创建，再回到本页自动绑定。
                            </p>
                        </div>
                        <div className="grid gap-4 lg:grid-cols-3">
                            <label className="space-y-2 text-sm font-medium text-slate-700">
                                训练单元
                                <select
                                    value={value.targetUnitId}
                                    onChange={(event) => updateValue({ ...value, targetUnitId: event.target.value })}
                                    disabled={isMutating || !canManageTask}
                                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                >
                                    <option value="">请选择已发布录音单元</option>
                                    {audioUnits.map((unit) => (
                                        <option key={unit.unit_id} value={unit.unit_id}>{unit.name}</option>
                                    ))}
                                </select>
                            </label>
                            <label className="space-y-2 text-sm font-medium text-slate-700">
                                {scenario.materialRequired ? "任务材料" : "选配材料"}
                                <select
                                    value={value.materialId}
                                    onChange={(event) => {
                                        const material = materials.find((item) => item.material_id === event.target.value);
                                        updateValue({
                                            ...value,
                                            materialId: event.target.value,
                                            materialVersionId: material?.current_version_id ?? "",
                                        });
                                    }}
                                    disabled={isMutating || !canManageTask}
                                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                >
                                    <option value="">请选择已发布材料</option>
                                    {materials.map((material) => (
                                        <option key={material.material_id} value={material.material_id}>
                                            {material.name} · {material.current_version?.version_label ?? "当前版本"}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label className="space-y-2 text-sm font-medium text-slate-700">
                                录音评测标准
                                <select
                                    value={value.scoringPromptId}
                                    onChange={(event) => updateValue({ ...value, scoringPromptId: event.target.value })}
                                    disabled={isMutating || !canManageTask}
                                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                >
                                    <option value="">请选择已发布评测标准</option>
                                    {prompts.map((prompt) => (
                                        <option key={prompt.prompt_id} value={prompt.prompt_id}>
                                            {prompt.name} v{prompt.version}
                                        </option>
                                    ))}
                                </select>
                            </label>
                        </div>
                        <div className="flex flex-wrap gap-3 text-sm font-semibold text-blue-700">
                            <Link className="underline" href={`/admin/sales-trainer/units/new?scenario=${scenario.slug}`}>
                                快速新建训练单元
                            </Link>
                            <Link className="underline" href={`/admin/sales-trainer/materials?scenario=${scenario.slug}`}>
                                快速新建或上传材料
                            </Link>
                            <Link className="underline" href={`/admin/sales-trainer/score-standards/new?scenario=${scenario.slug}`}>
                                快速新建评测标准
                            </Link>
                        </div>
                    </GlassCard>

                    <GlassCard className="space-y-4 p-5">
                        <div>
                            <h2 className="text-base font-bold text-slate-900">发布治理</h2>
                            <p className="text-sm text-slate-500">
                                保存会生成待发布修订；发布或回滚只影响后续学员，历史录音和评分按提交快照回放。
                            </p>
                        </div>
                        <textarea
                            value={changeReason}
                            onChange={(event) => setChangeReason(event.target.value)}
                            placeholder="填写本次变更说明，例如：配置公司产品 Demo 讲解任务"
                            className="min-h-24 w-full rounded-xl border border-slate-200 bg-white p-3 text-sm"
                        />
                        <div className="flex flex-wrap gap-3">
                            <button
                                type="button"
                                disabled={isMutating || !canManageTask}
                                onClick={() => void saveCurrentRevision()}
                                className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                            >
                                保存待发布修订
                            </button>
                            <button
                                type="button"
                                disabled={isMutating || !canManageTask}
                                onClick={() => void publishWorkingRevision()}
                                className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 disabled:opacity-50"
                            >
                                发布当前修订
                            </button>
                            <button
                                type="button"
                                disabled={isMutating || !canManageTask}
                                onClick={() => void load()}
                                className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 disabled:opacity-50"
                            >
                                重新加载
                            </button>
                        </div>
                    </GlassCard>
                </>
            ) : null}
        </AdminIndexShell>
    );
}
