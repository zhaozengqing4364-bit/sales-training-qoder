"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { Mic } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerScorePromptForm } from "@/components/admin/sales-trainer/score-prompt-form";
import { buildUnitTemplateForModule } from "@/components/admin/sales-trainer/unit-module-template";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/glass-modal";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import {
    audioEvaluationScenarioForPurpose,
    audioEvaluationScenarioForSlug,
    type AudioEvaluationModuleKey,
    type AudioEvaluationScenarioDefinition,
} from "@/lib/sales-trainer/audio-evaluation-scenarios";
import type {
    SalesTrainerAudioScorePromptCreateRequest,
    SalesTrainerMaterialType,
    SalesTrainerUnit,
} from "@/lib/api/types";
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

type QuickPanel = "unit" | "material" | "score-standard" | null;

function defaultMaterialKey(scenario: AudioEvaluationScenarioDefinition): string {
    return `${scenario.slug.replace(/-/g, "_")}_${Date.now()}`;
}

export default function SalesTrainerAudioTaskDetailPage() {
    const params = useParams<{ scenarioSlug: string }>();
    const pathname = usePathname();
    const router = useRouter();
    const toast = useToast();
    const scenario = audioEvaluationScenarioForSlug(paramValue(params.scenarioSlug));
    const [quickPanel, setQuickPanel] = useState<QuickPanel>(null);
    const [isQuickSubmitting, setIsQuickSubmitting] = useState(false);
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
                header={<AdminPageHeader title="录音任务不存在" description="未找到对应的录音任务。" />}
            >
                <AdminLoadErrorCard
                    title="录音任务不存在"
                    description="请从录音管理进入已配置的任务。"
                    message="未知录音任务。"
                    retryLabel="返回录音管理"
                    onRetry={() => router.push("/admin/sales-trainer/audio")}
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

    async function createAndBindUnit(draft: { readonly description: string; readonly name: string }) {
        if (!scenario || !value || !data) {
            return;
        }
        const template = buildUnitTemplateForModule({
            materials: data.materials,
            moduleKey,
            prompts: data.scorePrompts,
        });
        if (!template) {
            toast.error("当前录音任务没有可用的单元模板。");
            return;
        }
        setIsQuickSubmitting(true);
        try {
            const created = await api.admin.newcomerTraining.createUnit({
                name: draft.name.trim() || template.name,
                description: draft.description.trim() || template.description,
                unit_type: "audio_scoring",
                config: template.config,
                questions: [],
            });
            const published = await api.admin.newcomerTraining.publishUnit(created.unit_id);
            await load();
            updateValue({ ...value, targetUnitId: published.unit_id });
            setQuickPanel(null);
            toast.success("训练单元已创建、发布并绑定到当前录音任务");
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsQuickSubmitting(false);
        }
    }

    async function createAndBindMaterial(draft: {
        readonly description: string;
        readonly file: File | null;
        readonly materialKey: string;
        readonly materialType: SalesTrainerMaterialType;
        readonly name: string;
        readonly releaseNotes: string;
        readonly versionLabel: string;
        readonly versionTitle: string;
    }) {
        if (!scenario || !value) {
            return;
        }
        if (!draft.file) {
            toast.error("请先选择材料文件。");
            return;
        }
        setIsQuickSubmitting(true);
        try {
            const material = await api.admin.salesTrainer.createMaterial({
                material_key: draft.materialKey.trim() || defaultMaterialKey(scenario),
                name: draft.name.trim() || `${scenario.title}材料`,
                description: draft.description.trim() || null,
                material_type: draft.materialType,
                purpose: scenario.purposeKey,
            });
            const version = await api.admin.salesTrainer.uploadMaterialVersion(material.material_id, {
                file: draft.file,
                version_label: draft.versionLabel.trim() || "v1",
                title: draft.versionTitle.trim() || draft.file.name,
                release_notes: draft.releaseNotes.trim() || null,
            });
            const published = await api.admin.salesTrainer.publishMaterialVersion(version.version_id);
            await load();
            updateValue({
                ...value,
                materialId: material.material_id,
                materialVersionId: published.version_id,
            });
            setQuickPanel(null);
            toast.success("材料已创建、发布并绑定到当前录音任务");
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsQuickSubmitting(false);
        }
    }

    async function createAndBindScoreStandard(payload: SalesTrainerAudioScorePromptCreateRequest) {
        if (!value) {
            return;
        }
        setIsQuickSubmitting(true);
        try {
            const created = await api.admin.salesTrainer.createScorePrompt(payload);
            const published = await api.admin.salesTrainer.publishScorePrompt(created.prompt_id);
            await load();
            updateValue({ ...value, scoringPromptId: published.prompt_id });
            setQuickPanel(null);
            toast.success("评分标准已创建、发布并绑定到当前录音任务");
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsQuickSubmitting(false);
        }
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title={scenario.title}
                    description="在录音任务内完成单元、材料、评分标准和发布状态治理；发布只影响后续学员，历史录音按提交快照回放。"
                    icon={<Mic className="h-7 w-7 text-slate-800" />}
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={routeAccess.capabilities} />}
                />
            )}
        >
            {routeAccess.denialMessage ? (
                <AdminLoadErrorCard
                    title="录音任务不可访问"
                    description="当前账号没有配置新人训练录音任务的权限。"
                    message={routeAccess.denialMessage}
                    retryLabel="重新检查权限"
                    onRetry={routeAccess.reloadCapabilities}
                />
            ) : null}
            {canManageTask && isLoading && !value ? (
                <GlassCard className="p-8 text-center text-sm text-slate-500">
                    正在加载录音任务配置...
                </GlassCard>
            ) : null}
            {canManageTask && error ? (
                <GlassCard className="border-red-100 bg-red-50 p-4 text-sm font-medium text-red-700">
                    录音任务配置加载失败：{error}
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
                                <p className="text-sm font-semibold text-slate-500">任务策略</p>
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
                                选择已发布训练单元、材料和录音评分标准。缺资源时从当前录音管理模块内新建，保存后自动回到任务绑定。
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
                                录音评分标准
                                <select
                                    value={value.scoringPromptId}
                                    onChange={(event) => updateValue({ ...value, scoringPromptId: event.target.value })}
                                    disabled={isMutating || !canManageTask}
                                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                                >
                                    <option value="">请选择已发布评分标准</option>
                                    {prompts.map((prompt) => (
                                        <option key={prompt.prompt_id} value={prompt.prompt_id}>
                                            {prompt.name} v{prompt.version}
                                        </option>
                                    ))}
                                </select>
                            </label>
                        </div>
                        <div className="flex flex-wrap gap-3">
                            <Button
                                type="button"
                                variant="outline"
                                disabled={isMutating || !canManageTask}
                                onClick={() => setQuickPanel("unit")}
                            >
                                就地新建训练单元
                            </Button>
                            <Button
                                type="button"
                                variant="outline"
                                disabled={isMutating || !canManageTask}
                                onClick={() => setQuickPanel("material")}
                            >
                                就地新建或上传材料
                            </Button>
                            <Button
                                type="button"
                                variant="outline"
                                disabled={isMutating || !canManageTask}
                                onClick={() => setQuickPanel("score-standard")}
                            >
                                就地新建评分标准
                            </Button>
                            <Link className="self-center text-sm font-semibold text-blue-700 underline" href="/admin/sales-trainer/audio/materials">
                                查看全部材料
                            </Link>
                            <Link className="self-center text-sm font-semibold text-blue-700 underline" href="/admin/sales-trainer/audio/score-standards">
                                高级管理评分标准
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
                            placeholder={`填写本次变更说明，例如：配置${scenario.title}录音任务`}
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

            <Dialog
                open={quickPanel === "unit"}
                onOpenChange={(open) => {
                    if (!open) setQuickPanel(null);
                }}
            >
                <DialogContent className="max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>就地新建训练单元</DialogTitle>
                        <DialogDescription>
                            使用当前录音任务模板创建并发布单元，成功后自动绑定到 {scenario.title}。
                        </DialogDescription>
                    </DialogHeader>
                    <QuickUnitForm
                        scenario={scenario}
                        isSubmitting={isQuickSubmitting}
                        onSubmit={(draft) => void createAndBindUnit(draft)}
                    />
                </DialogContent>
            </Dialog>

            <Dialog
                open={quickPanel === "material"}
                onOpenChange={(open) => {
                    if (!open) setQuickPanel(null);
                }}
            >
                <DialogContent className="max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>就地新建或上传材料</DialogTitle>
                        <DialogDescription>
                            创建材料主档、上传并发布首个版本，成功后自动绑定到当前录音任务。
                        </DialogDescription>
                    </DialogHeader>
                    <QuickMaterialForm
                        scenario={scenario}
                        isSubmitting={isQuickSubmitting}
                        onSubmit={(draft) => void createAndBindMaterial(draft)}
                    />
                </DialogContent>
            </Dialog>

            <Dialog
                open={quickPanel === "score-standard"}
                onOpenChange={(open) => {
                    if (!open) setQuickPanel(null);
                }}
            >
                <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>就地新建评分标准</DialogTitle>
                        <DialogDescription>
                            普通模式填写维度、通过分和学员说明；高级 prompt 与 schema 已折叠。创建后会自动发布并绑定。
                        </DialogDescription>
                    </DialogHeader>
                    <SalesTrainerScorePromptForm
                        mode="create"
                        initialPurpose={scenario.purposeKey}
                        isSubmitting={isQuickSubmitting}
                        onSubmit={(payload) => void createAndBindScoreStandard(
                            payload as SalesTrainerAudioScorePromptCreateRequest,
                        )}
                    />
                </DialogContent>
            </Dialog>
        </AdminIndexShell>
    );
}

