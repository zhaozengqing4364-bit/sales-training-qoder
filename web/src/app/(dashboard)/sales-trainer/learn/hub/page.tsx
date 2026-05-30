"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, BookOpen } from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerUnit } from "@/lib/api/types";
import { buildHubChapterEntries, buildHubLearnHref } from "@/lib/sales-trainer/hub-chapters";
import { NEW_SELLER_MODULES_PATH_KEY } from "@/lib/sales-trainer/module-path";
import { readLearnerConfig } from "@/lib/sales-trainer/learner-presenter";

const HUB_UNIT_NAME = "模块二：拜访前商务";

export default function SalesTrainerLearnHubPage() {
    const [units, setUnits] = useState<SalesTrainerUnit[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function load() {
            setIsLoading(true);
            setError(null);
            try {
                const response = await api.salesTrainer.listUnits();
                setUnits(response.items);
            } catch (loadError) {
                setUnits([]);
                setError(getApiErrorMessage(loadError));
            } finally {
                setIsLoading(false);
            }
        }
        void load();
    }, []);

    const hubUnit = useMemo(
        () => units.find((unit) => unit.name === HUB_UNIT_NAME),
        [units],
    );

    const chapters = useMemo(() => buildHubChapterEntries(units), [units]);

    const contentHint = useMemo(() => {
        const learner = readLearnerConfig(hubUnit?.config);
        return learner?.learning_content_id ?? null;
    }, [hubUnit]);

    return (
        <div className="space-y-6 pb-20">
            <Link
                href="/sales-trainer"
                className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
            >
                <ArrowLeft className="h-4 w-4" />
                返回销售训练
            </Link>

            <div>
                <h1 className="text-3xl font-black tracking-tight text-slate-900">拜访前商务</h1>
                <p className="mt-1 text-sm text-slate-500">
                    COO 谈市场十五讲：章节可任意顺序阅读，无强制解锁。完成阅读后可进入对应章节测验（若已发布）。
                </p>
            </div>

            {error ? (
                <GlassCard className="space-y-3 p-4">
                    <p className="text-sm font-medium text-red-700">加载失败：{error}</p>
                    <Button
                        variant="outline"
                        className="rounded-full"
                        onClick={() => {
                            setIsLoading(true);
                            void api.salesTrainer.listUnits()
                                .then((response) => {
                                    setUnits(response.items);
                                    setError(null);
                                })
                                .catch((loadError) => {
                                    setUnits([]);
                                    setError(getApiErrorMessage(loadError));
                                })
                                .finally(() => setIsLoading(false));
                        }}
                    >
                        重试
                    </Button>
                </GlassCard>
            ) : null}

            {isLoading ? (
                <div className="h-48 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
            ) : chapters.length === 0 ? (
                <GlassCard className="space-y-3 p-6">
                    <p className="text-sm text-slate-600">
                        尚未找到带章节配置的 COO 测验单元。请先运行
                        {" "}
                        <code className="text-xs">seed_coo_path_extension.py</code>
                        {" "}
                        发布十五讲章节，并确认
                        {" "}
                        <code className="text-xs">{NEW_SELLER_MODULES_PATH_KEY}</code>
                        {" "}
                        种子已执行。
                    </p>
                    {contentHint ? (
                        <p className="text-xs text-slate-500">讲义 ID：{contentHint}</p>
                    ) : null}
                </GlassCard>
            ) : (
                <div className="grid gap-3 md:grid-cols-2">
                    {chapters.map((chapter) => (
                        <GlassCard key={chapter.unitId} className="flex flex-col gap-3 p-5">
                            <div className="flex items-start gap-3">
                                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-700">
                                    {chapter.chapterOrderIndex}
                                </span>
                                <div>
                                    <h2 className="font-bold text-slate-900">{chapter.levelTitle}</h2>
                                    <p className="mt-1 text-sm text-slate-500">{chapter.unitName}</p>
                                </div>
                            </div>
                            <Link href={buildHubLearnHref(chapter.unitId)}>
                                <Button variant="outline" className="w-full rounded-full">
                                    <BookOpen className="mr-2 h-4 w-4" />
                                    阅读本章
                                </Button>
                            </Link>
                        </GlassCard>
                    ))}
                </div>
            )}
        </div>
    );
}
