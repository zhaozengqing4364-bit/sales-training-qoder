"use client";

import { FileSearch } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import type { PracticeTemplateRecord } from "@/lib/api/types";

import {
    assetCardClassName,
    ContentAssetStatusGuide,
} from "./content-asset-status-guide";

function statusVariant(status: string): "green" | "orange" | "gray" {
    if (status === "published") return "green";
    if (status === "draft") return "orange";
    return "gray";
}

function statusLabel(status: string): string {
    return { draft: "草稿", published: "已发布", archived: "已归档" }[status] ?? "状态待确认";
}

function modeLabel(mode: string): string {
    return {
        learning: "引导学习",
        expert_qa: "专家问答",
        examiner: "考核对练",
        customer_roleplay: "客户实战对练",
        mixed_path: "组合训练",
    }[mode] ?? "自定义训练";
}

function scenarioLabel(scenarioType: string): string {
    return { sales: "销售沟通", presentation: "演示讲解" }[scenarioType] ?? "自定义场景";
}

function bindingLabel(item: PracticeTemplateRecord): string | null {
    if (item.case_item_id && item.role_profile_id) return "客户案例和角色档案已绑定";
    if (item.case_item_id) return "客户案例已绑定，角色档案待补充";
    if (item.role_profile_id) return "角色档案已绑定，客户案例待补充";
    return null;
}

interface TemplateListProps {
    items: PracticeTemplateRecord[];
    busyTemplateId: string | null;
    previewLoadingTemplateId: string | null;
    onEdit: (template: PracticeTemplateRecord) => void;
    onPreview: (template: PracticeTemplateRecord) => void;
    onPublish: (template: PracticeTemplateRecord) => void;
    onArchive: (template: PracticeTemplateRecord) => void;
}

export function TemplateList({
    items,
    busyTemplateId,
    previewLoadingTemplateId,
    onEdit,
    onPreview,
    onPublish,
    onArchive,
}: TemplateListProps) {
    return (
        <GlassCard className="space-y-4 p-6">
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-black text-slate-900">模板列表</h2>
                <Badge variant="gray">{items.length} 个模板</Badge>
            </div>
            <div className="grid gap-3">
                {items.map((item) => (
                    <div key={item.template_id} className={assetCardClassName(item.status)}>
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                            <div className="space-y-2">
                                <div className="flex flex-wrap items-center gap-2">
                                    <h3 className="font-bold text-slate-900">{item.name}</h3>
                                    <Badge variant={statusVariant(item.status)}>{statusLabel(item.status)} · v{item.version}</Badge>
                                </div>
                                <ContentAssetStatusGuide status={item.status} compact />
                                <p className="text-sm text-slate-600">{modeLabel(item.mode)} · {scenarioLabel(item.scenario_type)}</p>
                                {bindingLabel(item) ? <p className="text-xs text-slate-500">{bindingLabel(item)}</p> : null}
                                {item.description ? <p className="text-sm text-slate-600">{item.description}</p> : null}
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <Button
                                    variant="outline"
                                    onClick={() => onPreview(item)}
                                    disabled={busyTemplateId !== null || previewLoadingTemplateId !== null}
                                >
                                    <FileSearch className="mr-2 h-4 w-4" />
                                    {previewLoadingTemplateId === item.template_id ? "预览中..." : "预览角色档案"}
                                </Button>
                                {item.status === "draft" ? (
                                    <Button variant="outline" onClick={() => onEdit(item)}>编辑模板</Button>
                                ) : null}
                                <Button
                                    onClick={() => onPublish(item)}
                                    disabled={item.status === "published" || busyTemplateId !== null}
                                >
                                    {busyTemplateId === item.template_id ? "发布中..." : "发布模板"}
                                </Button>
                                {item.status !== "archived" && (
                                    <Button
                                        variant="outline"
                                        onClick={() => onArchive(item)}
                                        disabled={busyTemplateId !== null}
                                    >
                                        {busyTemplateId === item.template_id ? "归档中..." : "归档模板"}
                                    </Button>
                                )}
                            </div>
                        </div>
                    </div>
                ))}
                {items.length === 0 && <p className="text-sm text-slate-500">暂无课程训练模板。</p>}
            </div>
        </GlassCard>
    );
}
