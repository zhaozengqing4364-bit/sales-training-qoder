"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  Clock,
  Loader2,
  MessageSquare,
  Sparkles,
  Target,
  User,
} from "lucide-react";

import { HighlightList } from "@/components/highlights";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { HighlightItem, ReplayData } from "@/lib/api/types";
import { debug } from "@/lib/debug";
import {
  formatEvidenceCompletenessNote,
  formatGoalTypeLabel,
  formatIssueTypeLabel,
  formatNotEvaluableReason,
  formatSessionStageLabel,
} from "@/lib/session-evidence";

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

function enrichHighlights(
  highlights: HighlightItem[],
  replayData: ReplayData,
): HighlightItem[] {
  const messages = replayData.messages || [];
  return highlights.map((highlight) => {
    const relatedMessage = messages.find((message) => message.id === highlight.id);
    const relatedScore = relatedMessage?.score_snapshot?.overall_score
      ?? relatedMessage?.score_snapshot?.overall
      ?? highlight.score
      ?? null;

    return {
      ...highlight,
      audio_url: highlight.audio_url ?? relatedMessage?.audio_url ?? null,
      score: relatedScore,
    };
  });
}

export default function SessionReplayPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [highlights, setHighlights] = useState<HighlightItem[]>([]);
  const [highlightsUnavailableHint, setHighlightsUnavailableHint] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadReplayData = async () => {
      setIsLoading(true);
      setError(null);
      setReplayData(null);
      setHighlights([]);
      setHighlightsUnavailableHint(null);

      try {
        const replay = await api.sessions.getReplay(sessionId);
        if (cancelled) return;

        setReplayData(replay);
        debug.log("[Replay] Loaded unified evidence contract", {
          sessionId,
          overallScore: replay.overall_score,
          evaluable: replay.evaluable,
          notEvaluableReason: replay.not_evaluable_reason,
          messageCount: replay.messages.length,
          evidenceComplete: replay.evidence_completeness?.complete,
        });

        try {
          const highlightsData = await api.sessions.getHighlights(sessionId);
          if (cancelled) return;

          const highlightItems = Array.isArray(highlightsData.highlights)
            ? highlightsData.highlights
            : [];
          setHighlights(enrichHighlights(highlightItems, replay));
          debug.log("[Replay] Highlights loaded", {
            sessionId,
            highlightCount: highlightItems.length,
          });
        } catch (highlightsError) {
          if (cancelled) return;
          setHighlights([]);
          setHighlightsUnavailableHint("高光片段暂不可用，当前页面仍展示统一训练证据。");
          debug.warn("[Replay] Highlights unavailable; keeping unified evidence", {
            sessionId,
            error: highlightsError,
          });
        }
      } catch (loadError) {
        if (cancelled) return;
        setError(`统一训练证据加载失败：${getApiErrorMessage(loadError)}`);
        debug.error("[Replay] Unified evidence contract load failed", {
          sessionId,
          error: loadError,
        });
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadReplayData();

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const totalGood = useMemo(
    () => highlights.filter((highlight) => highlight.highlight_type === "good").length,
    [highlights],
  );
  const totalBad = useMemo(
    () => highlights.filter((highlight) => highlight.highlight_type === "bad").length,
    [highlights],
  );

  const evidenceCompletenessNote = formatEvidenceCompletenessNote(
    replayData?.evidence_completeness,
  );
  const notEvaluableReasonText = formatNotEvaluableReason(
    replayData?.not_evaluable_reason,
  );
  const mainIssueTypeLabel = formatIssueTypeLabel(replayData?.main_issue?.issue_type);
  const nextGoalTypeLabel = formatGoalTypeLabel(replayData?.next_goal?.goal_type);

  const handleJumpToMessage = (turnNumber: number) => {
    const messageElement = document.querySelector(`[data-turn-number="${turnNumber}"]`);
    if (messageElement) {
      messageElement.scrollIntoView({ behavior: "smooth", block: "center" });
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
          加载统一训练证据中...
        </div>
        <div className="h-24 rounded-2xl bg-white/60 animate-pulse" />
        <div className="h-64 rounded-2xl bg-white/60 animate-pulse" />
      </div>
    );
  }

  if (error || !replayData) {
    return (
      <div className="p-4 sm:p-6 max-w-5xl mx-auto space-y-4">
        <GlassCard className="p-6 border border-amber-200 bg-amber-50/80">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5" />
            <div>
              <h1 className="font-semibold text-amber-900">统一训练证据不可用</h1>
              <p className="text-sm text-amber-800 mt-1">{error || "未找到可回放的统一训练证据。"}</p>
            </div>
          </div>
        </GlassCard>
        <Button variant="outline" onClick={() => router.push("/history")}>
          返回历史
        </Button>
      </div>
    );
  }

  const messages = replayData.messages || [];

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <Button variant="ghost" className="pl-0" onClick={() => router.push("/history")}>
          <ArrowLeft className="w-4 h-4 mr-1" />
          返回历史
        </Button>
        <Link href={`/practice/${sessionId}/report`}>
          <Button variant="outline">查看报告</Button>
        </Link>
      </div>

      <GlassCard className="p-4 sm:p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-slate-900">会话回放</h1>
            <p className="text-sm text-slate-500 mt-1">Session ID: {sessionId}</p>
            <p className="text-xs text-slate-500 mt-2">本页消息与评分均直接来自统一训练证据 contract。</p>
          </div>
          <div className="text-right">
            <div data-testid="replay-overall-score" className="text-4xl font-black text-blue-600">
              {Math.round(replayData.overall_score)}
            </div>
            <div className="text-xs text-slate-500 mt-1">统一训练证据评分</div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 mt-4">
          <div>
            <div className="text-xs text-slate-500">智能体</div>
            <div className="font-bold text-slate-900 mt-1 text-sm sm:text-base">
              {replayData.agent_name || "--"}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500">角色画像</div>
            <div className="font-bold text-slate-900 mt-1 text-sm sm:text-base">
              {replayData.persona_name || "--"}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500">总时长</div>
            <div className="font-bold text-slate-900 mt-1 text-sm sm:text-base">
              {formatDuration(replayData.total_duration_ms || 0)}
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

      {replayData.evaluable === false && (
        <GlassCard className="p-4 sm:p-5 border border-amber-200 bg-amber-50/80">
          <h2 className="font-semibold text-amber-900">当前会话暂不可评估</h2>
          <p className="text-sm text-amber-800 mt-2">{notEvaluableReasonText}</p>
          {evidenceCompletenessNote && (
            <p className="text-xs text-amber-700 mt-2">{evidenceCompletenessNote}</p>
          )}
        </GlassCard>
      )}

      {replayData.evaluable !== false && evidenceCompletenessNote && (
        <GlassCard className="p-4 border border-blue-200 bg-blue-50/80">
          <p className="text-sm text-blue-800">{evidenceCompletenessNote}</p>
        </GlassCard>
      )}

      {highlightsUnavailableHint && (
        <GlassCard className="p-4 border border-slate-200 bg-slate-50/80">
          <p className="text-sm text-slate-700">{highlightsUnavailableHint}</p>
        </GlassCard>
      )}

      {(replayData.main_issue || replayData.next_goal) && (
        <GlassCard className="p-4 sm:p-5">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-blue-600" />
            <h2 className="font-bold text-slate-900 text-base sm:text-lg">本场教练结论</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {replayData.main_issue ? (
              <div className="rounded-xl border border-amber-100 bg-amber-50/80 p-4">
                <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
                  <p className="text-xs font-semibold text-amber-700">主问题</p>
                  {mainIssueTypeLabel ? (
                    <span className="inline-flex rounded-full border border-amber-200 bg-white/70 px-2.5 py-1 text-xs font-medium text-amber-800">
                      {mainIssueTypeLabel}
                    </span>
                  ) : null}
                </div>
                <p className="text-sm text-amber-900">{replayData.main_issue.issue_text}</p>
                <p className="text-xs text-amber-700 mt-2">
                  修正动作：{replayData.main_issue.recovery_rule}
                </p>
              </div>
            ) : null}

            {replayData.next_goal ? (
              <div className="rounded-xl border border-blue-100 bg-blue-50/80 p-4">
                <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
                  <p className="text-xs font-semibold text-blue-700">下一轮目标</p>
                  {nextGoalTypeLabel ? (
                    <span className="inline-flex rounded-full border border-blue-200 bg-white/70 px-2.5 py-1 text-xs font-medium text-blue-800">
                      {nextGoalTypeLabel}
                    </span>
                  ) : null}
                </div>
                <p className="text-sm text-blue-900">{replayData.next_goal.goal_text}</p>
                <p className="text-xs text-blue-700 mt-2">
                  判定条件：{replayData.next_goal.rule}
                </p>
              </div>
            ) : null}
          </div>
        </GlassCard>
      )}

      {Array.isArray(replayData.stage_summary) && replayData.stage_summary.length > 0 && (
        <GlassCard className="p-4 sm:p-5">
          <div className="flex items-center gap-2 mb-3">
            <Target className="w-4 h-4 text-blue-600" />
            <h2 className="font-bold text-slate-900 text-base sm:text-lg">阶段证据</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {replayData.stage_summary.map((stage) => (
              <div key={`${stage.stage}-${stage.duration_ms}`} className="rounded-xl border border-slate-100 bg-slate-50/80 p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-slate-900">
                    {formatSessionStageLabel(stage.stage)}
                  </span>
                  <span className="text-sm font-bold text-blue-600">
                    {Math.round(stage.score)} 分
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  停留时长：{formatDuration(stage.duration_ms)}
                </p>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      {replayData.voice_policy_snapshot_ref ? (
        <GlassCard className="p-4 sm:p-5">
          <h2 className="font-bold text-slate-900 mb-3 text-base sm:text-lg">策略快照基线</h2>
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

      {highlights.length > 0 ? (
        <GlassCard className="p-4 sm:p-5">
          <div className="flex items-center gap-2 mb-3 sm:mb-4">
            <Sparkles className="w-4 h-4 text-amber-500" />
            <h2 className="font-bold text-slate-900 text-base sm:text-lg">高光片段</h2>
            <span className="text-sm text-slate-500">({highlights.length} 条)</span>
          </div>
          <HighlightList
            highlights={highlights}
            totalGood={totalGood}
            totalBad={totalBad}
            onJumpToMessage={handleJumpToMessage}
          />
        </GlassCard>
      ) : !highlightsUnavailableHint ? (
        <GlassCard className="p-4 sm:p-5 border border-dashed border-slate-200 bg-slate-50/60">
          <p className="text-sm text-slate-500">当前会话暂无已标记高光片段。</p>
        </GlassCard>
      ) : null}

      <GlassCard className="p-4 sm:p-5">
        <div className="flex items-center gap-2 mb-3 sm:mb-4">
          <MessageSquare className="w-4 h-4 text-blue-600" />
          <h2 className="font-bold text-slate-900 text-base sm:text-lg">完整对话</h2>
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
                          {Math.round(overallScore)}分
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-sm leading-relaxed text-slate-700">{message.content}</div>
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
