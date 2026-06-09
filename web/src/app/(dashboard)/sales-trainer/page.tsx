"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, FileAudio, FileQuestion, RefreshCw } from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerPath, SalesTrainerUnit } from "@/lib/api/types";
import {
    collectPathUnitIds,
    getUnitTypeLabel,
    partitionUnits,
} from "@/lib/sales-trainer/learner-presenter";

import { SalesTrainerModuleGrid } from "@/components/sales-trainer/sales-trainer-module-grid";
import { SalesTrainerModuleMissionPanel } from "@/components/sales-trainer/sales-trainer-module-mission-panel";
import {
    filterPathsForHome,
    isThreeModulePath,
    NEWCOMER_TRAINING_PATH_KEY,
} from "@/lib/sales-trainer/module-path";

import { ExtraUnitsSection } from "./extra-units-section";
import { PathLevelTimeline } from "./path-level-timeline";
import { PathMissionPanel } from "./path-mission-panel";

function CatalogSection({
    quizUnits,
    audioUnits,
}: {
    quizUnits: SalesTrainerUnit[];
    audioUnits: SalesTrainerUnit[];
}) {
    return (
        <>
            <section className="space-y-4">
                <div className="flex items-center gap-2">
                    <FileQuestion className="h-5 w-5 text-slate-700" />
                    <h2 className="text-xl font-bold text-slate-900">做题训练</h2>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                    {quizUnits.map((unit) => (
                        <GlassCard key={unit.unit_id} className="space-y-4 p-6">
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <h3 className="text-lg font-bold text-slate-900">{unit.name}</h3>
                                    <p className="mt-1 text-sm text-slate-500">{unit.description || "未填写训练说明。"}</p>
                                </div>
                                <Badge className="bg-slate-100 text-slate-700">{getUnitTypeLabel(unit.unit_type)}</Badge>
                            </div>
                            <p className="text-sm text-slate-500">
                                共 {unit.questions.length} 道题
                            </p>
                            <Button asChild className="rounded-full bg-slate-900 text-white">
                                <Link href={`/sales-trainer/quiz/${unit.unit_id}`}>开始做题</Link>
                            </Button>
                        </GlassCard>
                    ))}
                </div>
            </section>

            <section className="space-y-4">
                <div className="flex items-center gap-2">
                    <FileAudio className="h-5 w-5 text-slate-700" />
                    <h2 className="text-xl font-bold text-slate-900">语音作业</h2>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                    {audioUnits.map((unit) => (
                        <GlassCard key={unit.unit_id} className="space-y-4 p-6">
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <h3 className="text-lg font-bold text-slate-900">{unit.name}</h3>
                                    <p className="mt-1 text-sm text-slate-500">{unit.description || "未填写训练说明。"}</p>
                                </div>
                                <Badge className="bg-slate-100 text-slate-700">{getUnitTypeLabel(unit.unit_type)}</Badge>
                            </div>
                            <p className="text-sm text-slate-500">
                                上传语音后由系统转写并评分。
                            </p>
                            <Button asChild className="rounded-full bg-slate-900 text-white">
                                <Link href={`/sales-trainer/audio/${unit.unit_id}`}>上传语音作业</Link>
                            </Button>
                        </GlassCard>
                    ))}
                </div>
            </section>
        </>
    );
}

function displayPathTitle(path: SalesTrainerPath): string {
    if (path.title.includes("新人销售")) {
        return "新人训练路径";
    }
    return path.title;
}

