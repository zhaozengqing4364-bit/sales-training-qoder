"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
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
import { HighlightItem, ReplayAnchorStatus, ReplayData, ReplayHighlightContext, ReplayLearningEvidence, ReplayTimelineMarker } from "@/lib/api/types";
import { debug } from "@/lib/debug";
import {
  extractSessionClaimTruth,
  formatClaimTruthEvidenceNote,
  formatClaimTruthSummary,
  formatEvidenceCompletenessNote,
  formatGoalTypeLabel,
  formatIssueTypeLabel,
  formatNotEvaluableReason,
  formatSessionStageLabel,
  getClaimTruthTone,
  type SessionClaimTruthTone,
} from "@/lib/session-evidence";
import { cn } from "@/lib/utils";

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

function getClaimTruthClasses(tone: SessionClaimTruthTone) {
  if (tone === "critical") {
    return {
      card: "border-rose-200 bg-rose-50/80",
      badge: "text-rose-700 bg-white/80 border-rose-200",
      text: "text-rose-900",
      note: "text-rose-700",
    };
  }

  if (tone === "warning") {
    return {
      card: "border-amber-200 bg-amber-50/80",
      badge: "text-amber-700 bg-white/80 border-amber-200",
      text: "text-amber-900",
      note: "text-amber-700",
    };
  }

  if (tone === "verified") {
    return {
      card: "border-emerald-200 bg-emerald-50/80",
      badge: "text-emerald-700 bg-white/80 border-emerald-200",
      text: "text-emerald-900",
      note: "text-emerald-700",
    };
  }

  return {
    card: "border-blue-200 bg-blue-50/80",
    badge: "text-blue-700 bg-white/80 border-blue-200",
    text: "text-blue-900",
    note: "text-blue-700",
  };
}

type ReplayDeepLinkFocus = "main_issue" | "next_goal" | "learning_evidence";
type ReplayAnchorNoticeTone = "info" | "warning";

interface ReplayDeepLinkRequest {
  focus: ReplayDeepLinkFocus | null;
  messageId: string | null;
  turnNumber: number | null;
  anchorStatus: ReplayAnchorStatus | null;
  anchorReason: string | null;
  markerType: string | null;
  markerTimestampMs: number | null;
}

interface ReplayAnchorNotice {
  title: string;
  description: string;
  tone: ReplayAnchorNoticeTone;
}

function parseReplayInteger(value?: string | null): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseReplayFocus(value?: string | null): ReplayDeepLinkFocus | null {
  if (value === "main_issue" || value === "next_goal" || value === "learning_evidence") {
    return value;
  }
  return null;
}

function parseReplayAnchorStatus(value?: string | null): ReplayAnchorStatus | null {
  if (value === "resolved" || value === "degraded" || value === "missing") {
    return value;
  }
  return null;
}

function parseReplayDeepLinkRequest(searchParams: Pick<URLSearchParams, "get">): ReplayDeepLinkRequest {
  return {
    focus: parseReplayFocus(searchParams.get("focus")),
    messageId: searchParams.get("message_id") || null,
    turnNumber: parseReplayInteger(searchParams.get("turn")),
    anchorStatus: parseReplayAnchorStatus(searchParams.get("anchor_status")),
    anchorReason: searchParams.get("anchor_reason") || null,
    markerType: searchParams.get("marker_type") || null,
    markerTimestampMs: parseReplayInteger(searchParams.get("marker_timestamp_ms")),
  };
}

function getReplayFocusLabel(focus: ReplayDeepLinkFocus | null): string {
  if (focus === "main_issue") return "主问题片段";
  if (focus === "next_goal") return "目标片段";
  if (focus === "learning_evidence") return "高光片段";
  return "回放片段";
}

function getReplayAnchorNoticeClasses(tone: ReplayAnchorNoticeTone) {
  if (tone === "warning") {
    return {
      card: "border-amber-200 bg-amber-50/80",
      eyebrow: "text-amber-700",
      title: "text-amber-900",
      body: "text-amber-800",
      icon: "text-amber-600",
    };
  }

  return {
    card: "border-blue-200 bg-blue-50/80",
    eyebrow: "text-blue-700",
    title: "text-blue-900",
    body: "text-blue-800",
    icon: "text-blue-600",
  };
}

