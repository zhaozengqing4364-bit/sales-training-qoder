"use client";

import { usePathname } from "next/navigation";
import { AlertTriangle, Plus, Save, ShieldCheck, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    BusinessEtiquetteCapabilityConfig,
    BusinessEtiquetteCapabilitySnapshotResponse,
    BusinessEtiquetteChapterCapabilityBinding,
    BusinessEtiquetteEvidenceRuleConfig,
    BusinessEtiquetteMasteryLevelConfig,
    SalesTrainerAdminCapabilities,
} from "@/lib/api/types";

function sourceLabel(source: BusinessEtiquetteCapabilitySnapshotResponse["source"]): string {
    if (source === "working_revision") {
        return "未发布草稿";
    }
    if (source === "active_revision") {
        return "已发布快照";
    }
    return "默认种子";
}

function statusLabel(status: BusinessEtiquetteCapabilityConfig["status"]): string {
    if (status === "published") {
        return "已发布";
    }
    if (status === "archived") {
        return "已归档";
    }
    return "草稿";
}

function capabilityKeysText(binding: BusinessEtiquetteChapterCapabilityBinding): string {
    return binding.capability_keys.join(", ");
}

function parseCapabilityKeys(value: string): string[] {
    return value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
}

function formatJson(value: unknown): string {
    return JSON.stringify(value, null, 2);
}

function parseJsonArray<T>(value: string, label: string): T[] {
    const parsed = JSON.parse(value) as unknown;
    if (!Array.isArray(parsed)) {
        throw new Error(`${label} 必须是 JSON 数组。`);
    }
    return parsed as T[];
}

function cloneCapabilityTemplate(
    template: BusinessEtiquetteCapabilityConfig,
    nextIndex: number,
): BusinessEtiquetteCapabilityConfig {
    return {
        ...template,
        capability_key: `custom_capability_${nextIndex}`,
        display_name: "新能力点",
        description: "",
        status: "draft",
        mastery_levels: template.mastery_levels.map((item) => ({ ...item })),
        evidence_rules: template.evidence_rules.map((item) => ({ ...item })),
    };
}

