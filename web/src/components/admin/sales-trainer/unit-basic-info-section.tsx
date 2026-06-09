"use client";

import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import type { SalesTrainerUnitType } from "@/lib/api/types";

interface UnitBasicInfoSectionProps {
    readonly canEdit: boolean;
    readonly description: string;
    readonly isEditMode: boolean;
    readonly isSubmitting: boolean;
    readonly name: string;
    readonly setDescription: (value: string) => void;
    readonly setName: (value: string) => void;
    readonly setUnitType: (value: SalesTrainerUnitType) => void;
    readonly unitType: SalesTrainerUnitType;
}

export function UnitBasicInfoSection({
    canEdit,
    description,
    isEditMode,
    isSubmitting,
    name,
    setDescription,
    setName,
    setUnitType,
    unitType,
}: UnitBasicInfoSectionProps) {
    return (
        <GlassCard className="space-y-4 p-6">
            <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-unit-name">训练单元名称</label>
                    <Input id="sales-trainer-unit-name" value={name} onChange={(event) => setName(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="例如：首轮客户需求问答" />
                </div>
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-unit-type">训练类型</label>
                    <select
                        id="sales-trainer-unit-type"
                        value={unitType}
                        onChange={(event) => setUnitType(event.target.value as SalesTrainerUnitType)}
                        disabled={isSubmitting || !canEdit || isEditMode}
                        className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                    >
                        <option value="quiz">做题训练</option>
                        <option value="audio_scoring">录音评分</option>
                    </select>
                </div>
            </div>
            <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-unit-description">描述</label>
                <textarea
                    id="sales-trainer-unit-description"
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    disabled={isSubmitting || !canEdit}
                    rows={4}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                    placeholder="说明这个训练单元适合什么场景。"
                />
            </div>
        </GlassCard>
    );
}