function resolveReplayMarker(
  markers: ReplayTimelineMarker[],
  request: ReplayDeepLinkRequest,
): ReplayTimelineMarker | null {
  if (!request.markerType || typeof request.markerTimestampMs !== "number") {
    return null;
  }

  return markers.find((marker) => (
    marker.type === request.markerType
    && marker.timestamp_ms === request.markerTimestampMs
  )) ?? null;
}

function buildReplayAnchorNotice(
  request: ReplayDeepLinkRequest,
  options: {
    targetFound: boolean;
    targetTurnNumber: number | null;
    marker?: ReplayTimelineMarker | null;
  },
): ReplayAnchorNotice | null {
  if (!request.focus) {
    return null;
  }

  const focusLabel = getReplayFocusLabel(request.focus);
  const turnLabel = typeof options.targetTurnNumber === "number"
    ? `第 ${options.targetTurnNumber} 轮`
    : "相关对话片段";
  const markerLabel = options.marker?.label || null;

  if (options.targetFound) {
    if (request.anchorStatus === "degraded") {
      if (request.anchorReason === "no_matching_highlight") {
        return {
          title: `已定位到${focusLabel}`,
          description: markerLabel
            ? `未找到精确高光，已定位到“${markerLabel}”阶段附近的${turnLabel}。`
            : `未找到精确高光，已定位到${turnLabel}附近。`,
          tone: "warning",
        };
      }

      if (request.anchorReason === "missing_marker") {
        return {
          title: `已定位到${focusLabel}`,
          description: `高光标记缺失，已直接定位到${turnLabel}。`,
          tone: "warning",
        };
      }
    }

    if (request.focus === "learning_evidence") {
      return {
        title: "已定位到高光片段",
        description: `已跳转到${turnLabel}。`,
        tone: "info",
      };
    }

    return {
      title: `已定位到${focusLabel}`,
      description: `已跳转到${turnLabel}${request.markerType === "highlight" ? "对应的高光片段。" : "。"}`,
      tone: request.anchorStatus === "resolved" ? "info" : "warning",
    };
  }

  if (request.anchorReason === "no_matching_highlight") {
    return {
      title: `未找到${focusLabel}`,
      description: markerLabel
        ? `报告引用的精确高光已不存在，且“${markerLabel}”阶段也没有可自动定位的回放片段；请结合完整对话继续查看。`
        : "报告引用的精确高光已不存在，页面保留完整对话供手动查找。",
      tone: "warning",
    };
  }

  if (request.anchorReason === "missing_marker") {
    return {
      title: `未找到${focusLabel}`,
      description: "报告引用的定位标记当前不存在，页面保留完整对话供手动查找。",
      tone: "warning",
    };
  }

  return {
    title: `未找到${focusLabel}`,
    description: "请求的回放片段当前不存在，页面保留完整对话供手动查找。",
    tone: "warning",
  };
}

function getReplayRoleLabel(role?: string | null): string {
  if (role === "assistant") return "AI";
  if (role === "user") return "用户";
  return "对话";
}

function getReplayEvidenceReason(
  learningEvidence?: ReplayLearningEvidence | null,
  fallbackReason?: string | null,
  fallbackFeedback?: string | null,
): string | null {
  return learningEvidence?.reason ?? fallbackReason ?? fallbackFeedback ?? null;
}

function getReplayStageName({
  learningEvidence,
  stageName,
  salesStage,
}: {
  learningEvidence?: ReplayLearningEvidence | null;
  stageName?: string | null;
  salesStage?: string | null;
}): string | null {
  return stageName
    ?? learningEvidence?.stage?.name
    ?? (salesStage ? formatSessionStageLabel(salesStage) : null);
}

function getReplayIssueFamilyLabel(
  learningEvidence?: ReplayLearningEvidence | null,
): string | null {
  return formatIssueTypeLabel(learningEvidence?.issue_family ?? null);
}

