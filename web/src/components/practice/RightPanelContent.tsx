"use client";

/**
 * v1-12 Fix: Extracted from inline function in page.tsx to prevent
 * re-mounting on every parent render.
 */
import * as React from "react";
import { cn } from "@/lib/utils";
import { SlideViewer } from "@/components/practice/presentation/SlideViewer";
import { PageNavigator } from "@/components/practice/presentation/PageNavigator";
import { PointTracker } from "@/components/practice/presentation/PointTracker";
import { ForbiddenWordsAlert } from "@/components/practice/presentation/ForbiddenWordsAlert";
import { ScorePanel } from "@/components/practice/ScorePanel";
import type {
    FuzzyDetection,
    SalesStage,
    ScoreUpdate,
    SlideUpdate,
    PointCovered,
    ForbiddenWordDetection,
} from "@/hooks/use-practice-websocket";

interface RightPanelContentProps {
    scenarioType: "sales" | "presentation";
    currentSlide: SlideUpdate | null;
    points: PointCovered[];
    forbiddenWords: ForbiddenWordDetection[];
    scores: ScoreUpdate | null;
    fuzzyDetections: FuzzyDetection[];
    salesStage: SalesStage | null;
    sendMessage: (type: string, data: unknown) => void;
}

export const RightPanelContent = React.memo(function RightPanelContent({
    scenarioType,
    currentSlide,
    points,
    forbiddenWords,
    scores,
    fuzzyDetections,
    salesStage,
    sendMessage,
}: RightPanelContentProps) {
    if (scenarioType === "presentation") {
        return (
            <div className="space-y-4">
                <SlideViewer
                    currentPage={currentSlide?.current_page || 1}
                    totalPages={currentSlide?.total_pages || 1}
                    slideContent={currentSlide?.content}
                    onPageChange={(page) => {
                        sendMessage("page_change", { page_number: page });
                    }}
                />

                <PageNavigator
                    currentPage={currentSlide?.current_page || 1}
                    totalPages={currentSlide?.total_pages || 1}
                    onPageChange={(page) => {
                        sendMessage("page_change", { page_number: page });
                    }}
                />

                <PointTracker
                    points={points.map((p) => ({
                        id: p.point_id,
                        content: p.content || "",
                        isCovered: p.is_covered,
                    }))}
                />

                <ForbiddenWordsAlert
                    detections={forbiddenWords}
                    onDismiss={() => {
                        // 可以在这里添加本地状态管理来隐藏已关闭的提示
                    }}
                />

                <ScorePanel scores={scores} />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {fuzzyDetections.length > 0 && (
                <div className="bg-white/50 backdrop-blur-sm rounded-2xl p-4 border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
                    <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-amber-500" />
                        实时提示
                    </h3>
                    <div className="space-y-3">
                        {fuzzyDetections.map((detection, idx) => (
                            <div
                                key={idx}
                                className={cn(
                                    "p-3 rounded-lg border",
                                    detection.severity === "high"
                                        ? "bg-red-50 border-red-100"
                                        : detection.severity === "medium"
                                        ? "bg-amber-50 border-amber-100"
                                        : "bg-blue-50 border-blue-100"
                                )}
                            >
                                <div
                                    className={cn(
                                        "text-xs font-bold mb-1",
                                        detection.severity === "high"
                                            ? "text-red-600"
                                            : detection.severity === "medium"
                                            ? "text-amber-600"
                                            : "text-blue-600"
                                    )}
                                >
                                    {detection.severity === "high" ? "⚠️" : "💡"}{" "}
                                    {detection.category === "feedback"
                                        ? "反馈"
                                        : "模糊词检测"}
                                </div>
                                {detection.matched.length > 0 && (
                                    <p className="text-xs text-slate-600 mb-1">
                                        检测到: {detection.matched.join(", ")}
                                    </p>
                                )}
                                <p className="text-xs text-slate-600">
                                    {detection.suggestion}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {salesStage && (
                <div className="bg-white/50 backdrop-blur-sm rounded-2xl p-4 border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
                    <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-blue-500" />
                        当前阶段
                    </h3>
                    <div className="bg-blue-50 border border-blue-100 p-3 rounded-lg">
                        <div className="text-xs text-blue-600 font-bold mb-1">
                            📊 {salesStage.stage_name}
                        </div>
                        <div className="w-full h-1.5 bg-blue-100 rounded-full mb-2">
                            <div
                                className="h-full bg-blue-500 rounded-full transition-all duration-500"
                                style={{
                                    width: `${salesStage.progress * 100}%`,
                                }}
                            />
                        </div>
                        <ul className="text-xs text-slate-600 list-disc list-inside space-y-1">
                            {salesStage.key_actions.map((action, idx) => (
                                <li key={idx}>{action}</li>
                            ))}
                        </ul>
                        {salesStage.guidance && (
                            <p className="text-xs text-slate-500 mt-2 italic">
                                {salesStage.guidance}
                            </p>
                        )}
                    </div>
                </div>
            )}

            <ScorePanel scores={scores} />
        </div>
    );
});
