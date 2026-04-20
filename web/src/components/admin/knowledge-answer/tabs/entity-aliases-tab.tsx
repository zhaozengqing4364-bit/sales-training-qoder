"use client";

import { useState, useCallback, useEffect } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { AdminKnowledgeEntityAlias } from "@/lib/api/types";
import { ProfileListDetail, type ProfileItem } from "../shared/profile-list-detail";
import { NumberField } from "../shared/number-field";

const ENTITY_TYPE_OPTIONS = [
    { value: "organization", label: "组织/公司" },
    { value: "product", label: "产品" },
    { value: "person", label: "人物" },
    { value: "feature", label: "特性" },
    { value: "other", label: "其他" },
] as const;

const ENTITY_TYPE_LABELS: Record<string, string> = Object.fromEntries(
    ENTITY_TYPE_OPTIONS.map((o) => [o.value, o.label]),
);

interface EntityAliasesTabProps {
    versionId: string;
}

export function EntityAliasesTab({ versionId }: EntityAliasesTabProps) {
    const toast = useToast();
    const [items, setItems] = useState<AdminKnowledgeEntityAlias[]>([]);
    const [loading, setLoading] = useState(true);
    const [deleteTarget, setDeleteTarget] = useState<AdminKnowledgeEntityAlias | null>(null);
    const [deleting, setDeleting] = useState(false);

    const reloadItems = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.admin.getKnowledgeEntityAliases(versionId);
            setItems(data);
        } catch (err) {
            toast.error(`加载实体别名失败：${getApiErrorMessage(err)}`);
        } finally {
            setLoading(false);
        }
    }, [versionId, toast]);

    useEffect(() => {
        void reloadItems();
    }, [reloadItems]);

    const handleSave = useCallback(
        async (data: Partial<AdminKnowledgeEntityAlias>, isCreating: boolean) => {
            if (isCreating) {
                await api.admin.createKnowledgeEntityAlias(versionId, {
                    canonical_entity: data.canonical_entity ?? "",
                    alias: data.alias ?? "",
                    entity_type: data.entity_type ?? "other",
                    confidence: data.confidence ?? 0.8,
                    enabled: data.enabled ?? true,
                });
                toast.success("实体别名已创建");
            } else {
                await api.admin.updateKnowledgeEntityAlias(versionId, data.id!, {
                    canonical_entity: data.canonical_entity,
                    alias: data.alias,
                    entity_type: data.entity_type,
                    confidence: data.confidence,
                    enabled: data.enabled,
                });
                toast.success("实体别名已更新");
            }
        },
        [versionId, toast],
    );

    const handleDelete = useCallback(
        async (id: string) => {
            setDeleting(true);
            try {
                await api.admin.deleteKnowledgeEntityAlias(versionId, id);
                toast.success("实体别名已删除");
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
        async (item: AdminKnowledgeEntityAlias, enabled: boolean) => {
            try {
                await api.admin.updateKnowledgeEntityAlias(versionId, item.id, { enabled });
                await reloadItems();
            } catch (err) {
                toast.error(`更新失败：${getApiErrorMessage(err)}`);
            }
        },
        [versionId, toast, reloadItems],
    );

    return (
        <>
            <ProfileListDetail<AdminKnowledgeEntityAlias>
                items={items}
                loading={loading}
                searchPlaceholder="搜索实体名称或别名..."
                newItemLabel="新增实体别名"
                renderItemLabel={(item) => item.canonical_entity || item.alias || "—"}
                renderItemMeta={(item) => (
                    <>
                        <Badge variant="secondary" className="text-xs">
                            {ENTITY_TYPE_LABELS[item.entity_type] ?? item.entity_type}
                        </Badge>
                        <span className="text-xs text-slate-400">
                            {(item.confidence * 100).toFixed(0)}%
                        </span>
                    </>
                )}
                renderDetail={({ item, isCreating, onSave, onCancel, onChange }) => (
                    <div className="space-y-4">
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">标准实体名称</label>
                            <Input
                                value={item?.canonical_entity ?? ""}
                                onChange={(e) => onChange("canonical_entity", e.target.value)}
                                placeholder="例如：石犀科技"
                                className="h-10"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">别名</label>
                            <Input
                                value={item?.alias ?? ""}
                                onChange={(e) => onChange("alias", e.target.value)}
                                placeholder="例如：世袭科技、食犀科技"
                                className="h-10"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">实体类型</label>
                            <select
                                value={item?.entity_type ?? "other"}
                                onChange={(e) => onChange("entity_type", e.target.value)}
                                className="h-10 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                            >
                                {ENTITY_TYPE_OPTIONS.map((opt) => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>
                        <NumberField
                            label="置信度"
                            description="别名到标准实体的映射置信度"
                            value={item?.confidence ?? 0.8}
                            onChange={(v) => onChange("confidence", v)}
                            min={0}
                            max={1}
                            step={0.05}
                        />
                        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <div>
                                <label className="block text-sm font-medium text-slate-700">启用</label>
                                <p className="text-xs text-slate-500">禁用后此别名不会参与实体识别</p>
                            </div>
                            <Switch
                                checked={item?.enabled ?? true}
                                onCheckedChange={(checked) => onChange("enabled", checked)}
                            />
                        </div>
                        <div className="flex items-center justify-between pt-2">
                            <div>
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
                                <Button type="button" variant="outline" className="rounded-full" onClick={onCancel}>取消</Button>
                                <Button type="button" className="rounded-full" onClick={() => void onSave(item as Partial<AdminKnowledgeEntityAlias>)}>保存</Button>
                            </div>
                        </div>
                    </div>
                )}
                onCreateNew={() => ({
                    id: "",
                    config_version_id: versionId,
                    canonical_entity: "",
                    alias: "",
                    entity_type: "other",
                    confidence: 0.8,
                    enabled: true,
                    created_at: "",
                    updated_at: "",
                })}
                onSave={handleSave}
                onDelete={async (id) => { await handleDelete(id); }}
                onToggleEnabled={handleToggleEnabled}
                reloadItems={reloadItems}
            />

            <ConfirmDialog
                open={deleteTarget !== null}
                onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
                title="确认删除"
                description={`确定要删除实体别名「${deleteTarget?.canonical_entity ?? deleteTarget?.alias}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={() => { if (deleteTarget) void handleDelete(deleteTarget.id); }}
                isLoading={deleting}
            />
        </>
    );
}