function getReplaySuggestedResponse(
  learningEvidence?: ReplayLearningEvidence | null,
  fallbackSuggestedResponse?: string | null,
): string | null {
  return learningEvidence?.suggested_response ?? fallbackSuggestedResponse ?? null;
}

function getReplayNearbyContext(
  learningEvidence?: ReplayLearningEvidence | null,
  fallbackContext?: ReplayHighlightContext | null,
): ReplayHighlightContext | null {
  return learningEvidence?.nearby_context ?? fallbackContext ?? null;
}

function hasReplayContext(context?: ReplayHighlightContext | null): boolean {
  return Boolean(context?.prev_message || context?.next_message);
}

function ReplayContextPreview({
  label,
  message,
}: {
  label: string;
  message?: ReplayHighlightContext["prev_message"];
}) {
  if (!message) return null;

  return (
    <div className="rounded-lg border border-white/70 bg-white/70 px-3 py-2">
      <div className="flex items-center justify-between gap-3 mb-1 flex-wrap">
        <span className="text-[11px] font-semibold text-slate-500">{label}</span>
        <span className="text-[11px] rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">
          {getReplayRoleLabel(message.role)}
        </span>
      </div>
      <p className="text-sm text-slate-700 leading-relaxed">{message.content || "--"}</p>
    </div>
  );
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
    const relatedContext = getReplayNearbyContext(
      relatedMessage?.learning_evidence,
      hasReplayContext(highlight.context) ? highlight.context : null,
    );

    return {
      ...highlight,
      sales_stage: highlight.sales_stage ?? relatedMessage?.sales_stage ?? null,
      stage_name: getReplayStageName({
        learningEvidence: highlight.learning_evidence ?? relatedMessage?.learning_evidence,
        stageName: highlight.stage_name ?? relatedMessage?.stage_name ?? relatedMessage?.score_snapshot?.stage_name ?? null,
        salesStage: highlight.sales_stage ?? relatedMessage?.sales_stage ?? null,
      }),
      suggested_response: getReplaySuggestedResponse(
        highlight.learning_evidence ?? relatedMessage?.learning_evidence,
        highlight.suggested_response ?? relatedMessage?.suggested_response ?? null,
      ),
      context: relatedContext ?? highlight.context,
      learning_evidence: highlight.learning_evidence ?? relatedMessage?.learning_evidence ?? null,
      audio_url: highlight.audio_url ?? relatedMessage?.audio_url ?? null,
      score: relatedScore,
    };
  });
}

