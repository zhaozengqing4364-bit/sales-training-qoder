"use client";

/**
 * Real-time Evaluation Feedback Component (C6)
 */

import { useState } from "react";
import { CheckCircle, TrendingUp, X } from "lucide-react";
import { GlassCard } from "@/components/ui/glass-card";

export interface EvaluationFeedback {
    feedback_type: "stage_feedback" | "milestone" | "comprehensive_report";
    stage_number?: number;
    scores?: Record<string, number>;
    strengths?: string[];
    suggestions?: string[];
    summary?: string;
    message?: string;
    overall_score?: number;
    key_strengths?: string[];
    key_improvements?: string[];
}

export function RealtimeFeedback() {
    const [feedbacks] = useState<EvaluationFeedback[]>([]);
    const [isExpanded, setIsExpanded] = useState(false);
    const unreadCount = feedbacks.length;

    return (
        <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2">
            {!isExpanded && feedbacks.length > 0 && (
                <button
                    onClick={() => setIsExpanded(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-white rounded-full shadow-lg border"
                >
                    <div className="w-4 h-4 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-sm">{unreadCount} 条新反馈</span>
                </button>
            )}

            {isExpanded && (
                <div className="w-80 max-h-96 overflow-y-auto">
                    <GlassCard className="p-4">
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="font-medium">实时评估反馈</h3>
                            <button onClick={() => setIsExpanded(false)} className="p-1">
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                        <div className="space-y-3">
                            {feedbacks.map((feedback, i) => (
                                <FeedbackItem key={i} feedback={feedback} />
                            ))}
                        </div>
                    </GlassCard>
                </div>
            )}
        </div>
    );
}

function FeedbackItem({ feedback }: { feedback: EvaluationFeedback }) {
    if (feedback.feedback_type === "milestone") {
        return (
            <div className="flex items-start gap-2 p-2 bg-blue-50 rounded-lg">
                <CheckCircle className="w-4 h-4 text-blue-500 mt-0.5" />
                <p className="text-sm text-blue-900">{feedback.message}</p>
            </div>
        );
    }

    if (feedback.feedback_type === "stage_feedback") {
        return (
            <div className="p-3 bg-zinc-50 rounded-lg">
                <div className="flex justify-between mb-2">
                    <span className="text-sm font-medium">第{feedback.stage_number}阶段</span>
                    <span className="text-sm font-semibold">
                        {feedback.scores ? Object.values(feedback.scores)[0]?.toFixed(0) : 0}分
                    </span>
                </div>
                {feedback.summary && <p className="text-xs text-zinc-600 mb-2">{feedback.summary}</p>}
                {feedback.strengths && feedback.strengths[0] && (
                    <div className="flex items-center gap-1 text-xs text-zinc-600">
                        <TrendingUp className="w-3 h-3 text-green-500" />
                        {feedback.strengths[0]}
                    </div>
                )}
            </div>
        );
    }

    return null;
}
