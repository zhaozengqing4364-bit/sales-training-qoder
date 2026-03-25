"use client";

import { useState, useEffect, useRef } from "react";
import {
  CheckCircle,
  AlertCircle,
  MessageCircle,
  ChevronRight,
  Play,
  Pause,
  Volume2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface HighlightCardProps {
  id: string;
  type: "good" | "bad";
  content: string;
  reason: string | null;
  stageName?: string | null;
  issueFamilyLabel?: string | null;
  goalText?: string | null;
  suggestedResponse?: string | null;
  aiFeedback?: string | null;
  score?: number | null;
  audioUrl?: string | null;
  onViewContext?: () => void;
  onJumpToMessage?: () => void;
}

export function HighlightCard({
  type,
  content,
  reason,
  stageName,
  issueFamilyLabel,
  goalText,
  suggestedResponse,
  aiFeedback,
  score,
  audioUrl,
  onViewContext,
  onJumpToMessage,
}: HighlightCardProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const isGood = type === "good";

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.remove();
        audioRef.current = null;
      }
    };
  }, []);

  const handlePlayPause = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!audioUrl) return;

    if (isPlaying) {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.remove();
        audioRef.current = null;
      }
      setIsPlaying(false);
      return;
    }

    const allAudioElements = document.querySelectorAll<HTMLAudioElement>('audio[data-highlight-audio="true"]');
    allAudioElements.forEach((audio) => {
      audio.pause();
      audio.remove();
    });

    const audio = new Audio(audioUrl);
    audio.setAttribute("data-highlight-audio", "true");
    audioRef.current = audio;

    audio.play().catch((err) => {
      console.error("[HighlightCard] Audio playback failed:", err);
      setIsPlaying(false);
    });

    setIsPlaying(true);

    audio.onended = () => {
      setIsPlaying(false);
      if (audioRef.current === audio) {
        audioRef.current = null;
      }
      audio.remove();
    };

    audio.onerror = () => {
      console.error("[HighlightCard] Audio error");
      setIsPlaying(false);
      if (audioRef.current === audio) {
        audioRef.current = null;
      }
    };
  };

  const getScoreColor = (value: number) => {
    if (value >= 80) return "text-green-600 bg-green-50 border-green-200";
    if (value >= 60) return "text-yellow-600 bg-yellow-50 border-yellow-200";
    return "text-red-600 bg-red-50 border-red-200";
  };

  const getScoreBorder = (value: number) => {
    if (value >= 80) return "border-green-400";
    if (value >= 60) return "border-yellow-400";
    return "border-red-400";
  };

  return (
    <div
      className={cn(
        "relative rounded-xl border-2 p-4 sm:p-5 transition-all duration-200",
        onJumpToMessage ? "hover:shadow-md cursor-pointer" : "hover:shadow-md",
        isGood
          ? "border-green-200 bg-green-50/50 hover:border-green-300"
          : "border-orange-200 bg-orange-50/50 hover:border-orange-300",
      )}
      onClick={onJumpToMessage}
    >
      <div className="flex items-start justify-between gap-2 mb-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <div
            className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
              isGood ? "bg-green-100 text-green-600" : "bg-orange-100 text-orange-600",
            )}
          >
            {isGood ? (
              <CheckCircle className="w-5 h-5" />
            ) : (
              <AlertCircle className="w-5 h-5" />
            )}
          </div>
          <span
            className={cn(
              "text-sm font-semibold",
              isGood ? "text-green-700" : "text-orange-700",
            )}
          >
            {isGood ? "优点" : "待改进"}
          </span>
          {stageName && (
            <span className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600">
              {stageName}
            </span>
          )}
          {issueFamilyLabel && (
            <span className="text-xs px-2 py-1 rounded-full bg-white/80 border border-slate-200 text-slate-700">
              {issueFamilyLabel}
            </span>
          )}
        </div>

        {score !== null && score !== undefined && (
          <div
            className={cn(
              "px-3 py-1 rounded-full text-sm font-bold border-2 min-w-[44px] h-[24px] flex items-center justify-center flex-shrink-0",
              getScoreColor(score),
              getScoreBorder(score),
            )}
          >
            {score}分
          </div>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex items-start gap-2">
          <MessageCircle className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-slate-700 leading-relaxed line-clamp-2">
            {content}
          </p>
        </div>

        {reason && (
          <div
            className={cn(
              "rounded-xl border px-3 py-3",
              isGood ? "border-green-100 bg-white/70" : "border-orange-100 bg-white/70",
            )}
          >
            <p className="text-xs font-semibold text-slate-500 mb-1">为什么重要</p>
            <p
              className={cn(
                "text-sm",
                isGood ? "text-green-700" : "text-orange-700",
              )}
            >
              {reason}
            </p>
          </div>
        )}

        {goalText && (
          <div className="pl-6 pt-2 border-t border-slate-100">
            <p className="text-sm text-slate-700">
              <span className="text-xs font-semibold text-slate-500">下一轮重点：</span>
              {goalText}
            </p>
          </div>
        )}

        {aiFeedback && (
          <div className="pl-6 pt-2 border-t border-slate-100">
            <p className="text-xs text-slate-500 mb-1">AI 反馈</p>
            <p className="text-sm text-slate-600">{aiFeedback}</p>
          </div>
        )}

        {suggestedResponse && (
          <div className="pl-6 pt-2 border-t border-orange-100">
            <p className="text-xs text-orange-600 mb-1">更优回应</p>
            <p className="text-sm text-slate-700 bg-white/50 p-2 rounded">
              {suggestedResponse}
            </p>
          </div>
        )}
      </div>

      {audioUrl && (
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-100">
          <Button
            size="sm"
            variant={isPlaying ? "primary" : "outline"}
            onClick={handlePlayPause}
            className="min-w-[88px] min-h-[36px]"
          >
            {isPlaying ? (
              <>
                <Pause className="w-4 h-4 mr-1" />
                暂停
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-1" />
                播放
              </>
            )}
          </Button>
          <div className="flex items-center gap-1 text-sm text-slate-500">
            <Volume2 className="w-4 h-4" />
            <span>音频回放</span>
          </div>
        </div>
      )}

      {onViewContext && (
        <div className="flex justify-end mt-3">
          <Button
            variant="ghost"
            size="sm"
            className="text-slate-500 hover:text-slate-700 min-w-[88px] min-h-[36px]"
            onClick={(e) => {
              e.stopPropagation();
              onViewContext();
            }}
          >
            查看详情
            <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      )}
    </div>
  );
}
