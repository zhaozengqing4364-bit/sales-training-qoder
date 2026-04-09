"use client";

import { useState, useCallback, useEffect } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { AdminKnowledgeRankingProfile } from "@/lib/api/types";
import { ProfileListDetail } from "../shared/profile-list-detail";
import { NumberField } from "../shared/number-field";
import { WeightEditor } from "../shared/weight-editor";

interface RankingProfilesTabProps {
    versionId: string;
}

export function RankingProfilesTab({ versionId }: RankingProfilesTabProps) {
    const toast = useToast();
    const [items, setItems] = useState<AdminKnowledgeRankingProfile[]>([]);
    const [loading, setLoading] = useState(true);
    const [deleteTarget, setDeleteTarget] = useState<AdminKnowledgeRankingProfile | null>(null);
    const [deleting, setDeleting] = useState(false);

    const reloadItems = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.admin.getKnowledgeRankingProfiles(versionId);
            setItems(data);
        } catch (err) {
            toast.error(`加载排序配置失败：${getApiErrorMessage(err)}`);
        } finally {
            setLoading(false);
        }
    }, [versionId, toast]);

    useEffect(() => {
        void reloadItems();
    }, [reloadItems]);

    const handleSave = useCallback(
        async (data: Partial<AdminKnowledgeRankingProfile>, isCreating: boolean) => {
            if (isCreating) {
                await api.admin.createKnowledgeRankingProfile(versionId, {
                    profile_key: data.profile_key ?? "",
                    title_exact_boost: data.title_exact_boost ?? 0.25,
                    entity_match_boost: data.entity_match_boost ?? 0.2,
                    doc_type_weights: data.doc_type_weights ?? {},
                    section_weights: data.section_weights ?? {},
                    min_pass_score: data.min_pass_score ?? 0.45,
                    min_pass_score_keyword: data.min_pass_score_keyword ?? 0.35,
                    base_weight: data.base_weight ?? 0.5,
                    coverage_weight: data.coverage_weight ?? 0.2,
                    phrase_bonus: data.phrase_bonus ?? 0.15,
                    title_bonus_max: data.title_bonus_max ?? 0.1,
                    ratio_bonus_max: data.ratio_bonus_max ?? 0.05,
                    cross_encoder_weight: data.cross_encoder_weight ?? 0.0,
                    diversity_penalty: data.diversity_penalty ?? 0.12,
                    enabled: data.enabled ?? true,
                });
                toast.success("排序配置已创建");
            } else {
                await api.admin.updateKnowledgeRankingProfile(versionId, data.id!, {
                    profile_key: data.profile_key,
                    title_exact_boost: data.title_exact_boost,
                    entity_match_boost: data.entity_match_boost,
                    doc_type_weights: data.doc_type_weights,
                    section_weights: data.section_weights,
                    min_pass_score: data.min_pass_score,
                    min_pass_score_keyword: data.min_pass_score_keyword,
                    enabled: data.enabled,
                });
                toast.success("排序配置已更新");
            }
        },
        [versionId, toast],
    );

    const handleDelete = useCallback(
        async (id: string) => {
            setDeleting(true);
            try {
                await api.admin.deleteKnowledgeRankingProfile(versionId, id);
                toast.success("排序配置已删除");
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
        async (item: AdminKnowledgeRankingProfile, enabled: boolean) => {
            try {
                await api.admin.updateKnowledgeRankingProfile(versionId, item.id, { enabled });
                await reloadItems();
            } catch (err) {
                toast.error(`更新失败：${getApiErrorMessage(err)}`);
            }
        },
        [versionId, toast, reloadItems],
    );

    return (
        <>
            <ProfileListDetail<AdminKnowledgeRankingProfile>
                items={items}
                loading={loading}
                searchPlaceholder="搜索配置标识..."
                newItemLabel="新增排序配置"
                renderItemLabel={(item) => item.profile_key || "未命名"}
                renderItemMeta={(item) => (
                    <>
                        <span className="text-xs text-slate-400">标题+{item.title_exact_boost}</span>
                        <span className="text-xs text-slate-400">实体+{item.entity_match_boost}</span>
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
                        <NumberField
                            label="标题精确匹配加成"
                            description="查询关键词出现在文档标题时的分数加成"
                            value={item?.title_exact_boost ?? 0.25}
                            onChange={(v) => onChange("title_exact_boost", v)}
                            min={0}
                            max={2}
                            step={0.05}
                        />
                        <NumberField
                            label="实体匹配加成"
                            description="解析出的实体出现在标题或内容时的分数加成"
                            value={item?.entity_match_boost ?? 0.2}
                            onChange={(v) => onChange("entity_match_boost", v)}
                            min={0}
                            max={2}
                            step={0.05}
                        />
                        <NumberField
                            label="最低通过分数（向量检索）"
                            description="向量检索模式下，低于此分数的结果将被过滤"
                            value={item?.min_pass_score ?? 0.45}
                            onChange={(v) => onChange("min_pass_score", v)}
                            min={0}
                            max={1}
                            step={0.05}
                        />
                        <NumberField
                            label="最低通过分数（关键词检索）"
                            description="关键词回退模式下，低于此分数的结果将被过滤"
                            value={item?.min_pass_score_keyword ?? 0.35}
                            onChange={(v) => onChange("min_pass_score_keyword", v)}
                            min={0}
                            max={1}
                            step={0.05}
                        />
                        <WeightEditor
                            label="文档类型权重"
                            description="不同文档类型的额外加成"
                            weights={item?.doc_type_weights ?? {}}
                            onChange={(v) => onChange("doc_type_weights", v)}
                            suggestedKeys={["product", "faq", "pricing", "comparison", "coach"]}
                            keyPlaceholder="文档类型"
                        />
                        <WeightEditor
                            label="章节权重"
                            description="不同章节的额外加成"
                            weights={item?.section_weights ?? {}}
                            onChange={(v) => onChange("section_weights", v)}
                            suggestedKeys={["overview", "pricing", "guidance", "comparison"]}
                            keyPlaceholder="章节名称"
                        />

                        {/* ── 统一评分权重 ── */}
                        <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4 space-y-4">
                            <h4 className="text-sm font-semibold text-slate-700">统一评分权重</h4>
                            <p className="text-xs text-slate-500">
                                控制检索管线的最终排序分数计算。修改后需重新触发检索才能生效。
                            </p>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <NumberField
                                    label="基础分权重 (base_weight)"
                                    description="向量/关键词基础分数的权重"
                                    value={item?.base_weight ?? 0.5}
                                    onChange={(v) => onChange("base_weight", v)}
                                    min={0}
                                    max={1}
                                    step={0.05}
                                />
                                <NumberField
                                    label="覆盖率权重 (coverage_weight)"
                                    description="查询词覆盖率加成的权重"
                                    value={item?.coverage_weight ?? 0.2}
                                    onChange={(v) => onChange("coverage_weight", v)}
                                    min={0}
                                    max={1}
                                    step={0.05}
                                />
                                <NumberField
                                    label="短语匹配加成 (phrase_bonus)"
                                    description="查询词完整出现在内容时的加成"
                                    value={item?.phrase_bonus ?? 0.15}
                                    onChange={(v) => onChange("phrase_bonus", v)}
                                    min={0}
                                    max={1}
                                    step={0.05}
                                />
                                <NumberField
                                    label="标题词加成上限 (title_bonus_max)"
                                    description="标题中匹配查询词的最大加成"
                                    value={item?.title_bonus_max ?? 0.1}
                                    onChange={(v) => onChange("title_bonus_max", v)}
                                    min={0}
                                    max={1}
                                    step={0.05}
                                />
                                <NumberField
                                    label="比率加成上限 (ratio_bonus_max)"
                                    description="SequenceMatcher 比率加成的最大值"
                                    value={item?.ratio_bonus_max ?? 0.05}
                                    onChange={(v) => onChange("ratio_bonus_max", v)}
                                    min={0}
                                    max={1}
                                    step={0.05}
                                />
                                <NumberField
                                    label="Cross-Encoder 权重 (cross_encoder_weight)"
                                    description="Cross-Encoder 重排序分数的权重（0 = 禁用）"
                                    value={item?.cross_encoder_weight ?? 0.0}
                                    onChange={(v) => onChange("cross_encoder_weight", v)}
                                    min={0}
                                    max={1}
                                    step={0.05}
                                />
                                <NumberField
                                    label="多样性惩罚 (diversity_penalty)"
                                    description="相同标题文档重复出现时的惩罚系数"
                                    value={item?.diversity_penalty ?? 0.12}
                                    onChange={(v) => onChange("diversity_penalty", v)}
                                    min={0}
                                    max={1}
                                    step={0.05}
                                />
                            </div>
                        </div>

                        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <div>
                                <label className="block text-sm font-medium text-slate-700">启用</label>
                                <p className="text-xs text-slate-500">禁用后此排序配置不会参与检索排序</p>
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
                                <Button type="button" className="rounded-full" onClick={() => void onSave(item as Partial<AdminKnowledgeRankingProfile>)}>保存</Button>
                            </div>
                        </div>
                    </div>
                )}
                onCreateNew={() => ({
                    id: "",
                    config_version_id: versionId,
                    profile_key: "",
                    title_exact_boost: 0.25,
                    entity_match_boost: 0.2,
                    doc_type_weights: {},
                    section_weights: {},
                    min_pass_score: 0.45,
                    min_pass_score_keyword: 0.35,
                    base_weight: 0.5,
                    coverage_weight: 0.2,
                    phrase_bonus: 0.15,
                    title_bonus_max: 0.1,
                    ratio_bonus_max: 0.05,
                    cross_encoder_weight: 0.0,
                    diversity_penalty: 0.12,
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
                description={`确定要删除排序配置「${deleteTarget?.profile_key ?? ""}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={() => { if (deleteTarget) void handleDelete(deleteTarget.id); }}
                isLoading={deleting}
            />
        </>
    );
}
