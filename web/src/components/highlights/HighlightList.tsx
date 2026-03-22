"use client";

import { useState } from "react";
import { HighlightCard } from "./HighlightCard";
import { HighlightDetailModal } from "./HighlightDetailModal";
import { ThumbsUp, ThumbsDown, ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/glass-card";

interface Highlight {
  id: string;
  turn_number: number;
  role: "assistant" | "user";
  content: string;
  timestamp: string;
  highlight_type: "good" | "bad";
  highlight_reason: string | null;
  ai_feedback: string | null;
  suggested_response: string | null;
  sales_stage: string | null;
  stage_name: string | null;
  context: {
    prev_message?: {
      id: string;
      role: string;
      content: string;
      timestamp: string;
    } | null;
    next_message?: {
      id: string;
      role: string;
      content: string;
      timestamp: string;
    } | null;
  };
  audio_url?: string | null;
  score?: number | null;
}

interface HighlightListProps {
  highlights: Highlight[];
  totalGood: number;
  totalBad: number;
  onJumpToMessage?: (turnNumber: number) => void;
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
  const [selectedHighlight, setSelectedHighlight] = useState<Highlight | null>(null);

  const goodHighlights = highlights.filter((h) => h.highlight_type === "good");
  const badHighlights = highlights.filter((h) => h.highlight_type === "bad");

  const toggleSection = (section: "good" | "bad") => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const handleViewContext = (highlight: Highlight) => {
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
        {/* Good Highlights Section */}
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
                expandedSections.good ? "block" : "hidden"
              )}
            >
              {goodHighlights.map((highlight) => (
                <HighlightCard
                  key={highlight.id}
                  id={highlight.id}
                  type="good"
                  content={highlight.content}
                  reason={highlight.highlight_reason}
                  stageName={highlight.stage_name}
                  aiFeedback={highlight.ai_feedback}
                  score={highlight.score ?? undefined}
                  audioUrl={highlight.audio_url ?? undefined}
                  onJumpToMessage={() => onJumpToMessage?.(highlight.turn_number)}
                  onViewContext={() => handleViewContext(highlight)}
                />
              ))}
            </div>
          </div>
        )}

        {/* Bad Highlights Section */}
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
                expandedSections.bad ? "block" : "hidden"
              )}
            >
              {badHighlights.map((highlight) => (
                <HighlightCard
                  key={highlight.id}
                  id={highlight.id}
                  type="bad"
                  content={highlight.content}
                  reason={highlight.highlight_reason}
                  stageName={highlight.stage_name}
                  aiFeedback={highlight.ai_feedback}
                  suggestedResponse={highlight.suggested_response}
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

      {/* Detail Modal */}
      <HighlightDetailModal
        isOpen={selectedHighlight !== null}
        onClose={handleCloseModal}
        highlight={selectedHighlight}
      />
    </>
  );
}
