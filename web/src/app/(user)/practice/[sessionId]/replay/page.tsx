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
import { AudioAuditCardWithSession as AudioAuditCard } from "@/components/audio/AudioAuditCard";
import { SlideViewer } from "@/components/practice/presentation/SlideViewer";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { HighlightItem, PracticeSessionReport, ReplayAnchorStatus, ReplayData, ReplayHighlightContext, ReplayLearningEvidence, ReplayTimelineMarker } from "@/lib/api/types";
import { debug } from "@/lib/debug";
import {
  extractSessionClaimTruth,
  formatClaimTruthEvidenceNote,
  formatClaimTruthSummary,
  formatConclusionEvidenceSections,
  formatEvidenceCompletenessNote,
  formatEvidenceDegradationItems,
  formatGoalTypeLabel,
  formatIssueTypeLabel,
  formatNotEvaluableReason,
  formatPresentationDegradedNote,
  formatPresentationIssueContextLines,
  formatPresentationIssueLabel,
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

interface PresentationPageRequest {
  pageNumber: number | null;
  anchorStatus: ReplayAnchorStatus | null;
  anchorReason: string | null;
}

function parsePresentationPageRequest(
  searchParams: Pick<URLSearchParams, "get">,
): PresentationPageRequest {
  return {
    pageNumber: parseReplayInteger(searchParams.get("page")),
    anchorStatus: parseReplayAnchorStatus(searchParams.get("page_anchor_status")),
    anchorReason: searchParams.get("page_anchor_reason") || null,
  };
}

function getPresentationPageSummaries(review?: ReplayData["presentation_review"] | null) {
  return Array.isArray(review?.page_summaries) ? review.page_summaries : [];
}

function getPresentationTotalPages(review?: ReplayData["presentation_review"] | null): number {
  const diagnosticTotal = review?.diagnostics?.total_pages;
  if (typeof diagnosticTotal === "number" && diagnosticTotal >= 1) {
    return diagnosticTotal;
  }

  const maxPageNumber = getPresentationPageSummaries(review).reduce((maxPage, pageSummary) => (
    typeof pageSummary.page_number === "number" && pageSummary.page_number > maxPage
      ? pageSummary.page_number
      : maxPage
  ), 0);

  return maxPageNumber >= 1 ? maxPageNumber : 1;
}

function resolvePresentationLandingPage(
  review?: ReplayData["presentation_review"] | null,
  requestedPageNumber?: number | null,
): number | null {
  const pageSummaries = getPresentationPageSummaries(review);
  const totalPages = getPresentationTotalPages(review);
  if (typeof requestedPageNumber === "number" && requestedPageNumber >= 1 && requestedPageNumber <= totalPages) {
    return requestedPageNumber;
  }

  const firstIssuePage = pageSummaries.find(
    (pageSummary) => (pageSummary.issue_clusters?.length || 0) > 0,
  )?.page_number;
  if (typeof firstIssuePage === "number") {
    return firstIssuePage;
  }

  const firstSummaryPage = pageSummaries[0]?.page_number;
  if (typeof firstSummaryPage === "number") {
    return firstSummaryPage;
  }

  return totalPages >= 1 ? 1 : null;
}

function buildPresentationSlideFallback(
  pageSummary?: {
    summary?: string | null;
    key_points?: string[] | null;
  } | null,
): string | undefined {
  if (!pageSummary) {
    return undefined;
  }

  if (typeof pageSummary.summary === "string" && pageSummary.summary.trim()) {
    return pageSummary.summary.trim();
  }

  if (Array.isArray(pageSummary.key_points) && pageSummary.key_points.length > 0) {
    return `关键点：${pageSummary.key_points.join("、")}`;
  }

  return undefined;
}

function buildPresentationPageNotice(
  request: PresentationPageRequest,
  options: {
    resolvedPageNumber: number | null;
    pageSummaryFound: boolean;
  },
): ReplayAnchorNotice | null {
  if (request.pageNumber === null) {
    return null;
  }

  if (options.resolvedPageNumber === null) {
    return {
      title: `未找到第 ${request.pageNumber} 页`,
      description: "当前回放缺少可用的页级证据，请回到报告页查看完整复盘。",
      tone: "warning",
    };
  }

  if (
    request.anchorStatus === "missing"
    || request.anchorReason === "page_not_found"
    || request.pageNumber !== options.resolvedPageNumber
  ) {
    return {
      title: `未找到第 ${request.pageNumber} 页`,
      description: `报告引用的页码当前不存在，已回退到第 ${options.resolvedPageNumber} 页继续查看。`,
      tone: "warning",
    };
  }

  if (
    request.anchorStatus === "degraded"
    || request.anchorReason === "missing_page_summary"
    || !options.pageSummaryFound
  ) {
    return {
      title: `已打开第 ${options.resolvedPageNumber} 页`,
      description: "当前会话缺少该页的逐页回放锚点，仅展示课件内容与已确认的页级证据。",
      tone: "warning",
    };
  }

  return {
    title: `已定位到第 ${options.resolvedPageNumber} 页`,
    description: "已打开报告引用的课件页，并同步展示该页问题簇与相关回合。",
    tone: "info",
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
  const [reportSnapshot, setReportSnapshot] = useState<PracticeSessionReport | null>(null);
  const [highlights, setHighlights] = useState<HighlightItem[]>([]);
  const [highlightsUnavailableHint, setHighlightsUnavailableHint] = useState<string | null>(null);
  const [activeTurnNumber, setActiveTurnNumber] = useState<number | null>(null);
  const [activePresentationPage, setActivePresentationPage] = useState<number | null>(null);
  const [replayAnchorNotice, setReplayAnchorNotice] = useState<ReplayAnchorNotice | null>(null);
  const [presentationPageNotice, setPresentationPageNotice] = useState<ReplayAnchorNotice | null>(null);
  const [retryEntry, setRetryEntry] = useState<PracticeSessionReport["retry_entry"]>(null);
  const [retryHint, setRetryHint] = useState<string | null>(null);

  const replayDeepLink = useMemo(
    () => parseReplayDeepLinkRequest(searchParams),
    [searchParams],
  );
  const presentationPageRequest = useMemo(
    () => parsePresentationPageRequest(searchParams),
    [searchParams],
  );

  useEffect(() => {
    let cancelled = false;

    const loadReplayData = async () => {
      setIsLoading(true);
      setError(null);
      setReplayData(null);
      setReportSnapshot(null);
      setHighlights([]);
      setHighlightsUnavailableHint(null);
      setActiveTurnNumber(null);
      setActivePresentationPage(null);
      setReplayAnchorNotice(null);
      setPresentationPageNotice(null);
      setRetryEntry(null);
      setRetryHint(null);

      try {
        const [replayResult, retryReportResult] = await Promise.allSettled([
          api.sessions.getReplay(sessionId),
          api.sessions.getReport(sessionId),
        ]);

        if (replayResult.status === "rejected") {
          throw replayResult.reason;
        }

        if (cancelled) return;

        const replay = replayResult.value;
        setReplayData(replay);
        debug.log("[Replay] Loaded unified evidence contract", {
          sessionId,
          scenarioType: replay.scenario_type ?? null,
          overallScore: replay.overall_score,
          evaluable: replay.evaluable,
          notEvaluableReason: replay.not_evaluable_reason,
          messageCount: replay.messages.length,
          evidenceComplete: replay.evidence_completeness?.complete,
          presentationReviewAvailable: Boolean(replay.presentation_review),
        });

        if (retryReportResult.status === "fulfilled") {
          setReportSnapshot(retryReportResult.value);
          setRetryEntry(retryReportResult.value.retry_entry ?? null);
          debug.log("[Replay] Retry entry loaded", {
            sessionId,
            retryScenarioType: retryReportResult.value.retry_entry?.scenario_type ?? null,
            retryFocusIntentVersion: retryReportResult.value.retry_entry?.focus_intent?.version ?? null,
            reportScenarioType: retryReportResult.value.scenario_type ?? null,
            presentationReviewAvailable: Boolean(retryReportResult.value.presentation_review),
          });
        } else {
          setReportSnapshot(null);
          setRetryEntry(null);
          debug.warn("[Replay] Retry entry unavailable; keeping replay conclusions read-only", {
            sessionId,
            error: retryReportResult.reason,
          });
        }

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
  const retryBlockedHint = (
    retryEntry?.scenario_type === "sales"
    && (!retryEntry.agent_id || !retryEntry.persona_id)
  )
    ? "当前销售会话缺少角色配置，请在训练页重新选择智能体与角色。"
    : (
        retryEntry?.scenario_type === "presentation"
        && !retryEntry.presentation_id
      )
        ? "当前演讲会话缺少课件配置，请返回训练页重新选择演示文稿。"
        : null;
  const claimTruth = extractSessionClaimTruth(replayData?.effectiveness_snapshot);
  const claimTruthSummary = formatClaimTruthSummary(claimTruth);
  const claimTruthEvidenceNote = formatClaimTruthEvidenceNote(claimTruth);
  const claimTruthClasses = getClaimTruthClasses(getClaimTruthTone(claimTruth?.status));
  const scenarioType = replayData?.scenario_type ?? reportSnapshot?.scenario_type ?? null;
  const isPresentationScenario = scenarioType === "presentation";
  const conclusionEvidenceSections = !isPresentationScenario
    ? formatConclusionEvidenceSections(replayData?.conclusion_evidence)
    : [];
  const evidenceDegradationItems = !isPresentationScenario
    ? formatEvidenceDegradationItems(replayData?.evidence_degradation)
    : [];
  const presentationReview = replayData?.presentation_review ?? reportSnapshot?.presentation_review ?? null;
  const presentationId = replayData?.presentation_id ?? retryEntry?.presentation_id ?? null;
  const presentationDegradedNote = formatPresentationDegradedNote(
    presentationReview,
    replayData?.evidence_completeness,
  );
  const presentationTotalPages = getPresentationTotalPages(presentationReview);
  const selectedPresentationSummary = getPresentationPageSummaries(presentationReview).find(
    (pageSummary) => pageSummary.page_number === activePresentationPage,
  ) ?? null;
  const presentationSlideContent = buildPresentationSlideFallback(selectedPresentationSummary);

  const handleJumpToMessage = useCallback((turnNumber: number) => {
    setActiveTurnNumber(turnNumber);
    const messageElement = document.querySelector(`[data-turn-number="${turnNumber}"]`);
    if (messageElement instanceof HTMLElement && typeof messageElement.scrollIntoView === "function") {
      messageElement.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, []);

  const handleRetryFromGoal = useCallback(async () => {
    const retry = retryEntry;
    setRetryHint(null);

    if (retryBlockedHint) {
      setRetryHint(retryBlockedHint);
      return;
    }

    if (!retry?.scenario_type) {
      setRetryHint("当前回放缺少再练配置，请先返回报告页确认训练目标。");
      return;
    }

    if (
      retry.scenario_type === "sales"
      && (!retry.agent_id || !retry.persona_id)
    ) {
      setRetryHint("当前销售会话缺少角色配置，请在训练页重新选择智能体与角色。");
      return;
    }

    try {
      const created = await api.practice.createSession({
        scenario_type: retry.scenario_type as "sales" | "presentation",
        agent_id: retry.agent_id || undefined,
        persona_id: retry.persona_id || undefined,
        presentation_id: retry.presentation_id || undefined,
        focus_intent: retry.focus_intent || undefined,
      });
      const nextParams = new URLSearchParams();
      nextParams.set("scenario_type", retry.scenario_type);
      if (retry.agent_id) nextParams.set("agent_id", retry.agent_id);
      if (retry.persona_id) nextParams.set("persona_id", retry.persona_id);
      if (retry.presentation_id) nextParams.set("presentation_id", retry.presentation_id);
      router.push(`/practice/${created.session_id}?${nextParams.toString()}`);
    } catch (retryError) {
      debug.warn("[Replay] Retry session creation failed", {
        sessionId,
        error: retryError,
      });
      setRetryHint(getApiErrorMessage(retryError));
    }
  }, [retryBlockedHint, retryEntry, router, sessionId]);

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

  useEffect(() => {
    if (!isPresentationScenario || !presentationReview) {
      setPresentationPageNotice(null);
      setActivePresentationPage(null);
      return;
    }

    const resolvedPageNumber = resolvePresentationLandingPage(
      presentationReview,
      presentationPageRequest.pageNumber,
    );
    const pageSummaryFound = Boolean(
      getPresentationPageSummaries(presentationReview).find(
        (pageSummary) => pageSummary.page_number === resolvedPageNumber,
      ),
    );
    setActivePresentationPage(resolvedPageNumber);
    setPresentationPageNotice(buildPresentationPageNotice(presentationPageRequest, {
      resolvedPageNumber,
      pageSummaryFound,
    }));

    debug.log("[Replay] Applied presentation page request", {
      sessionId,
      requestedPageNumber: presentationPageRequest.pageNumber,
      pageAnchorStatus: presentationPageRequest.anchorStatus,
      pageAnchorReason: presentationPageRequest.anchorReason,
      resolvedPageNumber,
      pageSummaryFound,
    });
  }, [
    isPresentationScenario,
    presentationPageRequest,
    presentationReview,
    sessionId,
  ]);

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

      {isPresentationScenario && presentationReview && (
        <>
          <GlassCard className="p-4 sm:p-5">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <h2 className="font-bold text-slate-900 text-base sm:text-lg">PPT 回放</h2>
                <p className="text-sm text-slate-600 mt-1">PPT 页级问题定位</p>
                <p className="text-sm text-slate-700 mt-3">
                  {presentationReview.detailed_feedback || "当前回放基于统一训练证据中的页级复盘与真实课件页码。"}
                </p>
                {presentationDegradedNote ? (
                  <p className="text-xs text-amber-700 mt-2">{presentationDegradedNote}</p>
                ) : null}
                {retryBlockedHint ? (
                  <p className="text-xs text-amber-700 mt-2">{retryBlockedHint}</p>
                ) : null}
                {retryHint ? (
                  <p className="text-xs text-amber-700 mt-2">{retryHint}</p>
                ) : null}
              </div>
              {retryEntry?.scenario_type === "presentation" ? (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleRetryFromGoal}
                  className="whitespace-nowrap"
                  disabled={Boolean(retryBlockedHint)}
                >
                  按目标再练一轮
                </Button>
              ) : null}
            </div>
          </GlassCard>

          {presentationPageNotice ? (() => {
            const noticeClasses = getReplayAnchorNoticeClasses(presentationPageNotice.tone);
            return (
              <GlassCard
                data-testid="presentation-page-banner"
                className={cn("p-4 sm:p-5 border", noticeClasses.card)}
              >
                <div className="flex items-start gap-3">
                  <Target className={cn("w-5 h-5 mt-0.5", noticeClasses.icon)} />
                  <div>
                    <p className={cn("text-xs font-semibold", noticeClasses.eyebrow)}>
                      来自报告的页级定位请求
                    </p>
                    <h2 className={cn("font-semibold mt-1", noticeClasses.title)}>
                      {presentationPageNotice.title}
                    </h2>
                    <p className={cn("text-sm mt-1", noticeClasses.body)}>
                      {presentationPageNotice.description}
                    </p>
                  </div>
                </div>
              </GlassCard>
            );
          })() : null}

          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)] gap-6">
            <SlideViewer
              presentationId={presentationId || undefined}
              currentPage={activePresentationPage || 1}
              totalPages={presentationTotalPages}
              slideContent={presentationSlideContent}
              onPageChange={(page) => setActivePresentationPage(page)}
            />

            <GlassCard className="p-4 sm:p-5">
              <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
                <h2 className="font-bold text-slate-900 text-base sm:text-lg">逐页定位</h2>
                <span className="text-xs rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-600">
                  {presentationTotalPages} 页
                </span>
              </div>
              <div className="flex flex-wrap gap-2 mb-4">
                {Array.from({ length: presentationTotalPages }, (_, index) => index + 1).map((pageNumber) => {
                  const pageSummary = getPresentationPageSummaries(presentationReview).find(
                    (item) => item.page_number === pageNumber,
                  );
                  const issueCount = pageSummary?.issue_clusters?.length || 0;
                  const isActive = pageNumber === activePresentationPage;
                  return (
                    <button
                      key={pageNumber}
                      type="button"
                      onClick={() => setActivePresentationPage(pageNumber)}
                      className={cn(
                        "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                        isActive
                          ? "border-blue-200 bg-blue-50 text-blue-700"
                          : "border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:text-blue-700",
                      )}
                    >
                      第 {pageNumber} 页{issueCount > 0 ? ` · ${issueCount} 个问题簇` : ""}
                    </button>
                  );
                })}
              </div>

              {selectedPresentationSummary ? (
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-2">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <p className="text-sm font-semibold text-slate-900">
                      第 {selectedPresentationSummary.page_number} 页
                    </p>
                    <span className="text-xs text-slate-500">
                      回合 {selectedPresentationSummary.start_turn}-{selectedPresentationSummary.end_turn}
                    </span>
                  </div>
                  <p className="text-sm text-slate-700">{selectedPresentationSummary.summary}</p>
                  {selectedPresentationSummary.key_points.length > 0 ? (
                    <p className="text-xs text-slate-500">
                      当前页要点：{selectedPresentationSummary.key_points.join("、")}
                    </p>
                  ) : null}
                  {selectedPresentationSummary.matched_required_points.length > 0 ? (
                    <p className="text-xs text-emerald-700">
                      已覆盖：{selectedPresentationSummary.matched_required_points.join("、")}
                    </p>
                  ) : null}
                  {selectedPresentationSummary.missing_required_points.length > 0 ? (
                    <p className="text-xs text-amber-700">
                      仍待补充：{selectedPresentationSummary.missing_required_points.join("、")}
                    </p>
                  ) : null}
                </div>
              ) : (
                <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4">
                  <p className="text-sm font-semibold text-amber-900">当前页暂无逐页摘要</p>
                  <p className="text-sm text-amber-800 mt-1">
                    {presentationDegradedNote || "这一页缺少稳定的页级回放锚点，请结合完整对话继续查看。"}
                  </p>
                </div>
              )}
            </GlassCard>
          </div>

          <GlassCard className="p-4 sm:p-5">
            <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
              <h2 className="font-bold text-slate-900 text-base sm:text-lg">当前页问题簇</h2>
              <span className="text-xs text-slate-500">
                {selectedPresentationSummary?.issue_clusters?.length || 0} 个问题簇
              </span>
            </div>
            {selectedPresentationSummary && (selectedPresentationSummary.issue_clusters?.length || 0) > 0 ? (
              <div className="space-y-3">
                {(selectedPresentationSummary.issue_clusters || []).map((issue, index) => {
                  const contextLines = formatPresentationIssueContextLines(issue);
                  const evidenceItems = (issue.evidence || []).filter((item) => !contextLines.includes(item));
                  return (
                    <div
                      key={`${selectedPresentationSummary.page_number}-${issue.issue_type}-${index}`}
                      className="rounded-xl border border-amber-100 bg-amber-50/70 p-4"
                    >
                      <div className="flex items-center justify-between gap-3 flex-wrap mb-2">
                        <span className="inline-flex rounded-full border border-amber-200 bg-white/90 px-2.5 py-1 text-xs font-semibold text-amber-800">
                          {formatPresentationIssueLabel(issue.issue_type) || issue.issue_type}
                        </span>
                        <span className="text-xs text-slate-500">
                          涉及回合：{issue.turn_numbers.length > 0 ? issue.turn_numbers.join("、") : "--"}
                        </span>
                      </div>
                      <p className="text-sm text-slate-800">{issue.summary}</p>
                      {contextLines.length > 0 ? (
                        <div className="mt-2 space-y-1">
                          {contextLines.map((line) => (
                            <p key={line} className="text-xs text-slate-600">{line}</p>
                          ))}
                        </div>
                      ) : null}
                      {evidenceItems.length > 0 ? (
                        <ul className="mt-3 space-y-1">
                          {evidenceItems.map((item) => (
                            <li key={item} className="text-xs text-slate-700 flex items-start gap-2">
                              <span className="mt-1 h-1.5 w-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                      {issue.turn_numbers.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {issue.turn_numbers.map((turnNumber) => (
                            <Button
                              key={`${issue.issue_type}-${turnNumber}`}
                              variant="outline"
                              size="sm"
                              onClick={() => handleJumpToMessage(turnNumber)}
                            >
                              定位到第 {turnNumber} 轮
                            </Button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
                <p className="text-sm text-slate-600">当前页暂无需要额外回看的问题簇。</p>
              </div>
            )}
          </GlassCard>
        </>
      )}

      {!isPresentationScenario && claimTruth && claimTruthSummary && (
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

      {!isPresentationScenario && conclusionEvidenceSections.length > 0 && (
        <GlassCard className="p-4 sm:p-5">
          <h2 className="font-bold text-slate-900 text-base sm:text-lg mb-4">结论出处</h2>
          <div className="space-y-4">
            {conclusionEvidenceSections.map((section) => (
              <div key={section.key} className="rounded-xl bg-slate-50/80 p-4">
                <p className="text-sm font-semibold text-slate-900 mb-3">{section.title}</p>
                <div className="flex flex-wrap gap-2">
                  {section.rows.map((row) => (
                    <span
                      key={`${section.key}-${row.key}`}
                      className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700"
                    >
                      {row.summary}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      {!isPresentationScenario && evidenceDegradationItems.length > 0 && (
        <GlassCard className="p-4 sm:p-5">
          <h2 className="font-bold text-slate-900 text-base sm:text-lg mb-4">证据降级状态</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {evidenceDegradationItems.map((item) => (
              <div
                key={item.key}
                className={cn(
                  "rounded-xl border p-4",
                  item.status === "ok"
                    ? "border-emerald-200 bg-emerald-50/70"
                    : "border-amber-200 bg-amber-50/70",
                )}
              >
                <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
                  <p className="text-sm font-semibold text-slate-900">{item.label}</p>
                  <span className={cn(
                    "inline-flex rounded-full border px-2.5 py-1 text-xs font-medium",
                    item.status === "ok"
                      ? "border-emerald-200 bg-white text-emerald-700"
                      : "border-amber-200 bg-white text-amber-700",
                  )}>
                    {item.status === "ok" ? "正常" : "降级"}
                  </span>
                </div>
                <p className="text-sm text-slate-700">{item.summary}</p>
              </div>
            ))}
          </div>
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

          {retryEntry?.scenario_type ? (
            <div className="mt-4 flex items-start justify-between gap-3 flex-wrap">
              <div>
                <p className="text-xs font-semibold text-slate-600">按当前问题线继续再练</p>
                <p className="text-sm text-slate-500 mt-1">
                  系统会沿用当前报告里的主问题与下一轮目标，再创建一场新的练习。
                </p>
                {retryBlockedHint ? (
                  <p className="text-xs text-amber-700 mt-2">{retryBlockedHint}</p>
                ) : null}
                {retryHint ? (
                  <p className="text-xs text-amber-700 mt-2">{retryHint}</p>
                ) : null}
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={handleRetryFromGoal}
                className="whitespace-nowrap"
                disabled={Boolean(retryBlockedHint)}
              >
                按目标再练一轮
              </Button>
            </div>
          ) : null}
        </GlassCard>
      )}

      {!isPresentationScenario && Array.isArray(replayData.stage_summary) && replayData.stage_summary.length > 0 && (
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

      {!isPresentationScenario && highlights.length > 0 ? (
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

      <AudioAuditCard audioAudit={replayData?.audio_audit} sessionId={sessionId} />

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
              const knowledgeAnswerDiagnostics = message.transcript_metadata?.knowledge_answer_diagnostics ?? null;
              const knowledgeCitations = Array.isArray(knowledgeAnswerDiagnostics?.citations)
                ? (knowledgeAnswerDiagnostics.citations as Array<Record<string, unknown>>).filter((item) => Boolean(item?.snippet))
                : [];
              const answerabilityLabel = typeof knowledgeAnswerDiagnostics?.answerability === 'string'
                ? knowledgeAnswerDiagnostics.answerability
                : null;
              const rewrittenQueries = Array.isArray(knowledgeAnswerDiagnostics?.rewritten_queries)
                ? (knowledgeAnswerDiagnostics.rewritten_queries as Array<unknown>).filter((item) => Boolean(typeof item === 'string' ? item.trim() : item))
                : [];
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
                  {message.role === "assistant" && knowledgeAnswerDiagnostics ? (
                    <div className="mt-3 rounded-xl border border-blue-200 bg-blue-50/70 p-3 space-y-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-semibold text-blue-700">回答级知识依据</span>
                        {answerabilityLabel ? (
                          <span className="text-[11px] rounded-full bg-white/80 px-2 py-1 text-blue-700 border border-blue-100">
                            回答约束：{answerabilityLabel}
                          </span>
                        ) : null}
                      </div>
                      {rewrittenQueries.length > 0 ? (
                        <p className="text-xs text-blue-700">
                          检索改写：{rewrittenQueries.join("；")}
                        </p>
                      ) : null}
                      {knowledgeCitations.length > 0 ? (
                        <div className="space-y-2">
                          {knowledgeCitations.slice(0, 3).map((citation, index) => {
                            const kbName = (typeof citation.knowledge_base_name === 'string' && citation.knowledge_base_name) ? citation.knowledge_base_name : "内部知识库";
                            const docTitle = typeof citation.document_title === 'string' && citation.document_title ? citation.document_title : "";
                            const snippet = typeof citation.snippet === 'string' ? citation.snippet : "";
                            return (
                            <div key={`${message.id}-citation-${index}`} className="rounded-lg border border-white/80 bg-white/80 px-3 py-2">
                              <p className="text-[11px] font-semibold text-slate-600">
                                {kbName}
                                {docTitle ? ` · ${docTitle}` : ""}
                              </p>
                              <p className="mt-1 text-sm leading-relaxed text-slate-700">{snippet}</p>
                            </div>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="text-xs text-blue-700">当前回答未附带可展示的内部引用片段。</p>
                      )}
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
  </div>
  );
}