export default function SessionReplayPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const sessionId = params.sessionId as string;

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [highlights, setHighlights] = useState<HighlightItem[]>([]);
  const [highlightsUnavailableHint, setHighlightsUnavailableHint] = useState<string | null>(null);
  const [activeTurnNumber, setActiveTurnNumber] = useState<number | null>(null);
  const [replayAnchorNotice, setReplayAnchorNotice] = useState<ReplayAnchorNotice | null>(null);

  const replayDeepLink = useMemo(
    () => parseReplayDeepLinkRequest(searchParams),
    [searchParams],
  );

  useEffect(() => {
    let cancelled = false;

    const loadReplayData = async () => {
      setIsLoading(true);
      setError(null);
      setReplayData(null);
      setHighlights([]);
      setHighlightsUnavailableHint(null);
      setActiveTurnNumber(null);
      setReplayAnchorNotice(null);

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
  const claimTruth = extractSessionClaimTruth(replayData?.effectiveness_snapshot);
  const claimTruthSummary = formatClaimTruthSummary(claimTruth);
  const claimTruthEvidenceNote = formatClaimTruthEvidenceNote(claimTruth);
  const claimTruthClasses = getClaimTruthClasses(getClaimTruthTone(claimTruth?.status));

  const handleJumpToMessage = useCallback((turnNumber: number) => {
    setActiveTurnNumber(turnNumber);
    const messageElement = document.querySelector(`[data-turn-number="${turnNumber}"]`);
    if (messageElement instanceof HTMLElement && typeof messageElement.scrollIntoView === "function") {
      messageElement.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, []);

  useEffect(() => {
    if (!replayData) {
      return;
    }

    if (!replayDeepLink.focus) {
      setReplayAnchorNotice(null);
      return;
    }

    const targetMessage = (
      replayDeepLink.messageId
        ? replayData.messages.find((message) => message.id === replayDeepLink.messageId)
        : null
    ) ?? (
      typeof replayDeepLink.turnNumber === "number"
        ? replayData.messages.find((message) => message.turn_number === replayDeepLink.turnNumber)
        : null
    );
    const resolvedMarker = resolveReplayMarker(replayData.timeline_markers || [], replayDeepLink);
    const targetTurnNumber = targetMessage?.turn_number ?? replayDeepLink.turnNumber;
    const notice = buildReplayAnchorNotice(replayDeepLink, {
      targetFound: Boolean(targetMessage),
      targetTurnNumber,
      marker: resolvedMarker,
    });

    setReplayAnchorNotice(notice);

    if (targetMessage) {
      handleJumpToMessage(targetMessage.turn_number);
    } else {
      setActiveTurnNumber(null);
    }

    debug.log("[Replay] Applied report anchor deep link", {
      sessionId,
      focus: replayDeepLink.focus,
      requestedMessageId: replayDeepLink.messageId,
      requestedTurnNumber: replayDeepLink.turnNumber,
      anchorStatus: replayDeepLink.anchorStatus,
      anchorReason: replayDeepLink.anchorReason,
      markerType: replayDeepLink.markerType,
      markerTimestampMs: replayDeepLink.markerTimestampMs,
      targetFound: Boolean(targetMessage),
      resolvedTurnNumber: targetMessage?.turn_number ?? null,
      resolvedMarkerLabel: resolvedMarker?.label ?? null,
    });
  }, [handleJumpToMessage, replayData, replayDeepLink, sessionId]);

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

      {replayAnchorNotice && (() => {
        const noticeClasses = getReplayAnchorNoticeClasses(replayAnchorNotice.tone);
        return (
          <GlassCard
            data-testid="replay-anchor-banner"
            className={cn("p-4 sm:p-5 border", noticeClasses.card)}
          >
            <div className="flex items-start gap-3">
              <Target className={cn("w-5 h-5 mt-0.5", noticeClasses.icon)} />
              <div>
                <p className={cn("text-xs font-semibold", noticeClasses.eyebrow)}>
                  来自报告的定位请求
                </p>
                <h2 className={cn("font-semibold mt-1", noticeClasses.title)}>
                  {replayAnchorNotice.title}
                </h2>
                <p className={cn("text-sm mt-1", noticeClasses.body)}>
                  {replayAnchorNotice.description}
                </p>
              </div>
            </div>
          </GlassCard>
        );
      })()}

      {claimTruth && claimTruthSummary && (
        <GlassCard className={cn("p-4 sm:p-5 border", claimTruthClasses.card)}>
          <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
            <h2 className="font-bold text-slate-900 text-base sm:text-lg">主张证据状态</h2>
            <span className={cn("inline-flex rounded-full border px-2.5 py-1 text-xs font-medium", claimTruthClasses.badge)}>
              {claimTruth.label}
            </span>
          </div>
          <p className={cn("text-sm", claimTruthClasses.text)}>{claimTruthSummary}</p>
          {claimTruthEvidenceNote ? (
            <p className={cn("text-xs mt-2", claimTruthClasses.note)}>{claimTruthEvidenceNote}</p>
          ) : null}
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
              const learningEvidence = message.learning_evidence ?? null;
              const stageName = getReplayStageName({
                learningEvidence,
                stageName: message.stage_name ?? message.score_snapshot?.stage_name ?? null,
                salesStage: message.sales_stage ?? null,
              });
              const issueFamilyLabel = getReplayIssueFamilyLabel(learningEvidence);
              const evidenceReason = getReplayEvidenceReason(
                learningEvidence,
                message.highlight_reason ?? null,
                message.ai_feedback ?? null,
              );
              const suggestedResponse = getReplaySuggestedResponse(
                learningEvidence,
                message.suggested_response ?? null,
              );
              const nearbyContext = getReplayNearbyContext(learningEvidence);
              const linkedIssue = learningEvidence?.linked_issue ?? null;
              const linkedGoal = learningEvidence?.linked_goal ?? null;
              const linkedGoalTypeLabel = formatGoalTypeLabel(linkedGoal?.goal_type ?? null);
              const hasLearningEvidence = Boolean(
                evidenceReason
                || stageName
                || issueFamilyLabel
                || suggestedResponse
                || linkedIssue
                || linkedGoal
                || hasReplayContext(nearbyContext),
              );

              return (
                <div
                  key={message.id}
                  data-turn-number={message.turn_number}
                  className={cn(
                    "rounded-xl border border-slate-100 p-3 sm:p-4 transition-all duration-300",
                    activeTurnNumber === message.turn_number
                      && "border-blue-300 bg-blue-50/70 shadow-[0_0_0_1px_rgba(59,130,246,0.2)]",
                  )}
                >
                  <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
                    <div className="flex items-center gap-2 text-xs text-slate-500 flex-wrap">
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
                      {stageName ? (
                        <span className="inline-flex rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                          {stageName}
                        </span>
                      ) : null}
                      {issueFamilyLabel ? (
                        <span className="inline-flex rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-700">
                          {issueFamilyLabel}
                        </span>
                      ) : null}
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
                  {message.is_highlight && hasLearningEvidence ? (
                    <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50/70 p-3 space-y-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-semibold text-amber-700">学习证据</span>
                        {stageName ? (
                          <span className="text-[11px] rounded-full bg-white/80 px-2 py-1 text-slate-700 border border-amber-100">
                            {stageName}
                          </span>
                        ) : null}
                        {issueFamilyLabel ? (
                          <span className="text-[11px] rounded-full bg-white/80 px-2 py-1 text-slate-700 border border-amber-100">
                            {issueFamilyLabel}
                          </span>
                        ) : null}
                      </div>

                      {evidenceReason ? (
                        <div>
                          <p className="text-xs font-semibold text-amber-700 mb-1">为什么这轮关键</p>
                          <p className="text-sm text-amber-900">{evidenceReason}</p>
                        </div>
                      ) : null}

                      {(linkedIssue || linkedGoal) ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {linkedIssue ? (
                            <div className="rounded-lg border border-white/70 bg-white/70 px-3 py-3">
                              <p className="text-xs font-semibold text-slate-500 mb-1">关联问题</p>
                              <p className="text-sm text-slate-800">{linkedIssue.issue_text}</p>
                            </div>
                          ) : null}
                          {linkedGoal ? (
                            <div className="rounded-lg border border-white/70 bg-white/70 px-3 py-3">
                              <div className="flex items-center justify-between gap-2 mb-1 flex-wrap">
                                <p className="text-xs font-semibold text-slate-500">下一轮目标</p>
                                {linkedGoalTypeLabel ? (
                                  <span className="text-[11px] rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">
                                    {linkedGoalTypeLabel}
                                  </span>
                                ) : null}
                              </div>
                              <p className="text-sm text-slate-800">{linkedGoal.goal_text}</p>
                            </div>
                          ) : null}
                        </div>
                      ) : null}

                      {suggestedResponse ? (
                        <div>
                          <p className="text-xs font-semibold text-emerald-700 mb-1">更优回应</p>
                          <p className="text-sm text-emerald-900">{suggestedResponse}</p>
                        </div>
                      ) : null}

                      {hasReplayContext(nearbyContext) ? (
                        <div className="space-y-2">
                          <p className="text-xs font-semibold text-slate-500">关联上下文</p>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            <ReplayContextPreview label="前一轮" message={nearbyContext?.prev_message} />
                            <ReplayContextPreview label="后一轮" message={nearbyContext?.next_message} />
                          </div>
                        </div>
                      ) : null}
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
