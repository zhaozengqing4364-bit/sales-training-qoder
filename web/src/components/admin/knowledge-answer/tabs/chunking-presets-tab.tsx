"use client";

import { useState, useCallback, useEffect } from "react";
import { Trash2, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    AdminKnowledgeChunkingPreset,
    CreateKnowledgeChunkingPresetRequest,
    UpdateKnowledgeChunkingPresetRequest,
} from "@/lib/api/types";
import { ProfileListDetail } from "../shared/profile-list-detail";
import { NumberField } from "../shared/number-field";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const STRATEGY_OPTIONS = [
    { value: "element_boundary", label: "元素边界" },
    { value: "fixed_size", label: "固定大小" },
    { value: "parent_child", label: "父子分块" },
] as const;

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */

interface ChunkingPresetsTabProps {
    versionId: string;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ChunkingPresetsTab({ versionId }: ChunkingPresetsTabProps) {
    const toast = useToast();
    const [items, setItems] = useState<AdminKnowledgeChunkingPreset[]>([]);
    const [loading, setLoading] = useState(true);
    const [deleteTarget, setDeleteTarget] = useState<AdminKnowledgeChunkingPreset | null>(null);
    const [deleting, setDeleting] = useState(false);

    /* ── Data loading ── */

    const reloadItems = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.admin.getKnowledgeChunkingPresets(versionId);
            setItems(data);
        } catch (err) {
            toast.error(`加载分块预设失败：${getApiErrorMessage(err)}`);
        } finally {
            setLoading(false);
        }
    }, [versionId, toast]);

    useEffect(() => {
        void reloadItems();
    }, [reloadItems]);

    /* ── CRUD ── */

    const handleSave = useCallback(
        async (data: Partial<AdminKnowledgeChunkingPreset>, isCreating: boolean) => {
            if (isCreating) {
                const payload: CreateKnowledgeChunkingPresetRequest = {
                    profile_key: data.profile_key ?? "",
                    description: data.description ?? null,
                    chunking_strategy: data.chunking_strategy ?? "element_boundary",
                    chunk_size: data.chunk_size ?? 500,
                    chunk_overlap: data.chunk_overlap ?? 50,
                    is_default: data.is_default ?? false,
                    enabled: data.enabled ?? true,
                };
                await api.admin.createKnowledgeChunkingPreset(versionId, payload);
                toast.success("分块预设已创建");
            } else {
                const payload: UpdateKnowledgeChunkingPresetRequest = {
                    profile_key: data.profile_key,
                    description: data.description ?? null,
                    chunking_strategy: data.chunking_strategy,
                    chunk_size: data.chunk_size,
                    chunk_overlap: data.chunk_overlap,
                    is_default: data.is_default,
                    enabled: data.enabled,
                };
                await api.admin.updateKnowledgeChunkingPreset(versionId, data.id!, payload);
                toast.success("分块预设已更新");
            }
        },
        [versionId, toast],
    );

    const handleDelete = useCallback(
        async (id: string) => {
            setDeleting(true);
            try {
                await api.admin.deleteKnowledgeChunkingPreset(versionId, id);
                toast.success("分块预设已删除");
                setDeleteTarget(null);
            } catch (err) {
                toast.error(`删除失败：${getApiErrorMessage(err)}`);
            } finally {
                setDeleting(false);
            }
        },
        [versionId, toast],
    );

    const handleToggleEnabled = useCallback(
        async (item: AdminKnowledgeChunkingPreset, enabled: boolean) => {
            try {
                await api.admin.updateKnowledgeChunkingPreset(versionId, item.id, { enabled });
                await reloadItems();
            } catch (err) {
                toast.error(`更新失败：${getApiErrorMessage(err)}`);
            }
        },
        [versionId, toast, reloadItems],
    );

    const handleSetDefault = useCallback(
        async (id: string) => {
            try {
                await api.admin.setDefaultChunkingPreset(versionId, id);
                toast.success("已设为默认");
                await reloadItems();
            } catch (err) {
                toast.error(`操作失败：${getApiErrorMessage(err)}`);
            }
        },
        [versionId, toast, reloadItems],
    );

    /* ── Render ── */

    return (
        <>
            <ProfileListDetail<AdminKnowledgeChunkingPreset>
                items={items}
                loading={loading}
                searchPlaceholder="搜索预设标识..."
                newItemLabel="新增分块预设"
                renderItemLabel={(item) =>
                    item.is_default ? `${item.profile_key} (默认)` : item.profile_key || "未命名"
                }
                renderItemMeta={(item) => (
                    <>
                        <span className="text-xs text-slate-400">
                            {STRATEGY_OPTIONS.find((o) => o.value === item.chunking_strategy)?.label ?? item.chunking_strategy}
                        </span>
                        <span className="text-xs text-slate-400">{item.chunk_size}字</span>
                        <span className="text-xs text-slate-400">重叠{item.chunk_overlap}</span>
                    </>
                )}
                renderDetail={({ item, isCreating, onSave, onCancel, onChange }) => (
                    <div className="space-y-4">
                        {/* Profile Key */}
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">预设标识</label>
                            <Input
                                value={item?.profile_key ?? ""}
                                onChange={(e) => onChange("profile_key", e.target.value)}
                                placeholder="例如：default, technical_docs"
                                className="h-10"
                            />
                        </div>

                        {/* Description */}
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">描述</label>
                            <Input
                                value={item?.description ?? ""}
                                onChange={(e) => onChange("description", e.target.value || null)}
                                placeholder="可选：说明此预设的适用场景"
                                className="h-10"
                            />
                        </div>

                        {/* Chunking Strategy */}
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">分块策略</label>
                            <select
                                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm h-10"
                                value={item?.chunking_strategy ?? "element_boundary"}
                                onChange={(e) => onChange("chunking_strategy", e.target.value)}
                            >
                                {STRATEGY_OPTIONS.map((o) => (
                                    <option key={o.value} value={o.value}>
                                        {o.label}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Chunk Size */}
                        <NumberField
                            label="分块大小"
                            description="每个文本块的最大字符数"
                            value={item?.chunk_size ?? 500}
                            onChange={(v) => onChange("chunk_size", v)}
                            min={100}
                            max={2000}
                            step={50}
                        />

                        {/* Chunk Overlap */}
                        <NumberField
                            label="重叠字符数"
                            description="相邻块之间的重叠字符数"
                            value={item?.chunk_overlap ?? 50}
                            onChange={(v) => onChange("chunk_overlap", v)}
                            min={0}
                            max={500}
                            step={10}
                        />

                        {/* Set Default */}
                        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <div>
                                <label className="block text-sm font-medium text-slate-700">设为默认</label>
                                <p className="text-xs text-slate-500">每个版本仅有一个默认预设</p>
                            </div>
                            <Switch
                                checked={item?.is_default ?? false}
                                onCheckedChange={(checked) => onChange("is_default", checked)}
                            />
                        </div>

                        {/* Enabled */}
                        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <div>
                                <label className="block text-sm font-medium text-slate-700">启用</label>
                                <p className="text-xs text-slate-500">禁用后此预设不会被引用</p>
                            </div>
                            <Switch
                                checked={item?.enabled ?? true}
                                onCheckedChange={(checked) => onChange("enabled", checked)}
                            />
                        </div>

                        {/* Actions */}
                        <div className="flex items-center justify-between pt-2">
                            <div className="flex gap-2">
                                {!isCreating && item?.id && !item.is_default && (
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        className="rounded-full"
                                        onClick={() => void handleSetDefault(item.id)}
                                    >
                                        <Star className="mr-1 h-3.5 w-3.5" /> 设为默认
                                    </Button>
                                )}
                                {!isCreating && item?.id && (
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        className="rounded-full text-red-600 hover:text-red-700"
                                        onClick={() => setDeleteTarget(item)}
                                    >
                                        <Trash2 className="mr-1 h-3.5 w-3.5" /> 删除
                                    </Button>
                                )}
                            </div>
                            <div className="flex gap-2">
                                <Button type="button" variant="outline" className="rounded-full" onClick={onCancel}>
                                    取消
                                </Button>
                                <Button
                                    type="button"
                                    className="rounded-full"
                                    onClick={() => void onSave(item as Partial<AdminKnowledgeChunkingPreset>)}
                                >
                                    保存
                                </Button>
                            </div>
                        </div>
                    </div>
                )}
                onCreateNew={() => ({
                    id: "",
                    config_version_id: versionId,
                    profile_key: "",
                    description: null,
                    chunking_strategy: "element_boundary",
                    chunk_size: 500,
                    chunk_overlap: 50,
                    is_default: false,
                    enabled: true,
                    created_at: "",
                    updated_at: "",
                })}
                onSave={handleSave}
                onDelete={async (id) => {
                    await handleDelete(id);
                }}
                onToggleEnabled={handleToggleEnabled}
                reloadItems={reloadItems}
            />

            <ConfirmDialog
                open={deleteTarget !== null}
                onOpenChange={(open) => {
                    if (!open) setDeleteTarget(null);
                }}
                title="确认删除"
                description={`确定要删除分块预设「${deleteTarget?.profile_key ?? ""}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={() => {
                    if (deleteTarget) void handleDelete(deleteTarget.id);
                }}
                isLoading={deleting}
            />
        </>
    );
}
