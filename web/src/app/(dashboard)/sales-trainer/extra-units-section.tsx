"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import type { SalesTrainerUnit } from "@/lib/api/types";
import {
    getUnitTypeLabel,
    isLikelyInternalUnit,
    sortExtraUnits,
} from "@/lib/sales-trainer/learner-presenter";

interface ExtraUnitsSectionProps {
    units: SalesTrainerUnit[];
}

export function ExtraUnitsSection({ units }: ExtraUnitsSectionProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const sortedUnits = sortExtraUnits(units);

    if (sortedUnits.length === 0) {
        return null;
    }

    return (
        <section className="space-y-3">
            <button
                type="button"
                onClick={() => setIsExpanded((current) => !current)}
                className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left"
            >
                <span className="text-base font-bold text-slate-900">更多练习（{sortedUnits.length}）</span>
                {isExpanded ? (
                    <ChevronUp className="h-5 w-5 text-slate-500" />
                ) : (
                    <ChevronDown className="h-5 w-5 text-slate-500" />
                )}
            </button>

            {isExpanded ? (
                <div className="grid gap-4 md:grid-cols-2">
                    {sortedUnits.map((unit) => {
                        const isInternal = isLikelyInternalUnit(unit);
                        const href = unit.unit_type === "quiz"
                            ? `/sales-trainer/quiz/${unit.unit_id}`
                            : `/sales-trainer/audio/${unit.unit_id}`;
                        const actionLabel = unit.unit_type === "quiz" ? "开始做题" : "上传语音作业";

                        return (
                            <GlassCard key={unit.unit_id} className="space-y-4 p-6">
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <h3 className="text-lg font-bold text-slate-900">{unit.name}</h3>
                                        <p className="mt-1 text-sm text-slate-500">
                                            {unit.description || "未填写训练说明。"}
                                        </p>
                                    </div>
                                    <div className="flex flex-col items-end gap-2">
                                        <Badge className="bg-slate-100 text-slate-700">{getUnitTypeLabel(unit.unit_type)}</Badge>
                                        {isInternal ? (
                                            <Badge className="bg-amber-100 text-amber-700">内测</Badge>
                                        ) : null}
                                    </div>
                                </div>
                                {unit.unit_type === "quiz" ? (
                                    <p className="text-sm text-slate-500">共 {unit.questions.length} 道题</p>
                                ) : (
                                    <p className="text-sm text-slate-500">上传语音后由系统转写并评分。</p>
                                )}
                                <Link href={href}>
                                    <Button variant="outline" className="rounded-full">{actionLabel}</Button>
                                </Link>
                            </GlassCard>
                        );
                    })}
                </div>
            ) : null}
        </section>
    );
}
