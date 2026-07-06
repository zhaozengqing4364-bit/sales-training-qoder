"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { TrainingJourneyModuleProgress, TrainingJourneyResponse } from "@/lib/api/types";

interface JourneyNextStepRecommendation {
    title: string;
    reason: string;
    action_label: string;
    target_path: string;
}

function moduleHasAction(module: TrainingJourneyModuleProgress): boolean {
    const action = module.next_action;
    return Boolean(action && !action.disabled && action.target_path);
}

function moduleNeedsAttention(module: TrainingJourneyModuleProgress): boolean {
    return module.stage !== "passed" && module.stage !== "disabled" && module.stage !== "archived";
}

function findRecommendation(journey: TrainingJourneyResponse): JourneyNextStepRecommendation | null {
    const sortedModules = [...journey.modules].sort((left, right) => left.order_index - right.order_index);
    const nextModule = sortedModules.find((item) => moduleNeedsAttention(item) && moduleHasAction(item))
        ?? sortedModules.find(moduleHasAction);
    const action = nextModule?.next_action;
    if (!nextModule || !action?.target_path) {
        return null;
    }
    return {
        title: nextModule.display_name,
        reason: action.disabled_reason || `根据当前训练路径，继续完成“${nextModule.display_name}”。`,
        action_label: action.label,
        target_path: action.target_path,
    };
}

interface SalesTrainerNextStepPanelProps {
    unitId: string;
}

export function SalesTrainerNextStepPanel({ unitId }: SalesTrainerNextStepPanelProps) {
    const [recommendation, setRecommendation] = useState<JourneyNextStepRecommendation | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let isMounted = true;
        async function loadRecommendation() {
            setIsLoading(true);
            setError(null);
            try {
                const response = await api.salesTrainer.getJourney();
                if (isMounted) {
                    setRecommendation(findRecommendation(response));
                }
            } catch (loadError) {
                if (isMounted) {
                    setRecommendation(null);
                    setError(getApiErrorMessage(loadError));
                }
            } finally {
                if (isMounted) {
                    setIsLoading(false);
                }
            }
        }

        void loadRecommendation();
        return () => {
            isMounted = false;
        };
    }, [unitId]);

    if (isLoading) {
        return (
            <GlassCard className="p-5">
                <div className="flex items-center gap-2 text-sm text-slate-500">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    正在生成下一步建议...
                </div>
            </GlassCard>
        );
    }

    if (error) {
        return (
            <GlassCard className="p-5">
                <p className="text-sm text-slate-500">下一步建议暂时不可用：{error}</p>
            </GlassCard>
        );
    }

    if (!recommendation) {
        return (
            <GlassCard className="p-5">
                <p className="text-xs font-semibold text-slate-500">练完下一步</p>
                <h2 className="mt-2 text-lg font-bold text-slate-900">回到新人训练路径首页</h2>
                <p className="mt-1 text-sm text-slate-500">
                    首页会根据当前训练路径继续展示可练关卡和复盘入口。
                </p>
                <Button asChild className="mt-4 rounded-full bg-slate-900 text-white">
                    <Link href="/sales-trainer">
                        查看训练路径
                    </Link>
                </Button>
            </GlassCard>
        );
    }

    return (
        <GlassCard className="space-y-4 p-5">
            <div>
                <p className="text-xs font-semibold text-slate-500">练完下一步</p>
                <h2 className="mt-2 text-lg font-bold text-slate-900">{recommendation.title}</h2>
                <p className="mt-1 text-sm leading-6 text-slate-600">{recommendation.reason}</p>
            </div>
            <Button asChild className="rounded-full bg-slate-900 text-white">
                <Link href={recommendation.target_path}>
                    {recommendation.action_label}
                    <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
            </Button>
        </GlassCard>
    );
}
