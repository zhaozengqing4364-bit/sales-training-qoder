"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { RefreshCcw } from "lucide-react";

import {
    CooChapterReader,
    CooChapterReaderTerminal,
} from "@/components/sales-trainer/coo-chapter-reader";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { LearnerStudyContent, LearnerStudyProgress, SalesTrainerPath, SalesTrainerUnit } from "@/lib/api/types";
import {
    buildPathChapterEntries,
    decodeReturnTo,
    findAdjacentLearnUnits,
    persistLearnReturn,
    resolveChapterByOrderIndex,
    resolveLearnerContentId,
    validateCooChapterAccess,
} from "@/lib/sales-trainer/coo-learn-navigation";
import { buildHubChapterEntries } from "@/lib/sales-trainer/hub-chapters";
import { findLevelForUnit, readLearnerConfig } from "@/lib/sales-trainer/learner-presenter";

export default function SalesTrainerLearnPage() {
    const params = useParams<{ unitId: string }>();
    const searchParams = useSearchParams();
    const returnTo = decodeReturnTo(searchParams.get("returnTo"));

    const [unit, setUnit] = useState<SalesTrainerUnit | null>(null);
    const [allUnits, setAllUnits] = useState<SalesTrainerUnit[]>([]);
    const [paths, setPaths] = useState<SalesTrainerPath[]>([]);
    const [content, setContent] = useState<LearnerStudyContent | null>(null);
    const [progress, setProgress] = useState<LearnerStudyProgress | null>(null);
    const [accessError, setAccessError] = useState<string | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const loadPage = useCallback(async () => {
        setIsLoading(true);
        setLoadError(null);
        setAccessError(null);
        setContent(null);
        setProgress(null);

        try {
            const [unitResult, pathResult, unitsResult] = await Promise.all([
                api.salesTrainer.getUnit(params.unitId),
                api.salesTrainer.listPaths(),
                api.salesTrainer.listUnits(),
            ]);
            setUnit(unitResult);
            setPaths(pathResult.items);
            setAllUnits(unitsResult.items);

            const learner = readLearnerConfig(unitResult.config);
            const chapterOrderIndex = learner?.chapter_order_index;
            if (typeof chapterOrderIndex !== "number" || chapterOrderIndex < 1) {
                setAccessError("本训练单元未配置章节阅读，请从新人训练路径进入。");
                return;
            }

            const contentId = resolveLearnerContentId(learner);
            if (!contentId) {
                setAccessError("未配置 COO 学习内容，请联系管理员。");
                return;
            }

            const pathContext = findLevelForUnit(pathResult.items, params.unitId);
            const studyContent = await api.learnerStudy.getContent(contentId);
            const chapter = resolveChapterByOrderIndex(studyContent.chapters, chapterOrderIndex);
            const softHubNavigation = searchParams.get("hub") === "1";
            const mismatchError = validateCooChapterAccess({
                pathContext,
                chapter,
                expectedChapterOrderIndex: chapterOrderIndex,
                softHubNavigation,
            });
            if (mismatchError) {
                setAccessError(mismatchError);
                return;
            }

            setContent(studyContent);
            setProgress(studyContent.progress);
            persistLearnReturn(returnTo);
        } catch (err) {
            setUnit(null);
            setAllUnits([]);
            setPaths([]);
            setLoadError(getApiErrorMessage(err));
        } finally {
            setIsLoading(false);
        }
    }, [params.unitId, returnTo, searchParams]);

    useEffect(() => {
        void loadPage();
    }, [loadPage]);

    const pathContext = useMemo(
        () => findLevelForUnit(paths, params.unitId),
        [paths, params.unitId],
    );

    const unitsById = useMemo(() => {
        const map = new Map<string, SalesTrainerUnit>();
        for (const pathUnit of allUnits) {
            map.set(pathUnit.unit_id, pathUnit);
        }
        if (unit) {
            map.set(unit.unit_id, unit);
        }
        return map;
    }, [allUnits, unit]);

    const hubMode = searchParams.get("hub") === "1";

    const chapterNav = useMemo(() => {
        if (hubMode) {
            const hubEntries = buildHubChapterEntries(allUnits).map((entry) => ({
                unitId: entry.unitId,
                chapterOrderIndex: entry.chapterOrderIndex,
                levelTitle: entry.levelTitle,
                pathOrderIndex: entry.chapterOrderIndex,
            }));
            return findAdjacentLearnUnits(hubEntries, params.unitId);
        }
        if (!pathContext) {
            return {
                prevUnitId: null as string | null,
                nextUnitId: null as string | null,
                chapterIndex: 0,
                totalChapters: 0,
            };
        }
        const entries = buildPathChapterEntries(pathContext.path, unitsById);
        return findAdjacentLearnUnits(entries, params.unitId);
    }, [hubMode, pathContext, unitsById, params.unitId, allUnits]);

    const learner = readLearnerConfig(unit?.config);
    const chapterOrderIndex = learner?.chapter_order_index ?? 0;
    const resolvedChapter = content
        ? resolveChapterByOrderIndex(content.chapters, chapterOrderIndex)
        : null;

    if (isLoading) {
        return (
            <div className="space-y-6 animate-in fade-in duration-300">
                <GlassCard className="p-8 text-center" role="status" aria-live="polite" aria-busy="true">
                    <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900" />
                    <p className="text-slate-500">加载本章讲义中...</p>
                </GlassCard>
            </div>
        );
    }

    if (loadError) {
        return (
            <div className="space-y-6 animate-in fade-in duration-300">
                <GlassCard className="p-8 text-center">
                    <h3 className="mb-2 text-lg font-bold text-slate-900">加载失败</h3>
                    <p className="mb-4 text-sm text-slate-500">{loadError}</p>
                    <Button onClick={() => void loadPage()} className="rounded-full">
                        <RefreshCcw className="mr-2 h-4 w-4" /> 重试
                    </Button>
                </GlassCard>
            </div>
        );
    }

    if (accessError) {
        return (
            <CooChapterReaderTerminal
                title="无法阅读本章"
                message={accessError}
                returnTo={returnTo}
            />
        );
    }

    if (!content || !progress || !resolvedChapter || !unit) {
        return (
            <CooChapterReaderTerminal
                title="无法阅读本章"
                message="章节数据不完整，请从新人训练路径重新进入。"
                returnTo={returnTo}
            />
        );
    }

    if (!hubMode && !pathContext) {
        return (
            <CooChapterReaderTerminal
                title="无法阅读本章"
                message="章节数据不完整，请从新人训练路径重新进入。"
                returnTo={returnTo}
            />
        );
    }

    return (
        <CooChapterReader
            contentId={content.learning_content_id}
            contentTitle={content.title}
            contentSummary={content.summary}
            chapter={resolvedChapter}
            progress={progress}
            pathTitle={hubMode ? "商务技巧" : pathContext!.path.title}
            levelTitle={hubMode
                ? `第 ${chapterOrderIndex} 章`
                : pathContext!.level.level_title}
            chapterIndex={chapterNav.chapterIndex}
            totalChapters={chapterNav.totalChapters}
            unitId={unit.unit_id}
            returnTo={returnTo}
            prevUnitId={chapterNav.prevUnitId}
            nextUnitId={chapterNav.nextUnitId}
            hubNavigation={hubMode}
            onProgressUpdated={setProgress}
        />
    );
}
