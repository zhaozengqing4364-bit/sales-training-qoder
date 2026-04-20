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
import type { AdminKnowledgeAnswerabilityProfile } from "@/lib/api/types";
import { ProfileListDetail } from "../shared/profile-list-detail";
import { NumberField } from "../shared/number-field";
import { SlotEditor } from "../shared/slot-editor";

interface AnswerabilityTabProps {
    versionId: string;
}

export function AnswerabilityTab({ versionId }: AnswerabilityTabProps) {
    const toast = useToast();
    const [items, setItems] = useState<AdminKnowledgeAnswerabilityProfile[]>([]);
    const [loading, setLoading] = useState(true);
    const [deleteTarget, setDeleteTarget] = useState<AdminKnowledgeAnswerabilityProfile | null>(null);
    const [deleting, setDeleting] = useState(false);

    const reloadItems = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.admin.getKnowledgeAnswerabilityProfiles(versionId);
            setItems(data);
        } catch (err) {
            toast.error(`加载可回答性配置失败：${getApiErrorMessage(err)}`);
        } finally {
            setLoading(false);
        }
    }, [versionId, toast]);

    useEffect(() => {
        void reloadItems();
    }, [reloadItems]);

    const handleSave = useCallback(
        async (data: Partial<AdminKnowledgeAnswerabilityProfile>, isCreating: boolean) => {
            if (isCreating) {
                await api.admin.createKnowledgeAnswerabilityProfile(versionId, {
                    profile_key: data.profile_key ?? "",
                    required_slots: data.required_slots ?? [],
                    optional_slots: data.optional_slots ?? [],
                    sufficient_threshold: data.sufficient_threshold ?? 0.66,
                    partial_threshold: data.partial_threshold ?? 0.5,
                    enabled: data.enabled ?? true,
                });
                toast.success("可回答性配置已创建");
            } else {
                await api.admin.updateKnowledgeAnswerabilityProfile(versionId, data.id!, {
                    profile_key: data.profile_key,
                    required_slots: data.required_slots,
                    optional_slots: data.optional_slots,
                    sufficient_threshold: data.sufficient_threshold,
                    partial_threshold: data.partial_threshold,
                    enabled: data.enabled,
                });
                toast.success("可回答性配置已更新");
            }
        },
        [versionId, toast],
    );

    const handleDelete = useCallback(
        async (id: string) => {
            setDeleting(true);
            try {
                await api.admin.deleteKnowledgeAnswerabilityProfile(versionId, id);
                toast.success("可回答性配置已删除");
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
        async (item: AdminKnowledgeAnswerabilityProfile, enabled: boolean) => {
            try {
                await api.admin.updateKnowledgeAnswerabilityProfile(versionId, item.id, { enabled });
                await reloadItems();
            } catch (err) {
                toast.error(`更新失败：${getApiErrorMessage(err)}`);
            }
        },
        [versionId, toast, reloadItems],
    );

    return (
        <>
            <ProfileListDetail<AdminKnowledgeAnswerabilityProfile>
                items={items}
                loading={loading}
                searchPlaceholder="搜索配置标识..."
                newItemLabel="新增可回答性配置"
                renderItemLabel={(item) => item.profile_key || "未命名"}
                renderItemMeta={(item) => (
                    <>
                        <Badge variant="secondary" className="text-xs">
                            必需 {item.required_slots?.length ?? 0}
                        </Badge>
                        <span className="text-xs text-slate-400">
                            充分阈值 {item.sufficient_threshold}
                        </span>
                    </>
                )}
                renderDetail={({ item, isCreating, onSave, onCancel, onChange }) => (
                    <div className="space-y-4">
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">配置标识</label>
                            <Input
                                value={item?.profile_key ?? ""}
                                onChange={(e) => onChange("profile_key", e.target.value)}
                                placeholder="例如：product_overview"
                                className="h-10"
                            />
                        </div>
                        <SlotEditor
                            label="必需槽位"
                            description="必须覆盖的信息槽位名称"
                            slots={item?.required_slots ?? []}
                            onChange={(v) => onChange("required_slots", v)}
                            placeholder="输入槽位名称后按 Enter 添加"
                        />
                        <SlotEditor
                            label="可选槽位"
                            description="加分但非必需的信息槽位"
                            slots={item?.optional_slots ?? []}
                            onChange={(v) => onChange("optional_slots", v)}
                            placeholder="输入槽位名称后按 Enter 添加"
                        />
                        <NumberField
                            label="充分判定阈值"
                            description="整体覆盖率超过此值时判定为「证据充分」"
                            value={item?.sufficient_threshold ?? 0.66}
                            onChange={(v) => onChange("sufficient_threshold", v)}
                            min={0}
                            max={1}
                            step={0.05}
                        />
                        <NumberField
                            label="部分覆盖阈值"
                            description="必需槽位覆盖率超过此值时判定为「部分覆盖」"
                            value={item?.partial_threshold ?? 0.5}
                            onChange={(v) => onChange("partial_threshold", v)}
                            min={0}
                            max={1}
                            step={0.05}
                        />
                        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <div>
                                <label className="block text-sm font-medium text-slate-700">启用</label>
                                <p className="text-xs text-slate-500">禁用后此可回答性配置不会参与判定</p>
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
                                <Button type="button" className="rounded-full" onClick={() => void onSave(item as Partial<AdminKnowledgeAnswerabilityProfile>)}>保存</Button>
                            </div>
                        </div>
                    </div>
                )}
                onCreateNew={() => ({
                    id: "",
                    config_version_id: versionId,
                    profile_key: "",
                    required_slots: [],
                    optional_slots: [],
                    sufficient_threshold: 0.66,
                    partial_threshold: 0.5,
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
                description={`确定要删除可回答性配置「${deleteTarget?.profile_key ?? ""}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={() => { if (deleteTarget) void handleDelete(deleteTarget.id); }}
                isLoading={deleting}
            />
        </>
    );
}
