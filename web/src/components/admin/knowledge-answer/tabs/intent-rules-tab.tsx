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
import type { AdminKnowledgeIntentRule, AdminKnowledgeQueryProfile } from "@/lib/api/types";
import { ProfileListDetail } from "../shared/profile-list-detail";
import { NumberField } from "../shared/number-field";

const MATCH_TYPE_OPTIONS = [
    { value: "regex", label: "正则匹配" },
    { value: "keyword_contains", label: "关键词包含" },
    { value: "entity_keyword_contains", label: "实体+关键词" },
] as const;

const MATCH_TYPE_LABELS: Record<string, string> = Object.fromEntries(
    MATCH_TYPE_OPTIONS.map((o) => [o.value, o.label]),
);

interface IntentRulesTabProps {
    versionId: string;
}

export function IntentRulesTab({ versionId }: IntentRulesTabProps) {
    const toast = useToast();
    const [items, setItems] = useState<AdminKnowledgeIntentRule[]>([]);
    const [loading, setLoading] = useState(true);
    const [queryProfiles, setQueryProfiles] = useState<AdminKnowledgeQueryProfile[]>([]);
    const [deleteTarget, setDeleteTarget] = useState<AdminKnowledgeIntentRule | null>(null);
    const [deleting, setDeleting] = useState(false);

    const reloadItems = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.admin.getKnowledgeIntentRules(versionId);
            setItems(data);
        } catch (err) {
            toast.error(`加载意图规则失败：${getApiErrorMessage(err)}`);
        } finally {
            setLoading(false);
        }
    }, [versionId, toast]);

    const loadQueryProfiles = useCallback(async () => {
        try {
            const data = await api.admin.getKnowledgeQueryProfiles(versionId);
            setQueryProfiles(data);
        } catch (err) {
            console.error("Failed to load query profiles:", err);
        }
    }, [versionId]);

    useEffect(() => {
        void reloadItems();
        void loadQueryProfiles();
    }, [reloadItems, loadQueryProfiles]);

    const handleSave = useCallback(
        async (data: Partial<AdminKnowledgeIntentRule>, isCreating: boolean) => {
            if (isCreating) {
                await api.admin.createKnowledgeIntentRule(versionId, {
                    intent_key: data.intent_key ?? "",
                    priority: data.priority ?? 10,
                    match_type: data.match_type ?? "keyword_contains",
                    pattern: data.pattern ?? "",
                    profile_key: data.profile_key ?? "",
                    enabled: data.enabled ?? true,
                });
                toast.success("意图规则已创建");
            } else {
                await api.admin.updateKnowledgeIntentRule(versionId, data.id!, {
                    intent_key: data.intent_key,
                    priority: data.priority,
                    match_type: data.match_type,
                    pattern: data.pattern,
                    profile_key: data.profile_key,
                    enabled: data.enabled,
                });
                toast.success("意图规则已更新");
            }
        },
        [versionId, toast],
    );

    const handleDelete = useCallback(
        async (id: string) => {
            setDeleting(true);
            try {
                await api.admin.deleteKnowledgeIntentRule(versionId, id);
                toast.success("意图规则已删除");
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
        async (item: AdminKnowledgeIntentRule, enabled: boolean) => {
            try {
                await api.admin.updateKnowledgeIntentRule(versionId, item.id, { enabled });
                await reloadItems();
            } catch (err) {
                toast.error(`更新失败：${getApiErrorMessage(err)}`);
            }
        },
        [versionId, toast, reloadItems],
    );

    return (
        <>
            <ProfileListDetail<AdminKnowledgeIntentRule>
                items={items}
                loading={loading}
                searchPlaceholder="搜索意图标识..."
                newItemLabel="新增意图规则"
                renderItemLabel={(item) => item.intent_key}
                renderItemMeta={(item) => (
                    <>
                        <Badge variant="secondary" className="text-xs">
                            {MATCH_TYPE_LABELS[item.match_type] ?? item.match_type}
                        </Badge>
                        <span className="text-xs text-slate-400">优先级 {item.priority}</span>
                    </>
                )}
                renderDetail={({ item, isCreating, onSave, onCancel, onChange }) => (
                    <div className="space-y-4">
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">意图标识</label>
                            <Input
                                value={item?.intent_key ?? ""}
                                onChange={(e) => onChange("intent_key", e.target.value)}
                                placeholder="例如：product_inquiry"
                                className="h-10"
                            />
                        </div>
                        <NumberField
                            label="优先级"
                            description="数值越小优先级越高"
                            value={item?.priority ?? 10}
                            onChange={(v) => onChange("priority", v)}
                            min={1}
                            max={100}
                            step={1}
                        />
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">匹配方式</label>
                            <select
                                value={item?.match_type ?? "keyword_contains"}
                                onChange={(e) => onChange("match_type", e.target.value)}
                                className="h-10 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                            >
                                {MATCH_TYPE_OPTIONS.map((opt) => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">匹配模式</label>
                            <textarea
                                value={item?.pattern ?? ""}
                                onChange={(e) => onChange("pattern", e.target.value)}
                                placeholder="关键词用 | 分隔，或输入正则表达式"
                                rows={3}
                                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200 resize-none"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="block text-sm font-medium text-slate-700">关联查询配置</label>
                            <select
                                value={item?.profile_key ?? ""}
                                onChange={(e) => onChange("profile_key", e.target.value)}
                                className="h-10 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                            >
                                <option value="">未关联</option>
                                {queryProfiles.map((p) => (
                                    <option key={p.profile_key} value={p.profile_key}>
                                        {p.profile_key}{p.description ? ` — ${p.description}` : ""}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <div>
                                <label className="block text-sm font-medium text-slate-700">启用</label>
                                <p className="text-xs text-slate-500">禁用后此规则不会参与意图匹配</p>
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
                                <Button type="button" className="rounded-full" onClick={() => void onSave(item as Partial<AdminKnowledgeIntentRule>)}>保存</Button>
                            </div>
                        </div>
                    </div>
                )}
                onCreateNew={() => ({
                    id: "",
                    config_version_id: versionId,
                    intent_key: "",
                    priority: 10,
                    match_type: "keyword_contains",
                    pattern: "",
                    profile_key: "",
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
                description={`确定要删除意图规则「${deleteTarget?.intent_key}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={() => { if (deleteTarget) void handleDelete(deleteTarget.id); }}
                isLoading={deleting}
            />
        </>
    );
}
