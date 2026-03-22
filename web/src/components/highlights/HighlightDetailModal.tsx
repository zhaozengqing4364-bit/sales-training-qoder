"use client";

import { useState, useEffect, useRef } from "react";
import { GlassModal } from "@/components/ui/glass-modal";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { CheckCircle, AlertCircle, Play, Pause, Volume2, MessageCircle, Clock } from "lucide-react";

interface HighlightDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  highlight: {
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
  } | null;
}

export function HighlightDetailModal({
  isOpen,
  onClose,
  highlight,
}: HighlightDetailModalProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Cleanup audio on unmount and when modal closes
  useEffect(() => {
    if (!isOpen && audioRef.current) {
      audioRef.current.pause();
      audioRef.current.remove();
      audioRef.current = null;
    }
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.remove();
        audioRef.current = null;
      }
    };
  }, [isOpen]);

  if (!highlight) return null;

  const isGood = highlight.highlight_type === "good";

  const handlePlayPause = () => {
    if (!highlight.audio_url) return;

    if (isPlaying) {
      // Stop current audio
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.remove();
        audioRef.current = null;
      }
      setIsPlaying(false);
    } else {
      // Create and play new audio
      const audio = new Audio(highlight.audio_url);
      audioRef.current = audio;

      audio.play().catch((err) => {
        console.error('[HighlightDetailModal] Audio playback failed:', err);
        setIsPlaying(false);
        if (audioRef.current === audio) {
          audioRef.current = null;
        }
      });

      setIsPlaying(true);

      // Handle audio events
      audio.onpause = () => {
        setIsPlaying(false);
      };

      audio.onended = () => {
        setIsPlaying(false);
        if (audioRef.current === audio) {
          audioRef.current = null;
        }
        audio.remove();
      };

      audio.onerror = () => {
        console.error('[HighlightDetailModal] Audio error');
        setIsPlaying(false);
        if (audioRef.current === audio) {
          audioRef.current = null;
        }
      };
    }
  };

  const formatTime = (timestamp: string) => {
    if (!timestamp) return "--";
    const date = new Date(timestamp);
    return date.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-green-600";
    if (score >= 60) return "text-yellow-600";
    return "text-red-600";
  };

  const getScoreBackground = (score: number) => {
    if (score >= 80) return "bg-green-50 border-green-200";
    if (score >= 60) return "bg-yellow-50 border-yellow-200";
    return "bg-red-50 border-red-200";
  };

  return (
    <GlassModal
      isOpen={isOpen}
      onClose={onClose}
      title="高光片段详情"
      description="查看该片段的详细信息和AI反馈"
      size="lg"
    >
      <div className="space-y-5">
        {/* Header with type badge and score */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2 flex-wrap">
            <div
              className={cn(
                "px-3 py-1.5 rounded-full text-sm font-semibold flex items-center gap-1.5",
                isGood ? "bg-green-100 text-green-700" : "bg-orange-100 text-orange-700"
              )}
            >
              {isGood ? (
                <CheckCircle className="w-4 h-4" />
              ) : (
                <AlertCircle className="w-4 h-4" />
              )}
              <span>{isGood ? "优点" : "待改进"}</span>
            </div>

            {highlight.stage_name && (
              <span className="px-3 py-1.5 rounded-full bg-slate-100 text-slate-700 text-sm font-medium">
                {highlight.stage_name}
              </span>
            )}

            <span className="flex items-center gap-1 text-slate-500 text-sm">
              <Clock className="w-4 h-4" />
              第 {highlight.turn_number} 轮
            </span>
          </div>

          {highlight.score !== null && highlight.score !== undefined && (
            <div
              className={cn(
                "px-3 py-1.5 rounded-full border-2 text-sm font-bold",
                getScoreBackground(highlight.score),
                getScoreColor(highlight.score)
              )}
            >
              {highlight.score}分
            </div>
          )}
        </div>

        {/* Audio player */}
        {highlight.audio_url && (
          <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl">
            <Button
              size="sm"
              variant={isPlaying ? "primary" : "outline"}
              onClick={handlePlayPause}
              className="min-w-[44px] min-h-[44px]"
            >
              {isPlaying ? (
                <Pause className="w-5 h-5" />
              ) : (
                <Play className="w-5 h-5 ml-0.5" />
              )}
            </Button>
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Volume2 className="w-4 h-4" />
              <span>点击播放音频</span>
            </div>
          </div>
        )}

        {/* Main content */}
        <div className="p-4 bg-slate-50 rounded-xl">
          <div className="flex items-center gap-2 mb-2 text-slate-500 text-sm">
            <MessageCircle className="w-4 h-4" />
            <span>
              {highlight.role === "assistant" ? "AI" : "用户"}
            </span>
            <span>·</span>
            <span>{formatTime(highlight.timestamp)}</span>
          </div>
          <p className="text-base leading-relaxed text-slate-800">
            {highlight.content}
          </p>
        </div>

        {/* Highlight reason */}
        {highlight.highlight_reason && (
          <div
            className={cn(
              "p-4 rounded-xl border-l-4",
              isGood
                ? "bg-green-50 border-green-300"
                : "bg-orange-50 border-orange-300"
            )}
          >
            <p
              className={cn(
                "text-sm font-medium",
                isGood ? "text-green-700" : "text-orange-700"
              )}
            >
              {highlight.highlight_reason}
            </p>
          </div>
        )}

        {/* AI Feedback */}
        {highlight.ai_feedback && (
          <div className="p-4 bg-blue-50 rounded-xl border border-blue-200">
            <p className="text-sm text-blue-700">
              <span className="font-semibold">AI 反馈：</span>
              {highlight.ai_feedback}
            </p>
          </div>
        )}

        {/* Suggested response (for bad highlights) */}
        {!isGood && highlight.suggested_response && (
          <div className="p-4 bg-amber-50 rounded-xl border border-amber-200">
            <p className="text-sm text-amber-800">
              <span className="font-semibold">建议改进：</span>
              {highlight.suggested_response}
            </p>
          </div>
        )}

        {/* Context messages */}
        <div className="space-y-3">
          <p className="text-sm font-semibold text-slate-700">对话上下文</p>

          {/* Previous message */}
          {highlight.context?.prev_message && (
            <div className="flex gap-3 p-3 bg-slate-50 rounded-lg">
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold",
                  highlight.context.prev_message.role === "assistant"
                    ? "bg-blue-100 text-blue-700"
                    : "bg-slate-200 text-slate-700"
                )}
              >
                AI
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-700 line-clamp-3">
                  {highlight.context.prev_message.content}
                </p>
              </div>
            </div>
          )}

          {/* Next message */}
          {highlight.context?.next_message && (
            <div className="flex gap-3 p-3 bg-slate-50 rounded-lg">
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold",
                  highlight.context.next_message.role === "assistant"
                    ? "bg-blue-100 text-blue-700"
                    : "bg-slate-200 text-slate-700"
                )}
              >
                AI
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-700 line-clamp-3">
                  {highlight.context.next_message.content}
                </p>
              </div>
            </div>
          )}

          {!highlight.context?.prev_message && !highlight.context?.next_message && (
            <p className="text-sm text-slate-500 italic">暂无上下文信息</p>
          )}
        </div>

        {/* Close button */}
        <div className="flex justify-end pt-2">
          <Button variant="outline" onClick={onClose} className="min-w-[88px] min-h-[44px]">
            关闭
          </Button>
        </div>
      </div>
    </GlassModal>
  );
}