function QuickUnitForm({
    isSubmitting,
    onSubmit,
    scenario,
}: {
    readonly isSubmitting: boolean;
    readonly onSubmit: (draft: { readonly description: string; readonly name: string }) => void;
    readonly scenario: AudioEvaluationScenarioDefinition;
}) {
    const [name, setName] = useState(`${scenario.orderLabel}：${scenario.title}`);
    const [description, setDescription] = useState(scenario.description);
    return (
        <form
            className="space-y-4"
            onSubmit={(event) => {
                event.preventDefault();
                onSubmit({ description, name });
            }}
        >
            <label className="block space-y-2 text-sm font-medium text-slate-700">
                单元名称
                <Input value={name} onChange={(event) => setName(event.target.value)} disabled={isSubmitting} />
            </label>
            <label className="block space-y-2 text-sm font-medium text-slate-700">
                单元说明
                <textarea
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    disabled={isSubmitting}
                    rows={4}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                />
            </label>
            <div className="flex justify-end">
                <Button type="submit" disabled={isSubmitting} className="rounded-full bg-slate-900 text-white">
                    {isSubmitting ? "创建中..." : "创建、发布并绑定"}
                </Button>
            </div>
        </form>
    );
}

function QuickMaterialForm({
    isSubmitting,
    onSubmit,
    scenario,
}: {
    readonly isSubmitting: boolean;
    readonly onSubmit: (draft: {
        readonly description: string;
        readonly file: File | null;
        readonly materialKey: string;
        readonly materialType: SalesTrainerMaterialType;
        readonly name: string;
        readonly releaseNotes: string;
        readonly versionLabel: string;
        readonly versionTitle: string;
    }) => void;
    readonly scenario: AudioEvaluationScenarioDefinition;
}) {
    const [materialKey, setMaterialKey] = useState(defaultMaterialKey(scenario));
    const [name, setName] = useState(`${scenario.title}材料`);
    const [description, setDescription] = useState(scenario.description);
    const [materialType, setMaterialType] = useState<SalesTrainerMaterialType>(
        scenario.materialRequired ? "ppt_deck" : "script",
    );
    const [versionLabel, setVersionLabel] = useState("v1");
    const [versionTitle, setVersionTitle] = useState(`${scenario.title}首版材料`);
    const [releaseNotes, setReleaseNotes] = useState("录音任务就地创建并发布");
    const [file, setFile] = useState<File | null>(null);
    return (
        <form
            className="space-y-4"
            onSubmit={(event) => {
                event.preventDefault();
                onSubmit({
                    description,
                    file,
                    materialKey,
                    materialType,
                    name,
                    releaseNotes,
                    versionLabel,
                    versionTitle,
                });
            }}
        >
            <div className="grid gap-4 md:grid-cols-2">
                <label className="block space-y-2 text-sm font-medium text-slate-700">
                    材料名称
                    <Input value={name} onChange={(event) => setName(event.target.value)} disabled={isSubmitting} />
                </label>
                <label className="block space-y-2 text-sm font-medium text-slate-700">
                    材料标识
                    <Input value={materialKey} onChange={(event) => setMaterialKey(event.target.value)} disabled={isSubmitting} />
                </label>
                <label className="block space-y-2 text-sm font-medium text-slate-700">
                    材料类型
                    <select
                        value={materialType}
                        onChange={(event) => setMaterialType(event.target.value as SalesTrainerMaterialType)}
                        disabled={isSubmitting}
                        className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                    >
                        <option value="ppt_deck">PPT / 胶片</option>
                        <option value="script">讲解脚本</option>
                        <option value="example_audio">示例录音</option>
                        <option value="attachment">附件</option>
                    </select>
                </label>
                <label className="block space-y-2 text-sm font-medium text-slate-700">
                    版本号
                    <Input value={versionLabel} onChange={(event) => setVersionLabel(event.target.value)} disabled={isSubmitting} />
                </label>
            </div>
            <label className="block space-y-2 text-sm font-medium text-slate-700">
                版本标题
                <Input value={versionTitle} onChange={(event) => setVersionTitle(event.target.value)} disabled={isSubmitting} />
            </label>
            <label className="block space-y-2 text-sm font-medium text-slate-700">
                说明
                <textarea
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    disabled={isSubmitting}
                    rows={3}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                />
            </label>
            <label className="block space-y-2 text-sm font-medium text-slate-700">
                发布备注
                <Input value={releaseNotes} onChange={(event) => setReleaseNotes(event.target.value)} disabled={isSubmitting} />
            </label>
            <label className="block space-y-2 text-sm font-medium text-slate-700">
                材料文件
                <Input
                    type="file"
                    disabled={isSubmitting}
                    onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
            </label>
            <div className="flex justify-end">
                <Button type="submit" disabled={isSubmitting || !file} className="rounded-full bg-slate-900 text-white">
                    {isSubmitting ? "上传中..." : "创建、发布并绑定"}
                </Button>
            </div>
        </form>
    );
}
