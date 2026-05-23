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
                <Badge variant="gray">{items.length} templates</Badge>
            </div>
            <div className="grid gap-3">
                {items.map((item) => (
                    <div key={item.template_id} className={assetCardClassName(item.status)}>
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                            <div className="space-y-2">
                                <div className="flex flex-wrap items-center gap-2">
                                    <h3 className="font-bold text-slate-900">{item.name}</h3>
                                    <Badge variant={statusVariant(item.status)}>{item.status} · v{item.version}</Badge>
                                </div>
                                <ContentAssetStatusGuide status={item.status} compact />
                                <p className="text-sm text-slate-600">{item.mode} · {item.scenario_type}</p>
                                <p className="text-xs text-slate-500">
                                    agent: {item.agent_id} · persona: {item.persona_id} · runtime: {item.runtime_profile_id}
                                </p>
                                {(item.case_item_id || item.role_profile_id) && (
                                    <p className="text-xs text-slate-500">case: {item.case_item_id ?? "未绑定"} · role: {item.role_profile_id ?? "未绑定"}</p>
                                )}
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
