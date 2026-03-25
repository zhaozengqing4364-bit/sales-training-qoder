"use client";

import { useState, useEffect, useRef } from "react";
import {
  CheckCircle,
  AlertCircle,
  Play,
  Pause,
  Volume2,
  MessageCircle,
  Clock,
} from "lucide-react";

import type { HighlightItem, ReplayContextMessage, ReplayHighlightContext } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { GlassModal } from "@/components/ui/glass-modal";
import {
  formatGoalTypeLabel,
  formatIssueTypeLabel,
  formatSessionStageLabel,
} from "@/lib/session-evidence";
import { cn } from "@/lib/utils";

interface HighlightDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  highlight: HighlightItem | null;
}

function formatRoleLabel(role?: string | null): string {
  if (role === "assistant") return "AI";
  if (role === "user") return "用户";
  return "对话";
}

function formatContextLabel(label: "prev" | "next"): string {
  return label === "prev" ? "上一轮" : "下一轮";
}

function resolveHighlightReason(highlight: HighlightItem): string | null {
  return highlight.learning_evidence?.reason
    ?? highlight.highlight_reason
    ?? highlight.ai_feedback
    ?? null;
}

function resolveHighlightStageName(highlight: HighlightItem): string | null {
  return highlight.stage_name
    ?? highlight.learning_evidence?.stage?.name
    ?? (highlight.sales_stage ? formatSessionStageLabel(highlight.sales_stage) : null);
}

function resolveSuggestedResponse(highlight: HighlightItem): string | null {
  return highlight.learning_evidence?.suggested_response
    ?? highlight.suggested_response
    ?? null;
}

function resolveContext(highlight: HighlightItem): ReplayHighlightContext {
  return highlight.learning_evidence?.nearby_context
    ?? highlight.context
    ?? {};
}

function ContextMessageCard({
  label,
  message,
}: {
  label: "prev" | "next";
  message?: ReplayContextMessage | null;
}) {
  if (!message) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 space-y-2">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <span className="text-xs font-semibold text-slate-500">{formatContextLabel(label)}</span>
        <span className="text-xs rounded-full bg-white px-2 py-1 text-slate-600 border border-slate-200">
          {formatRoleLabel(message.role)}
        </span>
      </div>
      <p className="text-sm text-slate-700 leading-relaxed">{message.content || "--"}</p>
    </div>
  );
}