export default function BusinessEtiquetteCapabilitiesPage() {
    const pathname = usePathname();
    const toast = useToast();
    const [snapshot, setSnapshot] = useState<BusinessEtiquetteCapabilitySnapshotResponse | null>(null);
    const [capabilities, setCapabilities] = useState<BusinessEtiquetteCapabilityConfig[]>([]);
    const [chapterBindings, setChapterBindings] = useState<BusinessEtiquetteChapterCapabilityBinding[]>([]);
    const [selectedKey, setSelectedKey] = useState<string | null>(null);
    const [masteryLevelsJson, setMasteryLevelsJson] = useState("[]");
    const [evidenceRulesJson, setEvidenceRulesJson] = useState("[]");
    const [reason, setReason] = useState("保存商务礼仪能力点快照");
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [archiveKey, setArchiveKey] = useState<string | null>(null);
    const [adminCapabilities, setAdminCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const canAccessCapabilities = isSalesTrainerAdminPathAllowedForCapabilities(pathname, adminCapabilities);

    const selectedCapability = useMemo(
        () => capabilities.find((capability) => capability.capability_key === selectedKey) ?? capabilities[0] ?? null,
        [capabilities, selectedKey],
    );
    const archiveCapability = capabilities.find((capability) => capability.capability_key === archiveKey) ?? null;

    const selectCapability = useCallback((capability: BusinessEtiquetteCapabilityConfig | null) => {
        setSelectedKey(capability?.capability_key ?? null);
        setMasteryLevelsJson(formatJson(capability?.mastery_levels ?? []));
        setEvidenceRulesJson(formatJson(capability?.evidence_rules ?? []));
    }, []);

    const applySnapshot = useCallback((nextSnapshot: BusinessEtiquetteCapabilitySnapshotResponse) => {
        setSnapshot(nextSnapshot);
        setCapabilities(nextSnapshot.capabilities);
        setChapterBindings(nextSnapshot.chapter_bindings);
        selectCapability(nextSnapshot.capabilities[0] ?? null);
    }, [selectCapability]);

    useEffect(() => {
        let isActive = true;
        void api.admin.salesTrainer.getCapabilities()
            .then((result) => {
                if (!isActive) {
                    return;
                }
                setAdminCapabilities(result);
                setCapabilityError(null);
            })
            .catch((error) => {
                if (!isActive) {
                    return;
                }
                setAdminCapabilities(null);
                setCapabilityError(getApiErrorMessage(error));
            })
            .finally(() => {
                if (isActive) {
                    setIsCapabilityLoading(false);
                }
            });
        return () => {
            isActive = false;
        };
    }, []);

    useEffect(() => {
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessCapabilities) {
            setSnapshot(null);
            setCapabilities([]);
            setChapterBindings([]);
            selectCapability(null);
            setIsLoading(false);
            return;
        }
        let isActive = true;
        setIsLoading(true);
        void api.admin.salesTrainer.getBusinessEtiquetteCapabilities()
            .then((nextSnapshot) => {
                if (!isActive) {
                    return;
                }
                applySnapshot(nextSnapshot);
            })
            .catch((error) => {
                toast.error(getApiErrorMessage(error));
            })
            .finally(() => {
                if (isActive) {
                    setIsLoading(false);
                }
            });
        return () => {
            isActive = false;
        };
    }, [applySnapshot, canAccessCapabilities, isCapabilityLoading, selectCapability, toast]);

    function updateCapability(
        capabilityKey: string,
        patch: Partial<BusinessEtiquetteCapabilityConfig>,
    ) {
        setCapabilities((current) => current.map((capability) => (
            capability.capability_key === capabilityKey
                ? { ...capability, ...patch }
                : capability
        )));
    }

    function updateBinding(chapterOrder: number, value: string) {
        setChapterBindings((current) => current.map((binding) => (
            binding.chapter_order === chapterOrder
                ? { ...binding, capability_keys: parseCapabilityKeys(value) }
                : binding
        )));
    }

    function addCapability() {
        const template = capabilities[0];
        if (!template) {
            return;
        }
        const nextCapability = cloneCapabilityTemplate(template, capabilities.length + 1);
        setCapabilities((current) => [...current, nextCapability]);
        selectCapability(nextCapability);
    }

    function capabilitiesForSave(): BusinessEtiquetteCapabilityConfig[] {
        if (!selectedCapability) {
            return capabilities;
        }
        const masteryLevels = parseJsonArray<BusinessEtiquetteMasteryLevelConfig>(
            masteryLevelsJson,
            "掌握等级",
        );
        const evidenceRules = parseJsonArray<BusinessEtiquetteEvidenceRuleConfig>(
            evidenceRulesJson,
            "证据规则",
        );
        return capabilities.map((capability) => (
            capability.capability_key === selectedCapability.capability_key
                ? {
                    ...capability,
                    mastery_levels: masteryLevels,
                    evidence_rules: evidenceRules,
                }
                : capability
        ));
    }

    async function saveSnapshot() {
        if (!snapshot || !canAccessCapabilities) {
            return;
        }
        setIsSaving(true);
        try {
            const saved = await api.admin.salesTrainer.saveBusinessEtiquetteCapabilities({
                training_pack_key: snapshot.training_pack_key,
                capabilities: capabilitiesForSave(),
                chapter_bindings: chapterBindings,
                reason,
            });
            applySnapshot(saved);
            toast.success("能力点快照已保存为训练包草稿版本。");
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsSaving(false);
        }
    }

    async function publishCapability(capabilityKey: string) {
        if (!snapshot || !canAccessCapabilities) {
            return;
        }
        setIsSaving(true);
        try {
            const saved = await api.admin.salesTrainer.publishBusinessEtiquetteCapability(
                capabilityKey,
                {
                    training_pack_key: snapshot.training_pack_key,
                    reason: `发布商务礼仪能力点 ${capabilityKey}`,
                },
            );
            applySnapshot(saved);
            toast.success("能力点已标记为已发布。");
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsSaving(false);
        }
    }

    async function archiveSelectedCapability() {
        if (!snapshot || !archiveCapability || !canAccessCapabilities) {
            return;
        }
        setIsSaving(true);
        try {
            const saved = await api.admin.salesTrainer.archiveBusinessEtiquetteCapability(
                archiveCapability.capability_key,
                {
                    training_pack_key: snapshot.training_pack_key,
                    reason: `归档商务礼仪能力点 ${archiveCapability.capability_key}`,
                },
            );
            applySnapshot(saved);
            setArchiveKey(null);
            toast.success("能力点已归档。");
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsSaving(false);
        }
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="商务礼仪能力点"
                    description="管理训练包版本快照内的能力点、章节绑定、达标线和证据规则。"
                    secondaryActions={(
                        <div className="flex flex-wrap gap-2">
                            {canAccessCapabilities ? (
                                <>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        className="rounded-full"
                                        onClick={addCapability}
                                        disabled={isLoading || !capabilities.length}
                                    >
                                        <Plus className="mr-2 h-4 w-4" />
                                        新增能力点
                                    </Button>
                                    <Button
                                        type="button"
                                        className="rounded-full bg-slate-900 text-white"
                                        onClick={() => void saveSnapshot()}
                                        disabled={isLoading || isSaving || !snapshot}
                                    >
                                        <Save className="mr-2 h-4 w-4" />
                                        保存能力点快照
                                    </Button>
                                </>
                            ) : null}
                            <SalesTrainerAdminModuleNav currentPath={pathname} capabilities={adminCapabilities} />
                        </div>
                    )}
                />
            )}
        >
            {isCapabilityLoading ? (
                <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
                    正在校验能力点管理权限...
                </div>
            ) : capabilityError || !canAccessCapabilities ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-800">
                    <div className="flex items-start gap-3">
                        <AlertTriangle className="mt-0.5 h-5 w-5" aria-hidden />
                        <div>
                            <h2 className="font-bold text-amber-950">能力点管理权限不足</h2>
                            <p className="mt-1 text-sm leading-6">
                                当前页不会在权限未确认时读取或展示商务礼仪能力点写入入口。请联系管理员开通内容管理权限后重试。
                            </p>
                            {capabilityError ? (
                                <p className="mt-2 text-sm font-medium">{capabilityError}</p>
                            ) : null}
                        </div>
                    </div>
                </div>
            ) : isLoading ? (
                <div className="h-64 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
            ) : snapshot ? (
                <div className="space-y-6">
                    <GlassCard className="p-5">
                        <div className="grid gap-3 md:grid-cols-4">
                            <Metric label="来源" value={sourceLabel(snapshot.source)} />
                            <Metric
                                label="训练包"
                                value={snapshot.training_pack_key}
                            />
                            <Metric
                                label="草稿版本"
                                value={snapshot.working_revision_no ? `v${snapshot.working_revision_no}` : "--"}
                            />
                            <Metric
                                label="已发布版本"
                                value={snapshot.active_revision_no ? `v${snapshot.active_revision_no}` : "--"}
                            />
                        </div>
                        {snapshot.needs_save ? (
                            <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800">
                                当前展示的是后端默认能力点种子，请保存为训练包草稿后再发布训练包。
                            </p>
                        ) : null}
                    </GlassCard>

                    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_420px]">
                        <GlassCard className="overflow-hidden">
                            <div className="border-b border-slate-100 px-5 py-4">
                                <h2 className="text-lg font-bold text-slate-900">
                                    能力点清单
                                </h2>
                            </div>
                            <div className="divide-y divide-slate-100">
                                {capabilities.map((capability) => (
                                    <CapabilityRow
                                        key={capability.capability_key}
                                        capability={capability}
                                        isSelected={selectedCapability?.capability_key === capability.capability_key}
                                        onSelect={() => selectCapability(capability)}
                                        onChange={(patch) => updateCapability(capability.capability_key, patch)}
                                        onPublish={() => void publishCapability(capability.capability_key)}
                                        onArchive={() => setArchiveKey(capability.capability_key)}
                                        disabled={isSaving}
                                    />
                                ))}
                            </div>
                        </GlassCard>

                        <div className="space-y-6">
                            <GlassCard className="p-5">
                                <h2 className="text-lg font-bold text-slate-900">
                                    等级与证据规则
                                </h2>
                                <p className="mt-1 text-sm text-slate-500">
                                    当前能力点：{selectedCapability?.display_name ?? "--"}
                                </p>
                                <label className="mt-4 block text-sm font-semibold text-slate-800">
                                    掌握等级 JSON
                                    <textarea
                                        className="mt-2 h-48 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-xs text-slate-700"
                                        value={masteryLevelsJson}
                                        onChange={(event) => setMasteryLevelsJson(event.target.value)}
                                    />
                                </label>
                                <label className="mt-4 block text-sm font-semibold text-slate-800">
                                    证据规则 JSON
                                    <textarea
                                        className="mt-2 h-48 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-xs text-slate-700"
                                        value={evidenceRulesJson}
                                        onChange={(event) => setEvidenceRulesJson(event.target.value)}
                                    />
                                </label>
                            </GlassCard>

                            <GlassCard className="p-5">
                                <h2 className="text-lg font-bold text-slate-900">
                                    章节能力点绑定
                                </h2>
                                <div className="mt-4 space-y-3">
                                    {chapterBindings.map((binding) => (
                                        <label
                                            key={binding.chapter_order}
                                            className="block text-sm font-semibold text-slate-800"
                                        >
                                            第 {binding.chapter_order} 章
                                            <input
                                                className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
                                                value={capabilityKeysText(binding)}
                                                onChange={(event) => updateBinding(binding.chapter_order, event.target.value)}
                                            />
                                        </label>
                                    ))}
                                </div>
                            </GlassCard>

                            <GlassCard className="p-5">
                                <label className="block text-sm font-semibold text-slate-800">
                                    保存原因
                                    <textarea
                                        className="mt-2 min-h-24 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
                                        value={reason}
                                        onChange={(event) => setReason(event.target.value)}
                                    />
                                </label>
                            </GlassCard>
                        </div>
                    </div>
                </div>
            ) : (
                <GlassCard className="p-6 text-sm text-slate-500">
                    暂未读取到商务礼仪能力点配置。
                </GlassCard>
            )}

            <ConfirmDialog
                open={Boolean(archiveCapability)}
                onOpenChange={(open) => {
                    if (!open) {
                        setArchiveKey(null);
                    }
                }}
                title="归档能力点"
                description={`归档后章节和小单元不能继续引用“${archiveCapability?.display_name ?? ""}”。`}
                confirmText="确认归档"
                variant="danger"
                isLoading={isSaving}
                onConfirm={() => void archiveSelectedCapability()}
                icon={<Trash2 className="h-5 w-5" />}
            />
        </AdminIndexShell>
    );
}

