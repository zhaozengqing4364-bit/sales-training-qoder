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
import { CoachHealthNotice } from "@/components/practice/CoachHealthNotice";
import {
    extractLiveSessionClaimTruth,
    extractLiveSessionLearningCue,
    formatClaimTruthEvidenceNote,
    formatClaimTruthSummary,
    getClaimTruthTone,
} from "@/lib/session-evidence";
import type { LiveSessionConclusionSummary } from "@/lib/api/types";
import type {
    FuzzyDetection,
    SalesStage,
    ScoreUpdate,
    ActionCard,
    CoachHealth,
    SlideUpdate,
    PointCovered,
    ForbiddenWordDetection,
} from "@/hooks/use-practice-websocket";

export type ActionCompletionStatus = {
    state: "waiting" | "improved" | "missed";
    label: string;
    detail: string;
};

interface RightPanelContentProps {
    scenarioType: "sales" | "presentation";
    presentationId?: string;
    currentSlide: SlideUpdate | null;
    presentationFocusPage?: number | null;
    points: PointCovered[];
    forbiddenWords: ForbiddenWordDetection[];
    scores: ScoreUpdate | null;
    liveSessionSummary: LiveSessionConclusionSummary | null;
    actionCard: ActionCard | null;
    actionCompletionStatus?: ActionCompletionStatus | null;
    coachHealth: CoachHealth;
    fuzzyDetections: FuzzyDetection[];
    salesStage: SalesStage | null;
    sendMessage: (type: string, data: unknown) => void;
}

