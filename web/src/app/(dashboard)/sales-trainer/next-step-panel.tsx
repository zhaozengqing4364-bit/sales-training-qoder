"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerGoalNextRecommendation, SalesTrainerPath } from "@/lib/api/types";

function findRecommendation(
    paths: SalesTrainerPath[],
    unitId: string,
): SalesTrainerGoalNextRecommendation | null {
    const currentPath = paths.find((path) =>
        path.levels.some((level) => level.unit_id === unitId),
    );
    return currentPath?.goal_context.next_recommendation ?? null;
}

interface SalesTrainerNextStepPanelProps {
    unitId: string;
}

export function SalesTrainerNextStepPanel({ unitId }: SalesTrainerNextStepPanelProps) {
    const [recommendation, setRecommendation] = useState<SalesTrainerGoalNextRecommendation | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let isMounted = true;
        async function loadRecommendation() {
            setIsLoading(true);
            setError(null);
            try {
                const response = await api.salesTrainer.listPaths();
                if (isMounted) {
                    setRecommendation(findRecommendation(response.items, unitId));
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
                <h2 className="mt-2 text-lg font-bold text-slate-900">回到销售训练首页</h2>
                <p className="mt-1 text-sm text-slate-500">
                    首页会根据当前训练路径继续展示可练关卡和复盘入口。
                </p>
                <Link className="mt-4 inline-flex" href="/sales-trainer">
                    <Button className="rounded-full bg-slate-900 text-white">
                        查看训练路径
                    </Button>
                </Link>
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
            <Link className="inline-flex" href={recommendation.target_path}>
                <Button className="rounded-full bg-slate-900 text-white">
                    {recommendation.action_label}
                    <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
            </Link>
        </GlassCard>
    );
}