export default function SalesTrainerPage() {
    const [units, setUnits] = useState<SalesTrainerUnit[]>([]);
    const [paths, setPaths] = useState<SalesTrainerPath[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    async function loadUnits() {
        setIsLoading(true);
        setError(null);
        try {
            const [unitResponse, pathResponse] = await Promise.all([
                api.salesTrainer.listUnits(),
                api.salesTrainer.listPaths(),
            ]);
            setUnits(unitResponse.items);
            setPaths(pathResponse.items);
        } catch (loadError) {
            setUnits([]);
            setPaths([]);
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }

    useEffect(() => {
        void loadUnits();
    }, []);

    const quizUnits = useMemo(
        () => units.filter((unit) => unit.unit_type === "quiz"),
        [units],
    );
    const audioUnits = useMemo(
        () => units.filter((unit) => unit.unit_type === "audio_scoring"),
        [units],
    );
    const unitsById = useMemo(
        () => new Map(units.map((unit) => [unit.unit_id, unit])),
        [units],
    );
    const pathUnitIds = useMemo(() => collectPathUnitIds(paths), [paths]);
    const { extraUnits } = useMemo(
        () => partitionUnits(units, pathUnitIds),
        [units, pathUnitIds],
    );
    const displayPaths = useMemo(() => filterPathsForHome(paths), [paths]);
    const hasPaths = displayPaths.length > 0;
    const hasNewcomerPath = displayPaths.some(
        (path) => path.path_key === NEWCOMER_TRAINING_PATH_KEY,
    );

    return (
        <div className="space-y-6 pb-20">
            <div className="space-y-4">
                <Link
                    href="/training"
                    className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
                >
                    <ArrowLeft className="h-4 w-4" />
                    返回训练大厅
                </Link>
                <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                    <div>
                        <h1 className="text-3xl font-black tracking-tight text-slate-900">新人训练路径</h1>
                        <p className="mt-1 text-sm text-slate-500">
                            按后台配置的训练模块完成学习、考试与录音任务；每个模块会显示当前要做什么和下一步去哪里。
                        </p>
                    </div>
                    <Button variant="outline" className="rounded-full" onClick={() => void loadUnits()} disabled={isLoading}>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        刷新
                    </Button>
                </div>
            </div>

            {error ? (
                <GlassCard className="space-y-3 p-4">
                    <p className="text-sm font-medium text-red-700">训练单元加载失败：{error}</p>
                    <Button variant="outline" className="rounded-full" onClick={() => void loadUnits()}>
                        重试
                    </Button>
                </GlassCard>
            ) : null}

            {isLoading ? (
                <div className="grid gap-4 md:grid-cols-2">
                    {Array.from({ length: 4 }).map((_, index) => (
                        <div key={index} className="h-44 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
                    ))}
                </div>
            ) : units.length === 0 ? (
                <EmptyState
                    title="暂无可用新人训练路径"
                    description="当前没有已发布训练模块，请稍后重试或联系管理员发布。"
                    actionLabel="刷新列表"
                    onAction={() => void loadUnits()}
                />
            ) : (
                <div className="space-y-6">
                    {hasPaths ? (
                        <>
                            <section className="space-y-4">
                                {displayPaths.map((path) => (
                                    <GlassCard key={path.path_key} className="space-y-5 p-6">
                                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                            <div>
                                                <Badge className="bg-blue-100 text-blue-700">
                                                    {isThreeModulePath(path) ? "新人训练路径" : "当前目标"}
                                                </Badge>
                                                <h2 className="mt-3 text-2xl font-black text-slate-900">{displayPathTitle(path)}</h2>
                                                <p className="mt-1 text-sm text-slate-500">
                                                    {path.goal_title || "按模块自选完成训练，无强制解锁。"}
                                                </p>
                                            </div>
                                            {!isThreeModulePath(path) ? (
                                                <div className="rounded-lg bg-slate-50 px-4 py-3 text-right">
                                                    <p className="text-xs text-slate-500">闯关进度</p>
                                                    <p className="mt-1 text-2xl font-black text-slate-900">
                                                        {path.completed_levels}/{path.total_levels}
                                                    </p>
                                                </div>
                                            ) : null}
                                        </div>
                                        {isThreeModulePath(path) ? (
                                            <>
                                                <SalesTrainerModuleMissionPanel path={path} unitsById={unitsById} />
                                                <SalesTrainerModuleGrid path={path} unitsById={unitsById} />
                                            </>
                                        ) : (
                                            <>
                                                <PathMissionPanel path={path} unitsById={unitsById} />
                                                <PathLevelTimeline path={path} unitsById={unitsById} />
                                            </>
                                        )}
                                    </GlassCard>
                                ))}
                            </section>
                            {hasNewcomerPath ? null : <ExtraUnitsSection units={extraUnits} />}
                        </>
                    ) : (
                        <CatalogSection quizUnits={quizUnits} audioUnits={audioUnits} />
                    )}
                </div>
            )}
        </div>
    );
}