function CapabilityRow({
    capability,
    disabled,
    isSelected,
    onArchive,
    onChange,
    onPublish,
    onSelect,
}: {
    readonly capability: BusinessEtiquetteCapabilityConfig;
    readonly disabled: boolean;
    readonly isSelected: boolean;
    readonly onArchive: () => void;
    readonly onChange: (patch: Partial<BusinessEtiquetteCapabilityConfig>) => void;
    readonly onPublish: () => void;
    readonly onSelect: () => void;
}) {
    return (
        <div className={`grid gap-3 px-5 py-4 lg:grid-cols-[1fr_160px_160px] ${isSelected ? "bg-slate-50" : ""}`}>
            <div>
                <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase text-slate-400">
                        {capability.capability_key}
                    </p>
                    <Button
                        type="button"
                        variant="ghost"
                        className="rounded-full px-3 py-1 text-xs"
                        onClick={onSelect}
                    >
                        {isSelected ? "编辑中" : "编辑等级"}
                    </Button>
                </div>
                <input
                    className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-900"
                    value={capability.display_name}
                    onChange={(event) => onChange({ display_name: event.target.value })}
                />
                <textarea
                    className="mt-2 min-h-20 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
                    value={capability.description ?? ""}
                    onChange={(event) => onChange({ description: event.target.value })}
                />
            </div>
            <label className="text-sm font-semibold text-slate-800">
                默认达标线
                <input
                    className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
                    type="number"
                    min={0}
                    max={100}
                    value={capability.default_threshold}
                    onChange={(event) => onChange({ default_threshold: Number(event.target.value) })}
                />
            </label>
            <div className="space-y-3">
                <label className="block text-sm font-semibold text-slate-800">
                    状态
                    <select
                        className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
                        value={capability.status}
                        onChange={(event) => onChange({
                            status: event.target.value as BusinessEtiquetteCapabilityConfig["status"],
                        })}
                    >
                        <option value="draft">草稿</option>
                        <option value="published">已发布</option>
                        <option value="archived">已归档</option>
                    </select>
                </label>
                <div className="flex flex-wrap gap-2">
                    <Button
                        type="button"
                        variant="outline"
                        className="rounded-full"
                        onClick={onPublish}
                        disabled={disabled || capability.status === "published"}
                    >
                        <ShieldCheck className="mr-2 h-4 w-4" />
                        发布
                    </Button>
                    <Button
                        type="button"
                        variant="outline"
                        className="rounded-full border-red-200 text-red-700"
                        onClick={onArchive}
                        disabled={disabled || capability.status === "archived"}
                    >
                        归档
                    </Button>
                </div>
                <p className="text-xs font-semibold text-slate-400">
                    {statusLabel(capability.status)}
                </p>
            </div>
        </div>
    );
}

function Metric({ label, value }: { readonly label: string; readonly value: string }) {
    return (
        <div className="rounded-xl border border-slate-100 bg-white/70 px-4 py-3">
            <p className="text-xs font-semibold text-slate-400">{label}</p>
            <p className="mt-1 break-all text-sm font-bold text-slate-900">{value}</p>
        </div>
    );
}
