"use client";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { TRAINING_PURPOSE_OPTIONS } from "@/lib/sales-trainer/admin-display";
import type { SalesTrainerMaterialCreateRequest } from "@/lib/api/types";

import {
    MATERIAL_TYPE_OPTIONS,
    toMaterialType,
} from "./material-page-model";

interface MaterialCreateCardProps {
    readonly isSubmitting: boolean;
    readonly materialDraft: SalesTrainerMaterialCreateRequest;
    readonly onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
    readonly setMaterialDraft: React.Dispatch<React.SetStateAction<SalesTrainerMaterialCreateRequest>>;
}

export function MaterialCreateCard({
    isSubmitting,
    materialDraft,
    onSubmit,
    setMaterialDraft,
}: MaterialCreateCardProps) {
    return (
        <GlassCard className="space-y-4 p-6">
            <div>
                <h2 className="text-lg font-bold text-slate-900">新建材料主档</h2>
                <p className="mt-1 text-sm text-slate-500">主档代表长期材料，文件变更通过版本管理。</p>
            </div>
            <form className="space-y-4" onSubmit={onSubmit}>
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="material-key">材料标识</label>
                    <Input
                        id="material-key"
                        value={materialDraft.material_key}
                        onChange={(event) => setMaterialDraft((current) => ({ ...current, material_key: event.target.value }))}
                        placeholder="company_master_deck"
                        disabled={isSubmitting}
                    />
                </div>
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="material-name">材料名称</label>
                    <Input
                        id="material-name"
                        value={materialDraft.name}
                        onChange={(event) => setMaterialDraft((current) => ({ ...current, name: event.target.value }))}
                        placeholder="公司主胶片"
                        disabled={isSubmitting}
                    />
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="material-type">材料类型</label>
                        <select
                            id="material-type"
                            value={materialDraft.material_type}
                            onChange={(event) => setMaterialDraft((current) => ({
                                ...current,
                                material_type: toMaterialType(event.target.value),
                            }))}
                            disabled={isSubmitting}
                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                        >
                            {MATERIAL_TYPE_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                        </select>
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="material-purpose">用途</label>
                        <select
                            id="material-purpose"
                            value={materialDraft.purpose}
                            onChange={(event) => setMaterialDraft((current) => ({ ...current, purpose: event.target.value }))}
                            disabled={isSubmitting}
                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                        >
                            {TRAINING_PURPOSE_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                        </select>
                    </div>
                </div>
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="material-description">说明</label>
                    <textarea
                        id="material-description"
                        value={materialDraft.description ?? ""}
                        onChange={(event) => setMaterialDraft((current) => ({ ...current, description: event.target.value }))}
                        disabled={isSubmitting}
                        rows={3}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                    />
                </div>
                <Button type="submit" disabled={isSubmitting} className="w-full rounded-full bg-slate-900 text-white">
                    创建材料
                </Button>
            </form>
        </GlassCard>
    );
}