export const RightPanelContent = React.memo(function RightPanelContent({
    scenarioType,
    presentationId,
    currentSlide,
    presentationFocusPage,
    points,
    forbiddenWords,
    scores,
    liveSessionSummary,
    actionCard,
    actionCompletionStatus,
    coachHealth,
    fuzzyDetections,
    salesStage,
    sendMessage,
}: RightPanelContentProps) {
    const suppressCompetingCoaching = Boolean(actionCard);
    const visibleFuzzyDetections = suppressCompetingCoaching ? [] : fuzzyDetections;
    const objectionProofPrompt = actionCard && scores?.suggestions?.length
        ? scores.suggestions[0]
        : null;
    const liveLearningCue = extractLiveSessionLearningCue(liveSessionSummary);
    const liveClaimTruth = extractLiveSessionClaimTruth(liveSessionSummary);
    const liveClaimTruthSummary = formatClaimTruthSummary(liveClaimTruth);
    const liveClaimTruthEvidenceNote = formatClaimTruthEvidenceNote(liveClaimTruth);
    const liveClaimTruthTone = getClaimTruthTone(liveClaimTruth?.status);

    if (scenarioType === "presentation") {
        return (
            <div className="space-y-4">
                {presentationFocusPage && (
                    <div className="rounded-2xl border border-purple-100 bg-purple-50/80 p-4 text-sm text-purple-900">
                        <p className="text-xs font-semibold text-purple-700">本轮重点页</p>
                        <p className="mt-1 font-bold">第 {presentationFocusPage} 页</p>
                        <p className="mt-2 text-xs text-purple-800">本轮优先补齐这一页的必讲点、缺失点或案例证据。</p>
                    </div>
                )}
                <SlideViewer
                    presentationId={presentationId}
                    currentPage={currentSlide?.current_page || 1}
                    totalPages={currentSlide?.total_pages || 1}
                    slideContent={currentSlide?.content}
                    slideImageUrl={currentSlide?.image_url}
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
            <CoachHealthNotice coachHealth={coachHealth} />

            {(liveLearningCue || liveClaimTruthSummary) && (
                <div className="bg-white/60 backdrop-blur-sm rounded-2xl p-4 border border-white/70 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
                    <div className="flex items-center gap-2 mb-3">
                        <span className="w-2 h-2 rounded-full bg-violet-500" />
                        <h3 className="text-sm font-semibold text-slate-700">当前同 session 结论</h3>
                    </div>

                    <div className="space-y-3 text-xs">
                        {liveLearningCue?.issueText && (
                            <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
                                <p className="font-bold text-amber-700 mb-1">
                                    主问题{liveLearningCue.issueLabel ? ` · ${liveLearningCue.issueLabel}` : ""}
                                </p>
                                <p className="text-amber-900">{liveLearningCue.issueText}</p>
                                {liveLearningCue.issueAction && (
                                    <p className="text-amber-800 mt-2">修正动作：{liveLearningCue.issueAction}</p>
                                )}
                            </div>
                        )}

                        {liveLearningCue?.goalText && (
                            <div className="rounded-lg border border-sky-100 bg-sky-50 p-3">
                                <p className="font-bold text-sky-700 mb-1">
                                    下一轮目标{liveLearningCue.goalLabel ? ` · ${liveLearningCue.goalLabel}` : ""}
                                </p>
                                <p className="text-sky-900">{liveLearningCue.goalText}</p>
                                {liveLearningCue.goalRule && (
                                    <p className="text-sky-800 mt-2">判定条件：{liveLearningCue.goalRule}</p>
                                )}
                            </div>
                        )}

                        {liveClaimTruth && liveClaimTruthSummary && (
                            <div
                                className={cn(
                                    "rounded-lg border p-3",
                                    liveClaimTruthTone === "critical"
                                        ? "border-rose-100 bg-rose-50"
                                        : liveClaimTruthTone === "warning"
                                        ? "border-amber-100 bg-amber-50"
                                        : liveClaimTruthTone === "verified"
                                        ? "border-emerald-100 bg-emerald-50"
                                        : "border-slate-200 bg-slate-50",
                                )}
                            >
                                <p
                                    className={cn(
                                        "font-bold mb-1",
                                        liveClaimTruthTone === "critical"
                                            ? "text-rose-700"
                                            : liveClaimTruthTone === "warning"
                                            ? "text-amber-700"
                                            : liveClaimTruthTone === "verified"
                                            ? "text-emerald-700"
                                            : "text-slate-700",
                                    )}
                                >
                                    主张证据状态 · {liveClaimTruth.label}
                                </p>
                                <p
                                    className={cn(
                                        liveClaimTruthTone === "critical"
                                            ? "text-rose-900"
                                            : liveClaimTruthTone === "warning"
                                            ? "text-amber-900"
                                            : liveClaimTruthTone === "verified"
                                            ? "text-emerald-900"
                                            : "text-slate-800",
                                    )}
                                >
                                    {liveClaimTruthSummary}
                                </p>
                                {liveClaimTruthEvidenceNote && (
                                    <p
                                        className={cn(
                                            "mt-2",
                                            liveClaimTruthTone === "critical"
                                                ? "text-rose-800"
                                                : liveClaimTruthTone === "warning"
                                                ? "text-amber-800"
                                                : liveClaimTruthTone === "verified"
                                                ? "text-emerald-800"
                                                : "text-slate-600",
                                        )}
                                    >
                                        {liveClaimTruthEvidenceNote}
                                    </p>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {actionCard && (
                <div className="bg-white/60 backdrop-blur-sm rounded-2xl p-4 border border-white/70 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
                    <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-emerald-500" />
                        本轮唯一动作
                    </h3>
                    <div className="space-y-2 text-xs">
                        <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-3">
                            <p className="font-bold text-emerald-700 mb-1">问题</p>
                            <p className="text-emerald-800">{actionCard.issue}</p>
                        </div>
                        <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
                            <p className="font-bold text-blue-700 mb-1">替换句</p>
                            <p className="text-blue-800">{actionCard.replacement}</p>
                        </div>
                        <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
                            <p className="font-bold text-amber-700 mb-1">下一轮判定条件</p>
                            <p className="text-amber-800">{actionCard.next_turn_rule}</p>
                        </div>
                        {actionCompletionStatus && (
                            <div
                                className={cn(
                                    "rounded-lg border p-3",
                                    actionCompletionStatus.state === "improved"
                                        ? "border-emerald-100 bg-emerald-50"
                                        : actionCompletionStatus.state === "missed"
                                        ? "border-amber-100 bg-amber-50"
                                        : "border-slate-200 bg-slate-50",
                                )}
                            >
                                <p
                                    className={cn(
                                        "font-bold mb-1",
                                        actionCompletionStatus.state === "improved"
                                            ? "text-emerald-700"
                                            : actionCompletionStatus.state === "missed"
                                            ? "text-amber-700"
                                            : "text-slate-700",
                                    )}
                                >
                                    动作完成状态
                                </p>
                                <p
                                    className={cn(
                                        "font-semibold",
                                        actionCompletionStatus.state === "improved"
                                            ? "text-emerald-900"
                                            : actionCompletionStatus.state === "missed"
                                            ? "text-amber-900"
                                            : "text-slate-800",
                                    )}
                                >
                                    {actionCompletionStatus.label}
                                </p>
                                <p className="text-xs text-slate-600 mt-1">{actionCompletionStatus.detail}</p>
                            </div>
                        )}
                        {objectionProofPrompt && (
                            <div className="rounded-lg border border-violet-100 bg-violet-50 p-3">
                                <p className="font-bold text-violet-700 mb-1">当前仍卡住的证明</p>
                                <p className="text-violet-800">{objectionProofPrompt}</p>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {visibleFuzzyDetections.length > 0 && (
                <div className="bg-white/50 backdrop-blur-sm rounded-2xl p-4 border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
                    <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-amber-500" />
                        实时提示
                    </h3>
                    <div className="space-y-3">
                        {visibleFuzzyDetections.map((detection, idx) => (
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

            <ScorePanel scores={scores} suppressSuggestions={suppressCompetingCoaching} />
        </div>
    );
});
