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
import type { AdminKnowledgeQueryProfile } from "@/lib/api/types";
import { ProfileListDetail } from "../shared/profile-list-detail";
import { NumberField } from "../shared/number-field";

const REWRITE_STRATEGY_OPTIONS = [
    { value: "single_query", label: "单次查询" },
    { value: "multi_query", label: "多查询扩展" },
] as const;

const REWRITE_STRATEGY_BADGE: Record<string, string> = {
    single_query: "单次",
    multi_query: "多查询",
};

interface QueryProfilesTabProps {
    versionId: string;
}

export function QueryProfilesTab({ versionId }: QueryProfilesTabProps) {
    const toast = useToast();
    const [items, setItems] = useState<AdminKnowledgeQueryProfile[]>([]);
    const [loading, setLoading] = useState(true);
    const [deleteTarget, setDeleteTarget] = useState<AdminKnowledgeQueryProfile | null>(null);
    const [deleting, setDeleting] = useState(false);

    const reloadItems = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.admin.getKnowledgeQueryProfiles(versionId);
            setItems(data);
        } catch (err) {
            toast.error(`加载查询配置失败：${getApiErrorMessage(err)}`);
        } finally {
            setLoading(false);
        }
    }, [versionId, toast]);

    useEffect(() => {
        void reloadItems();
    }, [reloadItems]);

    const handleSave = useCallback(
        async (data: Partial<AdminKnowledgeQueryProfile>, isCreating: boolean) => {
            if (isCreating) {
                await api.admin.createKnowledgeQueryProfile(versionId, {
                    profile_key: data.profile_key ?? "",
                    description: data.description ?? null,
                    rewrite_strategy: data.rewrite_strategy ?? "single_query",
                    max_rewrite_queries: data.max_rewrite_queries ?? 3,
                    stop_after_first_success: data.stop_after_first_success ?? false,
                    enabled: data.enabled ?? true,
                });
                toast.success("查询配置已创建");
            } else {
                await api.admin.updateKnowledgeQueryProfile(versionId, data.id!, {
                    profile_key: data.profile_key,
                    description: data.description,
                    rewrite_strategy: data.rewrite_strategy,
                    max_rewrite_queries: data.max_rewrite_queries,
                    stop_after_first_success: data.stop_after_first_success,
                    enabled: data.enabled,
                });
                toast.success("查询配置已更新");
            }
        },
        [versionId, toast],
    );

    const handleDelete = useCallback(
        async (id: string) => {
            setDeleting(true);
            try {
                await api.admin.deleteKnowledgeQueryProfile(versionId, id);
                toast.success("查询配置已删除");
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
        async (item: AdminKnowledgeQueryProfile, enabled: boolean) => {
            try {
                await api.admin.updateKnowledgeQueryProfile(versionId, item.id, { enabled });
                await reloadItems();
            } catch (err) {
                toast.error(`更新失败：${getApiErrorMessage(err)}`);
            }
        },
        [versionId, toast, reloadItems],
    );

    return (
        <>
            <ProfileListDetail<AdminKnowledgeQueryProfile>
                items={items}
                loading={loading}
                searchPlaceholder="搜索配置标识..."
                newItemLabel="新增查询配置"
                renderItemLabel={(item) => item.profile_key}
                renderItemMeta={(item) => (
                    <Badge variant="secondary" className="text-xs">
                        {REWRITE_STRATEGY_BADGE[item.rewrite_strategy] ?? item.rewrite_strategy}
                    </Badge>
                )}
                renderDetail={({ item, isCreating, onSave, onCancel, onChange }) => (
                    <div className="space-y-4">
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">配置标识</label>
                            <Input
                                value={item?.profile_key ?? ""}
                                onChange={(e) => onChange("profile_key", e.target.value)}
                                placeholder="例如：default_query"
                                className="h-10"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">描述</label>
                            <textarea
                                value={item?.description ?? ""}
                                onChange={(e) => onChange("description", e.target.value || null)}
                                placeholder="此配置的用途说明"
                                rows={2}
                                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200 resize-none"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">改写策略</label>
                            <select
                                value={item?.rewrite_strategy ?? "single_query"}
                                onChange={(e) => onChange("rewrite_strategy", e.target.value)}
                                className="h-10 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                            >
                                {REWRITE_STRATEGY_OPTIONS.map((opt) => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>
                        <NumberField
                            label="最大改写查询数"
                            description="multi_query 模式下生成的最大扩展查询数"
                            value={item?.max_rewrite_queries ?? 3}
                            onChange={(v) => onChange("max_rewrite_queries", v)}
                            min={1}
                            max={10}
                            step={1}
                        />
                        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <div>
                                <label className="block text-sm font-medium text-slate-700">首次成功后停止</label>
                                <p className="text-xs text-slate-500">检索到结果后立即停止后续查询</p>
                            </div>
                            <Switch
                                checked={item?.stop_after_first_success ?? false}
                                onCheckedChange={(checked) => onChange("stop_after_first_success", checked)}
                            />
                        </div>
                        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <div>
                                <label className="block text-sm font-medium text-slate-700">启用</label>
                                <p className="text-xs text-slate-500">禁用后此配置不会参与查询改写</p>
                            </div>
                            <Switch
                                checked={item?.enabled ?? true}
                                onCheckedChange={(checked) => onChange("enabled", checked)}
                            />
                        </div>
                        <div className="flex items-center justify-between pt-2">
                            <div>
                                {!isCreating && item?.id && (
                                    <Button type="button" variant="outline" size="sm" className="rounded-full text-red-600 hover:text-red-700" onClick={() => setDeleteTarget(item)}>
                                        <Trash2 className="mr-1 h-3.5 w-3.5" /> 删除
                                    </Button>
                                )}
                            </div>
                            <div className="flex gap-2">
                                <Button type="button" variant="outline" className="rounded-full" onClick={onCancel}>取消</Button>
                                <Button type="button" className="rounded-full" onClick={() => void onSave(item as Partial<AdminKnowledgeQueryProfile>)}>保存</Button>
                            </div>
                        </div>
                    </div>
                )}
                onCreateNew={() => ({
                    id: "",
                    config_version_id: versionId,
                    profile_key: "",
                    description: null,
                    rewrite_strategy: "single_query",
                    max_rewrite_queries: 3,
                    stop_after_first_success: false,
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
                description={`确定要删除查询配置「${deleteTarget?.profile_key}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={() => { if (deleteTarget) void handleDelete(deleteTarget.id); }}
                isLoading={deleting}
            />
        </>
    );
}