export function HighlightDetailModal({
  isOpen,
  onClose,
  highlight,
}: HighlightDetailModalProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

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
  const learningEvidence = highlight.learning_evidence ?? null;
  const issueFamilyLabel = formatIssueTypeLabel(learningEvidence?.issue_family ?? null);
  const stageName = resolveHighlightStageName(highlight);
  const reason = resolveHighlightReason(highlight);
  const suggestedResponse = resolveSuggestedResponse(highlight);
  const linkedIssue = learningEvidence?.linked_issue ?? null;
  const linkedGoal = learningEvidence?.linked_goal ?? null;
  const goalTypeLabel = formatGoalTypeLabel(linkedGoal?.goal_type ?? null);
  const context = resolveContext(highlight);

  const handlePlayPause = () => {
    if (!highlight.audio_url) return;

    if (isPlaying) {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.remove();
        audioRef.current = null;
      }
      setIsPlaying(false);
      return;
    }

    const audio = new Audio(highlight.audio_url);
    audioRef.current = audio;

    audio.play().catch((err) => {
      console.error("[HighlightDetailModal] Audio playback failed:", err);
      setIsPlaying(false);
      if (audioRef.current === audio) {
        audioRef.current = null;
      }
    });

    setIsPlaying(true);

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
      console.error("[HighlightDetailModal] Audio error");
      setIsPlaying(false);
      if (audioRef.current === audio) {
        audioRef.current = null;
      }
    };
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
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2 flex-wrap">
            <div
              className={cn(
                "px-3 py-1.5 rounded-full text-sm font-semibold flex items-center gap-1.5",
                isGood ? "bg-green-100 text-green-700" : "bg-orange-100 text-orange-700",
              )}
            >
              {isGood ? (
                <CheckCircle className="w-4 h-4" />
              ) : (
                <AlertCircle className="w-4 h-4" />
              )}
              <span>{isGood ? "优点" : "待改进"}</span>
            </div>

            {stageName && (
              <span className="px-3 py-1.5 rounded-full bg-slate-100 text-slate-700 text-sm font-medium">
                {stageName}
              </span>
            )}

            {issueFamilyLabel && (
              <span className="px-3 py-1.5 rounded-full bg-white text-slate-700 text-sm font-medium border border-slate-200">
                {issueFamilyLabel}
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
                getScoreColor(highlight.score),
              )}
            >
              {highlight.score}分
            </div>
          )}
        </div>

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

        <div className="p-4 bg-slate-50 rounded-xl">
          <div className="flex items-center gap-2 mb-2 text-slate-500 text-sm">
            <MessageCircle className="w-4 h-4" />
            <span>{formatRoleLabel(highlight.role)}</span>
            <span>·</span>
            <span>{formatTime(highlight.timestamp)}</span>
          </div>
          <p className="text-base leading-relaxed text-slate-800">{highlight.content}</p>
        </div>

        {reason && (
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
            <p className="text-xs font-semibold text-amber-700 mb-1">为什么值得复盘</p>
            <p className="text-sm text-amber-900">{reason}</p>
          </div>
        )}

        {(linkedIssue || linkedGoal) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {linkedIssue && (
              <div className="rounded-xl border border-orange-200 bg-orange-50/70 p-4">
                <p className="text-xs font-semibold text-orange-700 mb-2">关联问题</p>
                <p className="text-sm text-orange-900">{linkedIssue.issue_text}</p>
                {linkedIssue.recovery_rule ? (
                  <p className="text-xs text-orange-700 mt-2">修正动作：{linkedIssue.recovery_rule}</p>
                ) : null}
              </div>
            )}
            {linkedGoal && (
              <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-4">
                <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
                  <p className="text-xs font-semibold text-blue-700">下一轮目标</p>
                  {goalTypeLabel ? (
                    <span className="text-xs rounded-full border border-blue-200 bg-white/80 px-2 py-1 text-blue-700">
                      {goalTypeLabel}
                    </span>
                  ) : null}
                </div>
                <p className="text-sm text-blue-900">{linkedGoal.goal_text}</p>
                {linkedGoal.rule ? (
                  <p className="text-xs text-blue-700 mt-2">判定条件：{linkedGoal.rule}</p>
                ) : null}
              </div>
            )}
          </div>
        )}

        {highlight.ai_feedback && (
          <div className="p-4 bg-blue-50 rounded-xl border border-blue-200">
            <p className="text-sm text-blue-700">
              <span className="font-semibold">AI 反馈：</span>
              {highlight.ai_feedback}
            </p>
          </div>
        )}

        {suggestedResponse && (
          <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200">
            <p className="text-xs font-semibold text-emerald-700 mb-1">更好的回应</p>
            <p className="text-sm text-emerald-900">{suggestedResponse}</p>
          </div>
        )}

        <div className="space-y-3">
          <p className="text-sm font-semibold text-slate-700">对话上下文</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <ContextMessageCard label="prev" message={context.prev_message} />
            <ContextMessageCard label="next" message={context.next_message} />
          </div>
          {!context.prev_message && !context.next_message && (
            <p className="text-sm text-slate-500 italic">暂无上下文信息</p>
          )}
        </div>

        <div className="flex justify-end pt-2">
          <Button variant="outline" onClick={onClose} className="min-w-[88px] min-h-[44px]">
            关闭
          </Button>
        </div>
      </div>
    </GlassModal>
  );
}
