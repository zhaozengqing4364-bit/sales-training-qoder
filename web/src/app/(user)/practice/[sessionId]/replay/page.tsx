"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { ReplayData, ReplayMessage, HighlightItem } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  Clock,
  Loader2,
  MessageSquare,
  Sparkles,
  Target,
  User,
} from "lucide-react";
import { HighlightList } from "@/components/highlights";

function formatDuration(ms: number): string {
  const safe = Math.max(0, Math.floor(ms || 0));
  const totalSeconds = Math.floor(safe / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}分${seconds.toString().padStart(2, "0")}秒`;
}

function formatTime(value?: string): string {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export default function SessionReplayPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [messages, setMessages] = useState<ReplayMessage[]>([]);
  const [highlights, setHighlights] = useState<HighlightItem[]>([]);

  useEffect(() => {
    let cancelled = false;

    const loadReplayData = async () => {
      setIsLoading(true);
      setError(null);

      const [replayResult, messagesResult, highlightsResult] = await Promise.allSettled([
        api.sessions.getReplay(sessionId),
        api.sessions.getMessages(sessionId, 1, 100),
        api.sessions.getHighlights(sessionId),
      ]);

      if (cancelled) return;

      if (replayResult.status === "fulfilled") {
        setReplayData(replayResult.value);
        setMessages(replayResult.value.messages || []);
      }

      if (messagesResult.status === "fulfilled") {
        setMessages(messagesResult.value.messages || []);
      }

      if (highlightsResult.status === "fulfilled") {
        const highlightsData = highlightsResult.value;
        const highlightItems = highlightsData.highlights || [];
        const highlightMessages = messagesResult.status === "fulfilled"
          ? (messagesResult.value.messages || [])
          : (replayResult.status === "fulfilled" ? (replayResult.value.messages || []) : []);
        const enrichedHighlights = highlightItems.map((hl: HighlightItem) => {
          // Find corresponding message to get audio URL
          const relatedMessage = highlightMessages.find(
            (msg: ReplayMessage) => msg.id === hl.id
          );
          const relatedScore = relatedMessage?.score_snapshot?.overall_score
            ?? relatedMessage?.score_snapshot?.overall
            ?? null;
          return {
            ...hl,
            audio_url: relatedMessage?.audio_url || null,
            score: relatedScore,
          };
        });
        setHighlights(enrichedHighlights);
      }

      if (
        replayResult.status === "rejected"
        && messagesResult.status === "rejected"
        && highlightsResult.status === "rejected"
      ) {
        setError(getApiErrorMessage(replayResult.reason));
      }

      setIsLoading(false);
    };

    loadReplayData();

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const totalGood = highlights.filter((h) => h.highlight_type === "good").length;
  const totalBad = highlights.filter((h) => h.highlight_type === "bad").length;

  const handleJumpToMessage = (turnNumber: number) => {
    const messageElement = document.querySelector(`[data-turn-number="${turnNumber}"]`);
    if (messageElement) {
      messageElement.scrollIntoView({ behavior: "smooth", block: "center" });
      // Add highlight animation
      messageElement.classList.add("bg-yellow-100");
      setTimeout(() => {
        messageElement.classList.remove("bg-yellow-100");
      }, 2000);
    }
  };

  if (isLoading) {
    return (
      <div className="p-4 sm:p-6 max-w-5xl mx-auto space-y-4">
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 className="w-4 h-4 animate-spin" />
          加载会话回放中...
        </div>
        <div className="h-24 rounded-2xl bg-white/60 animate-pulse" />
        <div className="h-64 rounded-2xl bg-white/60 animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 sm:p-6 max-w-5xl mx-auto space-y-4">
        <div className="text-red-600 text-sm">{error}</div>
        <Button variant="outline" onClick={() => router.back()}>
          返回
        </Button>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto space-y-6">
      {/* Navigation */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <Button variant="ghost" className="pl-0" onClick={() => router.push("/history")}>
          <ArrowLeft className="w-4 h-4 mr-1" />
          返回历史
        </Button>
        <Link href={`/practice/${sessionId}/report`}>
          <Button variant="outline">查看报告</Button>
        </Link>
      </div>

      {/* Session Info Card */}
      <GlassCard className="p-4 sm:p-5">
        <h1 className="text-xl sm:text-2xl font-black text-slate-900">会话回放</h1>
        <p className="text-sm text-slate-500 mt-1">Session ID: {sessionId}</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 mt-4">
          <div>
            <div className="text-xs text-slate-500">智能体</div>
            <div className="font-bold text-slate-900 mt-1 text-sm sm:text-base">
              {replayData?.agent_name || "--"}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500">角色画像</div>
            <div className="font-bold text-slate-900 mt-1 text-sm sm:text-base">
              {replayData?.persona_name || "--"}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500">总时长</div>
            <div className="font-bold text-slate-900 mt-1 text-sm sm:text-base">
              {formatDuration(replayData?.total_duration_ms || 0)}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500">消息数</div>
            <div className="font-bold text-slate-900 mt-1 text-sm sm:text-base">
              {messages.length}
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Voice Policy Snapshot Card */}
      {replayData?.voice_policy_snapshot_ref ? (
        <GlassCard className="p-4 sm:p-5">
          <h2 className="font-bold text-slate-900 mb-3 text-base sm:text-lg">
            策略快照基线
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4 text-sm">
            <div>
              <div className="text-xs text-slate-500">语音模式</div>
              <div className="font-semibold text-slate-900 mt-1">
                {replayData.voice_policy_snapshot_ref.voice_mode || "--"}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Runtime Profile</div>
              <div className="font-semibold text-slate-900 mt-1 break-all">
                {replayData.voice_policy_snapshot_ref.runtime_profile_id || "--"}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">解析时间</div>
              <div className="font-semibold text-slate-900 mt-1">
                {formatTime(replayData.voice_policy_snapshot_ref.resolved_at || undefined)}
              </div>
            </div>
          </div>
          <div className="mt-3 text-xs text-slate-500">
            来源链路：
            {Object.entries(replayData.voice_policy_snapshot_ref.source || {})
              .map(([key, value]) => `${key}:${value}`)
              .join(" / ") || "--"}
          </div>
        </GlassCard>
      ) : null}

      {/* Highlights Section - Using new HighlightList component */}
      {highlights.length > 0 && (
        <GlassCard className="p-4 sm:p-5">
          <div className="flex items-center gap-2 mb-3 sm:mb-4">
            <Sparkles className="w-4 h-4 text-amber-500" />
            <h2 className="font-bold text-slate-900 text-base sm:text-lg">
              高光片段
            </h2>
            <span className="text-sm text-slate-500">({highlights.length} 条)</span>
          </div>
          <HighlightList
            highlights={highlights}
            totalGood={totalGood}
            totalBad={totalBad}
            onJumpToMessage={handleJumpToMessage}
          />
        </GlassCard>
      )}

      {/* Complete Conversation Section */}
      <GlassCard className="p-4 sm:p-5">
        <div className="flex items-center gap-2 mb-3 sm:mb-4">
          <MessageSquare className="w-4 h-4 text-blue-600" />
          <h2 className="font-bold text-slate-900 text-base sm:text-lg">
            完整对话
          </h2>
          <span className="text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-700">
            {messages.length} 条
          </span>
        </div>

        {messages.length === 0 ? (
          <div className="text-sm text-slate-500">暂无可回放消息。</div>
        ) : (
          <div className="space-y-3">
            {messages.map((message) => {
              const overallScore = message.score_snapshot?.overall_score
                ?? message.score_snapshot?.overall
                ?? null;
              return (
                <div
                  key={message.id}
                  data-turn-number={message.turn_number}
                  className="rounded-xl border border-slate-100 p-3 sm:p-4 transition-all duration-300"
                >
                  <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          message.role === "assistant"
                            ? "bg-green-100 text-green-700"
                            : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {message.role === "assistant" ? "AI" : "用户"}
                      </span>
                      <span>#{message.turn_number}</span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatTime(message.timestamp)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      {message.is_highlight ? (
                        <span className="inline-flex items-center gap-1 text-amber-600">
                          <Target className="w-3 h-3" /> 高光
                        </span>
                      ) : null}
                      {message.audio_url ? (
                        <span className="inline-flex items-center gap-1">
                          <User className="w-3 h-3" /> 有音频
                        </span>
                      ) : null}
                      {overallScore !== null && (
                        <span
                          className={`px-2 py-0.5 rounded-full font-medium ${
                            overallScore >= 80
                              ? "text-green-700 bg-green-50"
                              : overallScore >= 60
                                ? "text-yellow-700 bg-yellow-50"
                                : "text-red-700 bg-red-50"
                          }`}
                        >
                          {overallScore}分
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-sm leading-relaxed text-slate-700">
                    {message.content}
                  </div>
                  {message.ai_feedback ? (
                    <div className="mt-2 text-xs text-slate-500 bg-slate-50 rounded-lg px-2 py-1">
                      AI 点评：{message.ai_feedback}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </GlassCard>
    </div>
  );
}
