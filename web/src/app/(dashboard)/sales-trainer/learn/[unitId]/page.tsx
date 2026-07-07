"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { RefreshCcw } from "lucide-react";

import {
    CooChapterReader,
    CooChapterReaderTerminal,
} from "@/components/sales-trainer/coo-chapter-reader";
import { TrainingMaterialsSection } from "@/components/sales-trainer/training-materials-section";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    LearnerStudyContent,
    LearnerStudyProgress,
    SalesTrainerUnit,
    SalesTrainerUnitBriefMaterial,
} from "@/lib/api/types";
import {
    decodeReturnTo,
    persistLearnReturn,
    resolveChapterByOrderIndex,
    resolveLearnerContentId,
} from "@/lib/sales-trainer/coo-learn-navigation";
import { readLearnerConfig } from "@/lib/sales-trainer/learner-presenter";

export default function SalesTrainerLearnPage() {
    const params = useParams<{ unitId: string }>();
    const searchParams = useSearchParams();
    const returnTo = decodeReturnTo(searchParams.get("returnTo"));

    const [unit, setUnit] = useState<SalesTrainerUnit | null>(null);
    const [content, setContent] = useState<LearnerStudyContent | null>(null);
    const [progress, setProgress] = useState<LearnerStudyProgress | null>(null);
    const [materials, setMaterials] = useState<SalesTrainerUnitBriefMaterial[]>([]);
    const [accessError, setAccessError] = useState<string | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const loadPage = useCallback(async () => {
        setIsLoading(true);
        setLoadError(null);
        setAccessError(null);
        setContent(null);
        setProgress(null);
        setMaterials([]);

        try {
            const unitResult = await api.salesTrainer.getUnit(params.unitId);
            setUnit(unitResult);

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

            const studyContent = await api.learnerStudy.getContent(contentId);
            const chapter = resolveChapterByOrderIndex(studyContent.chapters, chapterOrderIndex);
            if (!chapter) {
                setAccessError("未找到对应章节内容，请联系管理员检查配置。");
                return;
            }

            setContent(studyContent);
            setProgress(studyContent.progress);
            persistLearnReturn(returnTo);

            // 拉取本关训练材料（PPT 模板等），在章节阅读页底部展示下载/预览入口。
            try {
                const brief = await api.salesTrainer.getUnitBrief(params.unitId);
                setMaterials(brief.materials ?? []);
            } catch {
                // 材料加载失败不阻塞章节阅读，仅隐藏材料区块。
                setMaterials([]);
            }
        } catch (err) {
            setUnit(null);
            setLoadError(getApiErrorMessage(err));
        } finally {
            setIsLoading(false);
        }
    }, [params.unitId, returnTo]);

    useEffect(() => {
        void loadPage();
    }, [loadPage]);

    const hubMode = searchParams.get("hub") === "1";

    const learner = readLearnerConfig(unit?.config);
    const chapterOrderIndex = learner?.chapter_order_index ?? 0;
    const resolvedChapter = content
        ? resolveChapterByOrderIndex(content.chapters, chapterOrderIndex)
        : null;
    const sortedChapters = content
        ? [...content.chapters].sort((left, right) => left.order_index - right.order_index)
        : [];
    const chapterIndex = resolvedChapter
        ? sortedChapters.findIndex((chapter) => chapter.chapter_id === resolvedChapter.chapter_id) + 1
        : 0;

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

    return (
        <div className="space-y-6">
            <CooChapterReader
                contentId={content.learning_content_id}
                contentTitle={content.title}
                contentSummary={content.summary}
                chapter={resolvedChapter}
                progress={progress}
                pathTitle={hubMode ? "商务技巧" : "新人训练"}
                levelTitle={`第 ${chapterOrderIndex} 章`}
                chapterIndex={chapterIndex}
                totalChapters={sortedChapters.length}
                unitId={unit.unit_id}
                returnTo={returnTo}
                prevUnitId={null}
                nextUnitId={null}
                hubNavigation={hubMode}
                onProgressUpdated={setProgress}
            />
            <TrainingMaterialsSection
                materials={materials}
                title="本关训练材料"
                emptyHint="本关暂无训练材料"
            />
        </div>
    );
}
