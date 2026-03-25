"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, ChevronDown, ChevronUp, Sparkles } from "lucide-react";

import type { HighlightItem } from "@/lib/api/types";
import { formatIssueTypeLabel, formatSessionStageLabel } from "@/lib/session-evidence";
import { cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/glass-card";

import { HighlightCard } from "./HighlightCard";
import { HighlightDetailModal } from "./HighlightDetailModal";

interface HighlightListProps {
  highlights: HighlightItem[];
  totalGood: number;
  totalBad: number;
  onJumpToMessage?: (turnNumber: number) => void;
}

function getHighlightReason(highlight: HighlightItem): string | null {
  return highlight.learning_evidence?.reason
    ?? highlight.highlight_reason
    ?? highlight.ai_feedback
    ?? null;
}

function getHighlightStageName(highlight: HighlightItem): string | null {
  return highlight.stage_name
    ?? highlight.learning_evidence?.stage?.name
    ?? (highlight.sales_stage ? formatSessionStageLabel(highlight.sales_stage) : null);
}

function getHighlightSuggestedResponse(highlight: HighlightItem): string | null {
  return highlight.learning_evidence?.suggested_response
    ?? highlight.suggested_response
    ?? null;
}

function getHighlightIssueFamilyLabel(highlight: HighlightItem): string | null {
  return formatIssueTypeLabel(highlight.learning_evidence?.issue_family ?? null);
}

function getHighlightGoalText(highlight: HighlightItem): string | null {
  const goalText = highlight.learning_evidence?.linked_goal?.goal_text;
  return typeof goalText === "string" && goalText.trim() ? goalText.trim() : null;
}

export function HighlightList({
  highlights,
  totalGood,
  totalBad,
  onJumpToMessage,
}: HighlightListProps) {
  const [expandedSections, setExpandedSections] = useState<{
    good: boolean;
    bad: boolean;
  }>({ good: true, bad: true });
  const [selectedHighlight, setSelectedHighlight] = useState<HighlightItem | null>(null);

  const goodHighlights = highlights.filter((h) => h.highlight_type === "good");
  const badHighlights = highlights.filter((h) => h.highlight_type === "bad");

  const toggleSection = (section: "good" | "bad") => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const handleViewContext = (highlight: HighlightItem) => {
    setSelectedHighlight(highlight);
  };

  const handleCloseModal = () => {
    setSelectedHighlight(null);
  };

  if (highlights.length === 0) {
    return (
      <GlassCard className="p-6 text-center">
        <Sparkles className="w-12 h-12 text-slate-300 mx-auto mb-3" />
        <p className="text-slate-700 font-medium">暂无高光片段</p>
        <p className="text-sm text-slate-500 mt-1">完成练习后将自动生成关键 moments</p>
      </GlassCard>
    );
  }

  return (
    <>
      <div className="space-y-6">
        {goodHighlights.length > 0 && (
          <div className="space-y-3">
            <button
              onClick={() => toggleSection("good")}
              className="flex items-center gap-2 w-full text-left group"
            >
              <div className="flex items-center gap-2 bg-green-100 text-green-700 px-3 py-1.5 rounded-full">
                <ThumbsUp className="w-4 h-4" />
                <span className="text-sm font-semibold">优点</span>
                <span className="text-xs bg-green-200 px-1.5 py-0.5 rounded-full">
                  {totalGood}
                </span>
              </div>
              {expandedSections.good ? (
                <ChevronUp className="w-4 h-4 text-slate-400 group-hover:text-slate-600 transition-colors" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-400 group-hover:text-slate-600 transition-colors" />
              )}
            </button>

            <div
              className={cn(
                "grid gap-3 transition-all duration-300",
                expandedSections.good ? "block" : "hidden",
              )}
            >
              {goodHighlights.map((highlight) => (
                <HighlightCard
                  key={highlight.id}
                  id={highlight.id}
                  type="good"
                  content={highlight.content}
                  reason={getHighlightReason(highlight)}
                  stageName={getHighlightStageName(highlight)}
                  issueFamilyLabel={getHighlightIssueFamilyLabel(highlight)}
                  goalText={getHighlightGoalText(highlight)}
                  aiFeedback={highlight.ai_feedback}
                  suggestedResponse={getHighlightSuggestedResponse(highlight)}
                  score={highlight.score ?? undefined}
                  audioUrl={highlight.audio_url ?? undefined}
                  onJumpToMessage={() => onJumpToMessage?.(highlight.turn_number)}
                  onViewContext={() => handleViewContext(highlight)}
                />
              ))}
            </div>
          </div>
        )}

        {badHighlights.length > 0 && (
          <div className="space-y-3">
            <button
              onClick={() => toggleSection("bad")}
              className="flex items-center gap-2 w-full text-left group"
            >
              <div className="flex items-center gap-2 bg-orange-100 text-orange-700 px-3 py-1.5 rounded-full">
                <ThumbsDown className="w-4 h-4" />
                <span className="text-sm font-semibold">待改进</span>
                <span className="text-xs bg-orange-200 px-1.5 py-0.5 rounded-full">
                  {totalBad}
                </span>
              </div>
              {expandedSections.bad ? (
                <ChevronUp className="w-4 h-4 text-slate-400 group-hover:text-slate-600 transition-colors" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-400 group-hover:text-slate-600 transition-colors" />
              )}
            </button>

            <div
              className={cn(
                "grid gap-3 transition-all duration-300",
                expandedSections.bad ? "block" : "hidden",
              )}
            >
              {badHighlights.map((highlight) => (
                <HighlightCard
                  key={highlight.id}
                  id={highlight.id}
                  type="bad"
                  content={highlight.content}
                  reason={getHighlightReason(highlight)}
                  stageName={getHighlightStageName(highlight)}
                  issueFamilyLabel={getHighlightIssueFamilyLabel(highlight)}
                  goalText={getHighlightGoalText(highlight)}
                  aiFeedback={highlight.ai_feedback}
                  suggestedResponse={getHighlightSuggestedResponse(highlight)}
                  score={highlight.score ?? undefined}
                  audioUrl={highlight.audio_url ?? undefined}
                  onJumpToMessage={() => onJumpToMessage?.(highlight.turn_number)}
                  onViewContext={() => handleViewContext(highlight)}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      <HighlightDetailModal
        isOpen={selectedHighlight !== null}
        onClose={handleCloseModal}
        highlight={selectedHighlight}
      />
    </>
  );
}
