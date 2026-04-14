"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
    AlertTriangle,
    ArrowLeft,
    CheckCircle,
    Home,
    Lightbulb,
    Sparkles,
    Target,
} from "lucide-react";

import { HighlightList } from "@/components/highlights";
import { AudioAuditCardWithSession as AudioAuditCard } from "@/components/audio/AudioAuditCard";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { api, ApiRequestError, getApiErrorMessage } from "@/lib/api/client";
import {
    ComprehensiveReport,
    HighlightsResponse,
    KnowledgeCheckDiagnostics,
    PracticeSessionReport,
    PresentationReview,
    ReplayAnchor,
    ReplayData,
} from "@/lib/api/types";
import { debug } from "@/lib/debug";
import {
    extractSessionLearningCue,
    formatClaimTruthEvidenceNote,
    formatClaimTruthSummary,
    formatConclusionEvidenceSections,
    formatEvidenceCompletenessNote,
    formatEvidenceDegradationItems,
    formatNotEvaluableReason,
    formatPresentationDegradedNote,
    formatPresentationIssueContextLines,
    formatPresentationIssueLabel,
    formatSessionStageLabel,
    extractSessionClaimTruth,
    getClaimTruthTone,
    extractRetrievalFacts,
    formatRetrievalStatusLabel,
    formatRetrievalStatusTone,
    formatLatestAttemptCopy,
    formatMissExplanation,
    formatSearchFailedExplanation,
    formatWeakEvidenceRetrievalNote,
    type SessionClaimTruthTone,
} from "@/lib/session-evidence";
import { cn } from "@/lib/utils";

function formatSnapshotTime(value?: string | null): string {
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

function getScoreColor(score: number): string {
    if (score >= 80) return "text-green-600";
    if (score >= 60) return "text-yellow-600";
    return "text-red-600";
}

function getScoreLabel(score: number): string {
    if (score >= 90) return "优秀";
    if (score >= 80) return "良好";
    if (score >= 60) return "及格";
    return "待改进";
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

function getRetrievalStatusClasses(tone: ReturnType<typeof formatRetrievalStatusTone>) {
    if (tone === "success") {
        return {
            card: "border-emerald-200 bg-emerald-50/80",
            badge: "text-emerald-700 bg-white/80 border-emerald-200",
            text: "text-emerald-900",
            note: "text-emerald-700",
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

    if (tone === "error") {
        return {
            card: "border-rose-200 bg-rose-50/80",
            badge: "text-rose-700 bg-white/80 border-rose-200",
            text: "text-rose-900",
            note: "text-rose-700",
        };
    }

    return {
        card: "border-slate-200 bg-slate-50/80",
        badge: "text-slate-700 bg-white/80 border-slate-200",
        text: "text-slate-900",
        note: "text-slate-600",
    };
}

function buildSalesDimensionScores(report: PracticeSessionReport) {
    return [
        {
            name: "价值表达",
            score: report.logic_score,
            description: "是否把产品能力翻译成客户收益与业务价值。",
        },
        {
            name: "证据与收益",
            score: report.accuracy_score,
            description: "是否用案例、数据或 ROI 证据支撑收益主张。",
        },
        {
            name: "异议推进",
            score: report.completeness_score,
            description: "是否处理价格/竞品/风险异议并推动下一步。",
        },
    ];
}

function buildPresentationIssueItems(review?: PresentationReview | null) {
    const pageIssueCounts = (review?.page_summaries || []).reduce((counts, pageSummary) => {
        for (const cluster of pageSummary.issue_clusters || []) {
            counts.set(cluster.issue_type, (counts.get(cluster.issue_type) || 0) + 1);
        }
        return counts;
    }, new Map<string, number>());

    const diagnosticIssueTypes = Array.isArray(review?.diagnostics?.page_issue_types)
        ? review.diagnostics.page_issue_types.filter(Boolean)
        : [];
    const issueTypes = diagnosticIssueTypes.length > 0
        ? diagnosticIssueTypes
        : Array.from(pageIssueCounts.keys());

    if (issueTypes.length > 0) {
        return issueTypes
            .map((issueType) => ({
                issueType,
                count: pageIssueCounts.get(issueType) || Number(review?.issue_counts?.[issueType] || 0),
                label: formatPresentationIssueLabel(issueType) || issueType,
            }))
            .filter((item) => item.count > 0);
    }

    return Object.entries(review?.issue_counts || {})
        .map(([issueType, rawCount]) => ({
            issueType,
            count: Number(rawCount || 0),
            label: formatPresentationIssueLabel(issueType) || issueType,
        }))
        .filter((item) => item.count > 0);
}

function isReportNotFound(error: unknown): boolean {
    if (error instanceof ApiRequestError) {
        return error.status === 404
            || error.errorCode === "[REPORT_NOT_FOUND]"
            || error.errorCode === "[SESSION_NOT_FOUND]";
    }

    return error instanceof Error && /404|not found/i.test(error.message);
}

function hasEnhancedInsights(report: ComprehensiveReport | null): boolean {
    if (!report) {
        return false;
    }

    return Boolean(
        report.key_strengths.length
        || report.key_improvements.length
        || report.recommendations.length
        || report.detailed_feedback?.trim(),
    );
}

type ReplayDeepLinkFocus = "main_issue" | "next_goal" | "learning_evidence";

function hasReplayAnchorTarget(anchor?: ReplayAnchor | null): boolean {
    if (!anchor) {
        return false;
    }

    return Boolean(
        (typeof anchor.message_id === "string" && anchor.message_id.trim())
        || typeof anchor.turn_number === "number",
    );
}

function buildReplayDeepLink(
    sessionId: string,
    options: {
        focus: ReplayDeepLinkFocus;
        anchor?: ReplayAnchor | null;
        turnNumber?: number | null;
    },
): string {
    const params = new URLSearchParams();
    params.set("focus", options.focus);

    const anchor = options.anchor;
    if (anchor) {
        if (typeof anchor.message_id === "string" && anchor.message_id.trim()) {
            params.set("message_id", anchor.message_id);
        }
        if (typeof anchor.turn_number === "number") {
            params.set("turn", String(anchor.turn_number));
        }
        params.set("anchor_status", anchor.status);
        if (anchor.degraded_reason) {
            params.set("anchor_reason", anchor.degraded_reason);
        }
        if (anchor.marker?.type) {
            params.set("marker_type", anchor.marker.type);
        }
        if (typeof anchor.marker?.timestamp_ms === "number") {
            params.set("marker_timestamp_ms", String(anchor.marker.timestamp_ms));
        }
    } else if (typeof options.turnNumber === "number") {
        params.set("turn", String(options.turnNumber));
    }

    return `/practice/${sessionId}/replay?${params.toString()}`;
}

function formatReplayAnchorHint(anchor?: ReplayAnchor | null): string {
    if (!anchor || !hasReplayAnchorTarget(anchor) || anchor.status === "missing") {
        return "当前暂无可定位的回放片段。";
    }

    if (anchor.status === "resolved") {
        if (typeof anchor.turn_number === "number") {
            return `回放将定位到第 ${anchor.turn_number} 轮高光片段。`;
        }
        return "回放将定位到对应高光片段。";
    }

    if (anchor.degraded_reason === "missing_marker") {
        if (typeof anchor.turn_number === "number") {
            return `高光标记缺失，回放将直接定位到第 ${anchor.turn_number} 轮。`;
        }
        return "高光标记缺失，回放将直接定位到相关对话片段。";
    }

    if (anchor.degraded_reason === "no_matching_highlight") {
        if (anchor.marker?.label) {
            return `未找到精确高光，回放将定位到“${anchor.marker.label}”阶段。`;
        }
        if (typeof anchor.turn_number === "number") {
            return `未找到精确高光，回放将定位到第 ${anchor.turn_number} 轮附近。`;
        }
    }

    return "当前暂无可定位的回放片段。";
}

export default function ComprehensiveReportPage() {
    const router = useRouter();
    const params = useParams();
    const sessionId = params.sessionId as string;

    const [loading, setLoading] = useState(true);
    const [report, setReport] = useState<PracticeSessionReport | null>(null);
    const [enhancedReport, setEnhancedReport] = useState<ComprehensiveReport | null>(null);
    const [enhancedUnavailableHint, setEnhancedUnavailableHint] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [knowledgeCheck, setKnowledgeCheck] = useState<KnowledgeCheckDiagnostics | null>(null);
    const [replayData, setReplayData] = useState<ReplayData | null>(null);
    const [highlightsData, setHighlightsData] = useState<HighlightsResponse | null>(null);
    const [highlightsLoading, setHighlightsLoading] = useState(false);
    const [highlightsUnavailableHint, setHighlightsUnavailableHint] = useState<string | null>(null);
    const [retryHint, setRetryHint] = useState<string | null>(null);

    const loadUnifiedEvidence = useCallback(async () => {
        setLoading(true);
        setError(null);
        setReplayData(null);

        try {
            const data = await api.sessions.getReport(sessionId);
            setReport(data);
            debug.log("[Report] Loaded unified evidence contract", {
                sessionId,
                scenarioType: data.scenario_type,
                overallScore: data.overall_score,
                evaluable: data.evaluable,
                notEvaluableReason: data.not_evaluable_reason,
                evidenceComplete: data.evidence_completeness?.complete,
                presentationReviewAvailable: Boolean(data.presentation_review),
            });
        } catch (err) {
            setReport(null);
            setError(`统一训练证据加载失败：${getApiErrorMessage(err)}`);
            debug.error("[Report] Unified evidence contract load failed", {
                sessionId,
                error: err,
            });
        } finally {
            setLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        void loadUnifiedEvidence();
    }, [loadUnifiedEvidence]);

    useEffect(() => {
        if (!report) {
            return;
        }

        let cancelled = false;
        const enhancedUnavailableCopy = report.scenario_type === "presentation"
            ? "综合洞察暂不可用，当前页面仍展示基于课件证据的 PPT 复盘。"
            : "综合洞察暂不可用，当前页面仅展示统一训练证据。";

        const loadEnhancedInsights = async () => {
            setEnhancedReport(null);
            setEnhancedUnavailableHint(null);

            try {
                const data = await api.admin.getComprehensiveReport(sessionId);
                if (cancelled) return;
                setEnhancedReport(data);
                debug.log("[Report] Loaded enhanced report", {
                    sessionId,
                    scenarioType: report.scenario_type,
                    hasInsights: hasEnhancedInsights(data),
                });
                return;
            } catch (error) {
                if (!isReportNotFound(error)) {
                    if (!cancelled) {
                        setEnhancedUnavailableHint(enhancedUnavailableCopy);
                        debug.warn("[Report] Enhanced report unavailable; keeping unified evidence", {
                            sessionId,
                            scenarioType: report.scenario_type,
                            source: "load",
                            error,
                        });
                    }
                    return;
                }
            }

            try {
                const generated = await api.admin.generateComprehensiveReport(sessionId);
                if (cancelled) return;
                setEnhancedReport(generated);
                debug.log("[Report] Generated enhanced report on demand", {
                    sessionId,
                    scenarioType: report.scenario_type,
                    hasInsights: hasEnhancedInsights(generated),
                });
            } catch (error) {
                if (cancelled) return;
                setEnhancedUnavailableHint(enhancedUnavailableCopy);
                debug.warn("[Report] Enhanced report unavailable after generate attempt", {
                    sessionId,
                    scenarioType: report.scenario_type,
                    source: "generate",
                    error,
                });
            }
        };

        void loadEnhancedInsights();

        return () => {
            cancelled = true;
        };
    }, [sessionId, report]);

    useEffect(() => {
        if (!report || (!report.main_issue && !report.next_goal)) {
            setReplayData(null);
            return;
        }

        let cancelled = false;

        api.sessions
            .getReplay(sessionId)
            .then((data) => {
                if (cancelled) return;
                setReplayData(data);
                debug.log("[Report] Replay anchors loaded", {
                    sessionId,
                    issueAnchorStatus: data.main_issue?.replay_anchor?.status,
                    goalAnchorStatus: data.next_goal?.replay_anchor?.status,
                });
            })
            .catch((err) => {
                if (cancelled) return;
                setReplayData(null);
                debug.warn("[Report] Replay anchors unavailable; keeping report conclusions local", {
                    sessionId,
                    error: err,
                });
            });

        return () => {
            cancelled = true;
        };
    }, [sessionId, report]);

    useEffect(() => {
        if (!report) {
            return;
        }

        let cancelled = false;

        if (report.scenario_type === "presentation") {
            setKnowledgeCheck(null);
            debug.log("[Report] Knowledge-check skipped for presentation scenario", {
                sessionId,
                scenarioType: report.scenario_type,
            });
            return () => {
                cancelled = true;
            };
        }

        api.sessions
            .getKnowledgeCheck(sessionId)
            .then((data) => {
                if (cancelled) return;
                setKnowledgeCheck(data);
                debug.log("[Report] Knowledge-check", {
                    sessionId,
                    status: data.status,
                    summary: data.summary,
                    attemptCount: data.attempt_count,
                    hitRate: data.hit_rate,
                });
            })
            .catch((err) => {
                if (cancelled) return;
                setKnowledgeCheck(null);
                debug.warn("[Report] Knowledge-check load failed", {
                    sessionId,
                    error: err,
                });
            });

        return () => {
            cancelled = true;
        };
    }, [sessionId, report]);

    useEffect(() => {
        if (!report) {
            return;
        }

        let cancelled = false;
        setHighlightsLoading(true);
        setHighlightsUnavailableHint(null);

        api.sessions.getHighlights(sessionId)
            .then((data) => {
                if (cancelled) return;
                setHighlightsData(data);
                debug.log("[Report] Highlights loaded", {
                    sessionId,
                    scenarioType: report.scenario_type,
                    highlightCount: data.highlights.length,
                });
            })
            .catch((err) => {
                if (cancelled) return;
                setHighlightsData(null);
                setHighlightsUnavailableHint(
                    report.scenario_type === "presentation"
                        ? "高光片段暂不可用，PPT 基础复盘不受影响。"
                        : "高光片段暂不可用，基础评估结果不受影响。",
                );
                debug.warn("[Report] Highlights unavailable; keeping unified evidence", {
                    sessionId,
                    scenarioType: report.scenario_type,
                    error: err,
                });
            })
            .finally(() => {
                if (!cancelled) {
                    setHighlightsLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [sessionId, report]);

    const isPresentationScenario = report?.scenario_type === "presentation";
    const presentationReview = isPresentationScenario ? report?.presentation_review ?? null : null;
    const presentationDegradedNote = formatPresentationDegradedNote(
        presentationReview,
        report?.evidence_completeness,
    );
    const presentationIssueItems = useMemo(
        () => buildPresentationIssueItems(presentationReview),
        [presentationReview],
    );
    const presentationIssueClusterCount = useMemo(() => {
        const diagnosticCount = presentationReview?.diagnostics?.page_issue_cluster_count;
        if (typeof diagnosticCount === "number") {
            return diagnosticCount;
        }
        return (presentationReview?.page_summaries || []).reduce(
            (count, pageSummary) => count + (pageSummary.issue_clusters?.length || 0),
            0,
        );
    }, [presentationReview]);
    const retryEntry = report?.retry_entry;
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
    const issueReplayAnchor = replayData?.main_issue?.replay_anchor ?? null;
    const nextGoalReplayAnchor = replayData?.next_goal?.replay_anchor ?? null;
    const issueReplayHint = formatReplayAnchorHint(issueReplayAnchor);
    const nextGoalReplayHint = formatReplayAnchorHint(nextGoalReplayAnchor);
    const issueReplayAvailable = hasReplayAnchorTarget(issueReplayAnchor);
    const nextGoalReplayAvailable = hasReplayAnchorTarget(nextGoalReplayAnchor);

    const goHome = () => {
        router.push("/");
    };

    const openReplayDeepLink = useCallback((options: {
        focus: ReplayDeepLinkFocus;
        anchor?: ReplayAnchor | null;
        turnNumber?: number | null;
    }) => {
        router.push(buildReplayDeepLink(sessionId, options));
    }, [router, sessionId]);

    const handleRetryFromGoal = async () => {
        const retry = retryEntry;
        setRetryHint(null);

        if (retryBlockedHint) {
            setRetryHint(retryBlockedHint);
            return;
        }

        if (!retry?.scenario_type) {
            setRetryHint("当前报告缺少再练配置，请先返回训练页重新创建会话。");
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
        } catch (err) {
            debug.warn("[Report] Retry session creation failed", { sessionId, error: err });
            setRetryHint(getApiErrorMessage(err));
        }
    };

    const dimensionScores = useMemo(() => {
        if (!report) {
            return [];
        }

        if (presentationReview) {
            return presentationReview.dimension_scores.map((dimension) => ({
                name: dimension.name,
                score: dimension.score,
                description: dimension.description,
            }));
        }

        return buildSalesDimensionScores(report);
    }, [report, presentationReview]);

    const practiceSuggestions = useMemo(() => {
        if (presentationReview?.recommendations?.length) {
            return presentationReview.recommendations;
        }
        return report?.suggestions || [];
    }, [presentationReview, report?.suggestions]);

    const evidenceCompletenessNote = presentationReview
        ? (presentationDegradedNote || formatEvidenceCompletenessNote(report?.evidence_completeness))
        : formatEvidenceCompletenessNote(report?.evidence_completeness);
    const notEvaluableReasonText = formatNotEvaluableReason(report?.not_evaluable_reason);
    const reportTitle = isPresentationScenario ? "PPT 复盘报告" : "训练评估报告";
    const reportIntro = isPresentationScenario
        ? "综合评分反映流畅连贯、内容准确、专业表达、互动问答与整体表现。"
        : "综合评分反映价值翻译、证据支撑和异议推进的完成度。";
    const overallResult = report?.overall_result || null;
    const overallResultLabel = overallResult === "strong_pass"
        ? "销售价值表达优秀"
        : overallResult === "pass"
            ? "销售基线通过"
            : overallResult === "fail"
                ? "销售基线待加强"
                : "未判定";
    const overallResultTone = overallResult === "strong_pass"
        ? "text-emerald-700 bg-emerald-50 border-emerald-200"
        : overallResult === "pass"
            ? "text-blue-700 bg-blue-50 border-blue-200"
            : overallResult === "fail"
                ? "text-rose-700 bg-rose-50 border-rose-200"
                : "text-slate-700 bg-slate-50 border-slate-200";
    const claimTruth = !isPresentationScenario
        ? extractSessionClaimTruth(report?.effectiveness_snapshot)
        : null;
    const reportLearningCue = extractSessionLearningCue({
        mainIssue: report?.main_issue,
        nextGoal: report?.next_goal,
    });
    const claimTruthSummary = formatClaimTruthSummary(claimTruth);
    const claimTruthEvidenceNote = formatClaimTruthEvidenceNote(claimTruth);
    const claimTruthClasses = getClaimTruthClasses(getClaimTruthTone(claimTruth?.status));
    const retrievalFacts = !isPresentationScenario
        ? extractRetrievalFacts(report?.effectiveness_snapshot)
        : null;
    const conclusionEvidenceSections = !isPresentationScenario
        ? formatConclusionEvidenceSections(report?.conclusion_evidence)
        : [];
    const evidenceDegradationItems = !isPresentationScenario
        ? formatEvidenceDegradationItems(report?.evidence_degradation)
        : [];
    const retrievalStatusTone = formatRetrievalStatusTone(retrievalFacts?.status);
    const retrievalClasses = getRetrievalStatusClasses(retrievalStatusTone);
    const retrievalLatestAttemptCopy = retrievalFacts ? formatLatestAttemptCopy(retrievalFacts) : null;
    const retrievalMissExplanation = retrievalFacts ? formatMissExplanation(retrievalFacts) : null;
    const retrievalFailureExplanation = retrievalFacts ? formatSearchFailedExplanation(retrievalFacts) : null;
    const retrievalWeakEvidenceNote = formatWeakEvidenceRetrievalNote(claimTruth, retrievalFacts);
    const retrievalResultSummaries = retrievalFacts?.latest_attempt?.result_summaries ?? [];

    if (loading) {
        return (
            <div className="container mx-auto px-4 py-12 text-center">
                <StatusIndicator status="loading" />
                <p className="mt-4 text-zinc-500">加载统一训练证据中...</p>
            </div>
        );
    }

    if (error || !report) {
        return (
            <div className="container mx-auto px-4 py-12 text-center">
                <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
                <p className="text-zinc-600">{error || "统一训练证据不存在"}</p>
                <Button variant="outline" onClick={goHome} className="mt-4">返回首页</Button>
            </div>
        );
    }

    return (
        <div className="container mx-auto px-4 py-6 max-w-5xl">
            <div className="flex items-center justify-between mb-6">
                <Button variant="ghost" size="sm" onClick={goHome}>
                    <ArrowLeft className="w-4 h-4 mr-2" />返回首页
                </Button>
                <div className="flex items-center gap-2">
                    <Button variant="primary" size="sm" onClick={goHome}>
                        <Home className="w-4 h-4 mr-2" />退出到首页
                    </Button>
                </div>
            </div>

            <GlassCard className="p-6 mb-6">
                <div className="text-center">
                    <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white mb-4">
                        <span data-testid="report-overall-score" className="text-3xl font-bold">
                            {report.overall_score.toFixed(0)}
                        </span>
                    </div>
                    <h1 className="text-2xl font-bold text-zinc-900 mb-2">{reportTitle}</h1>
                    <p className={cn("text-lg font-medium", getScoreColor(report.overall_score))}>
                        {getScoreLabel(report.overall_score)}
                    </p>
                    <p className="text-xs text-zinc-500 mt-2">
                        {reportIntro}
                    </p>
                </div>
            </GlassCard>

            {report.evaluable === false && (
                <GlassCard className="p-6 mb-6 border border-amber-200 bg-amber-50/80">
                    <h2 className="text-lg font-semibold text-amber-900 mb-2">当前会话暂不可评估</h2>
                    <p className="text-sm text-amber-800">{notEvaluableReasonText}</p>
                    {evidenceCompletenessNote && (
                        <p className="text-xs text-amber-700 mt-2">{evidenceCompletenessNote}</p>
                    )}
                </GlassCard>
            )}

            {!isPresentationScenario && report.evaluable !== false && evidenceCompletenessNote && (
                <GlassCard className="p-4 mb-6 border border-blue-200 bg-blue-50/80">
                    <p className="text-sm text-blue-800">{evidenceCompletenessNote}</p>
                </GlassCard>
            )}

            {enhancedUnavailableHint && (
                <GlassCard className="p-4 mb-6 border border-slate-200 bg-slate-50/80">
                    <p className="text-sm text-slate-700">{enhancedUnavailableHint}</p>
                </GlassCard>
            )}

            {!isPresentationScenario && claimTruth && claimTruthSummary && (
                <GlassCard className={cn("p-6 mb-6 border", claimTruthClasses.card)}>
                    <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
                        <h2 className="text-lg font-semibold text-zinc-900">主张证据状态</h2>
                        <span className={cn("text-xs font-semibold px-3 py-1 rounded-full border", claimTruthClasses.badge)}>
                            {claimTruth.label}
                        </span>
                    </div>
                    <p className={cn("text-sm", claimTruthClasses.text)}>{claimTruthSummary}</p>
                    {claimTruthEvidenceNote && (
                        <p className={cn("text-xs mt-2", claimTruthClasses.note)}>{claimTruthEvidenceNote}</p>
                    )}
                </GlassCard>
            )}

            {isPresentationScenario && presentationReview && (
                <>
                    <GlassCard className="p-6 mb-6">
                        <div className="flex items-start justify-between gap-4 flex-wrap">
                            <div className="max-w-3xl">
                                <div className="flex items-center gap-2 mb-3 flex-wrap">
                                    <h2 className="text-lg font-semibold text-zinc-900">PPT 复盘基线</h2>
                                    <span className={cn(
                                        "text-xs font-semibold px-3 py-1 rounded-full border",
                                        presentationReview.coverage_status === "complete"
                                            ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                                            : "text-amber-700 bg-amber-50 border-amber-200",
                                    )}>
                                        {presentationReview.coverage_status === "complete" ? "页级证据完整" : "页级证据降级"}
                                    </span>
                                </div>
                                <p className="text-sm text-zinc-700 leading-7">
                                    {presentationReview.detailed_feedback || "当前页面展示基于真实课件与页级证据生成的 PPT 复盘。"}
                                </p>
                                {retryBlockedHint && (
                                    <p className="text-xs text-amber-700 mt-2">{retryBlockedHint}</p>
                                )}
                                {retryHint && (
                                    <p className="text-xs text-amber-700 mt-2">{retryHint}</p>
                                )}
                            </div>
                            {retryEntry?.scenario_type === "presentation" && (
                                <Button
                                    variant="primary"
                                    size="sm"
                                    onClick={handleRetryFromGoal}
                                    className="whitespace-nowrap"
                                    disabled={Boolean(retryBlockedHint)}
                                >
                                    按目标再练一轮
                                </Button>
                            )}
                        </div>
                    </GlassCard>

                    <GlassCard className="p-6 mb-6">
                        <h2 className="text-lg font-semibold text-zinc-900 mb-4">PPT 表达能力总览</h2>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {dimensionScores.map((dimension) => (
                                <div key={dimension.name} className="rounded-xl bg-zinc-50 p-4">
                                    <div className="flex items-center justify-between gap-3 mb-2">
                                        <p className="text-sm font-semibold text-zinc-700">{dimension.name}</p>
                                        <span className={cn("text-lg font-bold", getScoreColor(dimension.score))}>
                                            {dimension.score.toFixed(0)}
                                        </span>
                                    </div>
                                    <div className="relative w-full h-2 bg-zinc-200 rounded-full mb-2">
                                        <div
                                            className={cn(
                                                "absolute top-0 left-0 h-full rounded-full",
                                                dimension.score >= 80
                                                    ? "bg-green-500"
                                                    : dimension.score >= 60
                                                        ? "bg-yellow-500"
                                                        : "bg-red-500",
                                            )}
                                            style={{ width: `${dimension.score}%` }}
                                        />
                                    </div>
                                    <p className="text-xs text-zinc-500">{dimension.description}</p>
                                </div>
                            ))}
                        </div>
                    </GlassCard>

                    {presentationIssueClusterCount > 0 && (
                        <GlassCard className="p-6 mb-6">
                            <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
                                <div>
                                    <h2 className="text-lg font-semibold text-zinc-900">页级问题簇总览</h2>
                                    <p className="text-sm text-zinc-600 mt-1">
                                        共 {presentationIssueClusterCount} 个页级问题簇，优先按页修正这些表达偏差。
                                    </p>
                                </div>
                                <span className="inline-flex rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800">
                                    {presentationIssueClusterCount} 个问题簇
                                </span>
                            </div>
                            {presentationIssueItems.length > 0 ? (
                                <div className="flex flex-wrap gap-2">
                                    {presentationIssueItems.map((item) => (
                                        <span
                                            key={item.issueType}
                                            className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800"
                                        >
                                            {item.label} · {item.count}
                                        </span>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-zinc-600">当前尚未识别出需要逐页回看的问题簇。</p>
                            )}
                        </GlassCard>
                    )}

                    <GlassCard className="p-6 mb-6">
                        <h2 className="text-lg font-semibold text-zinc-900 mb-4">逐页总结</h2>
                        {presentationReview.page_summaries.length > 0 ? (
                            <div className="space-y-4">
                                {presentationReview.page_summaries.map((pageSummary) => (
                                    <div key={`${pageSummary.page_number}-${pageSummary.stage_number}`} className="rounded-xl bg-zinc-50 p-4">
                                        <div className="flex items-start justify-between gap-3 flex-wrap mb-3">
                                            <div>
                                                <p className="text-sm font-semibold text-zinc-900">第 {pageSummary.page_number} 页</p>
                                                <p className="text-xs text-zinc-500">
                                                    第 {pageSummary.stage_number} 段 · 回合 {pageSummary.start_turn}-{pageSummary.end_turn}
                                                </p>
                                            </div>
                                            <span className={cn("text-sm font-semibold", getScoreColor(pageSummary.average_score))}>
                                                {pageSummary.average_score.toFixed(0)}分
                                            </span>
                                        </div>
                                        <p className="text-sm text-zinc-700 mb-3">{pageSummary.summary}</p>
                                        {pageSummary.key_points.length > 0 && (
                                            <p className="text-xs text-zinc-500 mb-1">关键点：{pageSummary.key_points.join("、")}</p>
                                        )}
                                        {pageSummary.matched_required_points.length > 0 && (
                                            <p className="text-xs text-emerald-700 mb-1">
                                                已覆盖：{pageSummary.matched_required_points.join("、")}
                                            </p>
                                        )}
                                        {pageSummary.missing_required_points.length > 0 && (
                                            <p className="text-xs text-amber-700">
                                                仍待补充：{pageSummary.missing_required_points.join("、")}
                                            </p>
                                        )}

                                        {(pageSummary.issue_clusters?.length || 0) > 0 && (
                                            <div className="mt-4 rounded-xl border border-amber-100 bg-white/80 p-4">
                                                <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
                                                    <p className="text-sm font-semibold text-zinc-900">
                                                        第 {pageSummary.page_number} 页问题簇
                                                    </p>
                                                    <span className="inline-flex rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800">
                                                        {pageSummary.issue_clusters?.length || 0} 个
                                                    </span>
                                                </div>
                                                <div className="space-y-3">
                                                    {(pageSummary.issue_clusters || []).map((issue, index) => {
                                                        const contextLines = formatPresentationIssueContextLines(issue);
                                                        const evidenceItems = issue.evidence.filter(
                                                            (item) => !contextLines.includes(item),
                                                        );
                                                        return (
                                                            <div
                                                                key={`${pageSummary.page_number}-${issue.issue_type}-${index}`}
                                                                className="rounded-xl border border-amber-100 bg-amber-50/70 p-3"
                                                            >
                                                                <div className="flex items-center justify-between gap-3 flex-wrap mb-2">
                                                                    <span className="inline-flex rounded-full border border-amber-200 bg-white/90 px-2.5 py-1 text-xs font-semibold text-amber-800">
                                                                        {formatPresentationIssueLabel(issue.issue_type) || issue.issue_type}
                                                                    </span>
                                                                    <span className="text-xs text-zinc-500">
                                                                        涉及回合：{issue.turn_numbers.length > 0 ? issue.turn_numbers.join("、") : "--"}
                                                                    </span>
                                                                </div>
                                                                <p className="text-sm text-zinc-800">{issue.summary}</p>
                                                                {contextLines.length > 0 && (
                                                                    <div className="mt-2 space-y-1">
                                                                        {contextLines.map((line) => (
                                                                            <p key={line} className="text-xs text-zinc-600">{line}</p>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                                {evidenceItems.length > 0 && (
                                                                    <ul className="mt-3 space-y-1">
                                                                        {evidenceItems.map((item) => (
                                                                            <li key={item} className="text-xs text-zinc-700 flex items-start gap-2">
                                                                                <span className="mt-1 h-1.5 w-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                                                                                <span>{item}</span>
                                                                            </li>
                                                                        ))}
                                                                    </ul>
                                                                )}
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                                <p className="text-sm font-semibold text-amber-900 mb-1">逐页总结暂不可用</p>
                                <p className="text-sm text-amber-800">
                                    {presentationDegradedNote || "当前页级证据不足，逐页总结会在页码事实补齐后恢复。"}
                                </p>
                            </div>
                        )}
                    </GlassCard>

                    <GlassCard className="p-6 mb-6">
                        <h2 className="text-lg font-semibold text-zinc-900 mb-4">要点覆盖与表达诊断</h2>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                            <div className="rounded-xl bg-zinc-50 p-3">
                                <div className="text-xs text-zinc-500">已总结页数</div>
                                <div className="text-lg font-bold text-zinc-900">
                                    {presentationReview.page_summaries.length} / {presentationReview.diagnostics.total_pages}
                                </div>
                            </div>
                            <div className="rounded-xl bg-zinc-50 p-3">
                                <div className="text-xs text-zinc-500">必讲要点覆盖</div>
                                <div className="text-lg font-bold text-zinc-900">
                                    {presentationReview.required_talking_points.covered} / {presentationReview.required_talking_points.total} 已覆盖
                                </div>
                            </div>
                            <div className="rounded-xl bg-zinc-50 p-3">
                                <div className="text-xs text-zinc-500">遗漏要点</div>
                                <div className="text-lg font-bold text-zinc-900">
                                    {presentationReview.required_talking_points.missing}
                                </div>
                            </div>
                            <div className="rounded-xl bg-zinc-50 p-3">
                                <div className="text-xs text-zinc-500">禁用词提醒</div>
                                <div className="text-lg font-bold text-zinc-900">
                                    {presentationReview.issue_counts.forbidden_word || 0}
                                </div>
                            </div>
                        </div>

                        {presentationIssueItems.length > 0 ? (
                            <div className="flex flex-wrap gap-2 mb-4">
                                {presentationIssueItems.map((item) => (
                                    <span
                                        key={item.issueType}
                                        className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800"
                                    >
                                        {item.label} · {item.count}
                                    </span>
                                ))}
                            </div>
                        ) : null}

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="rounded-xl bg-zinc-50 p-4">
                                <p className="text-sm font-semibold text-zinc-900 mb-2">做得好的部分</p>
                                {presentationReview.strengths.length > 0 ? (
                                    <ul className="space-y-2">
                                        {presentationReview.strengths.map((item, index) => (
                                            <li key={`${item}-${index}`} className="text-sm text-zinc-700 flex items-start gap-2">
                                                <CheckCircle className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                                                {item}
                                            </li>
                                        ))}
                                    </ul>
                                ) : (
                                    <p className="text-sm text-zinc-600">当前暂无额外优势总结。</p>
                                )}
                            </div>
                            <div className="rounded-xl bg-zinc-50 p-4">
                                <p className="text-sm font-semibold text-zinc-900 mb-2">下一轮重点改进</p>
                                {presentationReview.improvements.length > 0 ? (
                                    <ul className="space-y-2">
                                        {presentationReview.improvements.map((item, index) => (
                                            <li key={`${item}-${index}`} className="text-sm text-zinc-700 flex items-start gap-2">
                                                <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                                                {item}
                                            </li>
                                        ))}
                                    </ul>
                                ) : (
                                    <p className="text-sm text-zinc-600">当前暂无额外改进项。</p>
                                )}
                            </div>
                        </div>
                    </GlassCard>
                </>
            )}

            {!isPresentationScenario && (report.overall_result || report.main_issue) && (
                <GlassCard className="p-6 mb-6">
                    <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
                        <h2 className="text-lg font-semibold text-zinc-900">销售推进结果</h2>
                        <span className={cn("text-xs font-semibold px-3 py-1 rounded-full border", overallResultTone)}>
                            {overallResultLabel}
                        </span>
                    </div>
                    {report.main_issue ? (
                        <div className="rounded-xl border border-amber-100 bg-amber-50 p-4">
                            <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
                                <p className="text-xs font-semibold text-amber-700">本场销售主问题</p>
                                {reportLearningCue?.issueLabel ? (
                                    <span className="inline-flex rounded-full border border-amber-200 bg-white/80 px-2.5 py-1 text-xs font-medium text-amber-800">
                                        {reportLearningCue.issueLabel}
                                    </span>
                                ) : null}
                            </div>
                            <p className="text-sm text-amber-900">{report.main_issue.issue_text}</p>
                            <p className="text-xs text-amber-700 mt-2">
                                修正动作：{report.main_issue.recovery_rule}
                            </p>
                            <div className="mt-3 flex items-center justify-between gap-3 flex-wrap">
                                <p className="text-xs text-amber-700">{issueReplayHint}</p>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => openReplayDeepLink({
                                        focus: "main_issue",
                                        anchor: issueReplayAnchor,
                                    })}
                                    disabled={!issueReplayAvailable}
                                >
                                    定位问题片段
                                </Button>
                            </div>
                        </div>
                    ) : (
                        <p className="text-sm text-zinc-600">本场未产生主问题诊断结果。</p>
                    )}
                </GlassCard>
            )}

            {!isPresentationScenario && report.next_goal && (
                <GlassCard className="p-6 mb-6">
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                        <div>
                            <div className="flex items-center gap-2 mb-2 flex-wrap">
                                <h2 className="text-lg font-semibold text-zinc-900 flex items-center gap-2">
                                    <Target className="w-5 h-5 text-blue-600" />
                                    下一轮销售目标
                                </h2>
                                {reportLearningCue?.goalLabel ? (
                                    <span className="inline-flex rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-800">
                                        {reportLearningCue.goalLabel}
                                    </span>
                                ) : null}
                            </div>
                            <p className="text-sm text-zinc-700 mb-2">{report.next_goal.goal_text}</p>
                            <p className="text-xs text-zinc-500">判定条件：{report.next_goal.rule}</p>
                            <p className="text-xs text-blue-700 mt-2">{nextGoalReplayHint}</p>
                            {retryBlockedHint && (
                                <p className="text-xs text-amber-700 mt-2">{retryBlockedHint}</p>
                            )}
                            {retryHint && (
                                <p className="text-xs text-amber-700 mt-2">{retryHint}</p>
                            )}
                        </div>
                        <div className="flex flex-col items-stretch gap-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => openReplayDeepLink({
                                    focus: "next_goal",
                                    anchor: nextGoalReplayAnchor,
                                })}
                                className="whitespace-nowrap"
                                disabled={!nextGoalReplayAvailable}
                            >
                                定位目标片段
                            </Button>
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
                    </div>
                </GlassCard>
            )}

            {!isPresentationScenario && report.pass_flags && (
                <GlassCard className="p-6 mb-6">
                    <h2 className="text-lg font-semibold text-zinc-900 mb-3">销售推进基线</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div className={cn(
                            "rounded-xl border p-3",
                            report.pass_flags.pass_3min_flow
                                ? "bg-emerald-50 border-emerald-200"
                                : "bg-amber-50 border-amber-200",
                        )}>
                            <p className="text-xs font-semibold text-zinc-700">价值翻译达标</p>
                            <p className="text-sm mt-1 font-bold">
                                {report.pass_flags.pass_3min_flow ? "已达标" : "未达标"}
                            </p>
                        </div>
                        <div className={cn(
                            "rounded-xl border p-3",
                            report.pass_flags.pass_5turn_defense
                                ? "bg-emerald-50 border-emerald-200"
                                : "bg-amber-50 border-amber-200",
                        )}>
                            <p className="text-xs font-semibold text-zinc-700">异议承接达标</p>
                            <p className="text-sm mt-1 font-bold">
                                {report.pass_flags.pass_5turn_defense ? "已达标" : "未达标"}
                            </p>
                        </div>
                        <div className={cn(
                            "rounded-xl border p-3",
                            report.pass_flags.pass_4step_structure
                                ? "bg-emerald-50 border-emerald-200"
                                : "bg-amber-50 border-amber-200",
                        )}>
                            <p className="text-xs font-semibold text-zinc-700">证据推进达标</p>
                            <p className="text-sm mt-1 font-bold">
                                {report.pass_flags.pass_4step_structure ? "已达标" : "未达标"}
                            </p>
                        </div>
                    </div>
                </GlassCard>
            )}

            {!isPresentationScenario && conclusionEvidenceSections.length > 0 && (
                <GlassCard className="p-6 mb-6">
                    <h2 className="text-lg font-semibold text-zinc-900 mb-4">结论出处</h2>
                    <div className="space-y-4">
                        {conclusionEvidenceSections.map((section) => (
                            <div key={section.key} className="rounded-xl bg-zinc-50 p-4">
                                <p className="text-sm font-semibold text-zinc-900 mb-3">{section.title}</p>
                                <div className="flex flex-wrap gap-2">
                                    {section.rows.map((row) => (
                                        <span
                                            key={`${section.key}-${row.key}`}
                                            className="inline-flex items-center rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-medium text-zinc-700"
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
                <GlassCard className="p-6 mb-6">
                    <h2 className="text-lg font-semibold text-zinc-900 mb-4">证据降级状态</h2>
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
                                    <p className="text-sm font-semibold text-zinc-900">{item.label}</p>
                                    <span className={cn(
                                        "inline-flex rounded-full border px-2.5 py-1 text-xs font-medium",
                                        item.status === "ok"
                                            ? "border-emerald-200 bg-white text-emerald-700"
                                            : "border-amber-200 bg-white text-amber-700",
                                    )}>
                                        {item.status === "ok" ? "正常" : "降级"}
                                    </span>
                                </div>
                                <p className="text-sm text-zinc-700">{item.summary}</p>
                            </div>
                        ))}
                    </div>
                </GlassCard>
            )}

            {!isPresentationScenario && retrievalFacts && (
                <GlassCard className={cn("p-6 mb-6 border", retrievalClasses.card)}>
                    <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
                        <h2 className="text-lg font-semibold text-zinc-900">知识库检索事实</h2>
                        <span className={cn("text-xs font-semibold px-3 py-1 rounded-full border", retrievalClasses.badge)}>
                            {formatRetrievalStatusLabel(retrievalFacts.status)}
                        </span>
                    </div>

                    <p className={cn("text-sm mb-4", retrievalClasses.text)}>{retrievalFacts.summary}</p>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                        <div className="rounded-xl bg-white/70 p-3">
                            <div className="text-xs text-zinc-500">绑定知识库</div>
                            <div className="text-lg font-bold text-zinc-900">{retrievalFacts.knowledge_base_count}</div>
                        </div>
                        <div className="rounded-xl bg-white/70 p-3">
                            <div className="text-xs text-zinc-500">检索次数</div>
                            <div className="text-lg font-bold text-zinc-900">{retrievalFacts.attempt_count}</div>
                        </div>
                        <div className="rounded-xl bg-white/70 p-3">
                            <div className="text-xs text-zinc-500">命中次数</div>
                            <div className="text-lg font-bold text-zinc-900">{retrievalFacts.hit_count}</div>
                        </div>
                        <div className="rounded-xl bg-white/70 p-3">
                            <div className="text-xs text-zinc-500">命中率</div>
                            <div className="text-lg font-bold text-zinc-900">{(retrievalFacts.hit_rate * 100).toFixed(0)}%</div>
                        </div>
                    </div>

                    <div className="space-y-3">
                        {retrievalFacts.knowledge_base_ids.length > 0 && (
                            <p className="text-xs text-zinc-600">
                                绑定 KB：{retrievalFacts.knowledge_base_ids.join(" · ")}
                            </p>
                        )}

                        {retrievalLatestAttemptCopy && (
                            <div className="rounded-xl bg-white/70 p-3">
                                <p className="text-xs text-zinc-500 mb-1">最近一次检索</p>
                                <p className={cn("text-sm", retrievalClasses.text)}>{retrievalLatestAttemptCopy}</p>
                            </div>
                        )}

                        {retrievalResultSummaries.length > 0 && (
                            <div className="space-y-2">
                                <p className="text-xs text-zinc-500">最近命中的知识片段</p>
                                {retrievalResultSummaries.map((summary, index) => (
                                    <div key={`${summary.knowledge_base_id}-${index}`} className="rounded-xl border border-white/70 bg-white/70 p-3">
                                        <div className="flex items-center justify-between gap-3 flex-wrap mb-1">
                                            <p className="text-xs font-semibold text-zinc-700">
                                                {summary.knowledge_base_name || summary.knowledge_base_id}
                                            </p>
                                            {typeof summary.score === "number" && (
                                                <span className="text-xs text-zinc-500">相关度 {summary.score.toFixed(2)}</span>
                                            )}
                                        </div>
                                        {summary.snippet && (
                                            <p className="text-sm text-zinc-800">{summary.snippet}</p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}

                        {retrievalMissExplanation && (
                            <p className={cn("text-xs", retrievalClasses.note)}>{retrievalMissExplanation}</p>
                        )}

                        {retrievalFailureExplanation && (
                            <p className={cn("text-xs", retrievalClasses.note)}>{retrievalFailureExplanation}</p>
                        )}

                        {retrievalWeakEvidenceNote && (
                            <p className="text-xs text-amber-700">{retrievalWeakEvidenceNote}</p>
                        )}

                        {knowledgeCheck?.knowledge_answer_diagnostics && (
                            <div className="rounded-xl bg-white/70 p-3 space-y-2">
                                <p className="text-xs text-zinc-500 mb-1">回答级诊断</p>
                                {typeof knowledgeCheck.knowledge_answer_diagnostics.answerability === 'string' && knowledgeCheck.knowledge_answer_diagnostics.answerability && (
                                    <p className="text-sm text-zinc-800">
                                        回答约束：{knowledgeCheck.knowledge_answer_diagnostics.answerability as string}
                                    </p>
                                )}
                                {Array.isArray(knowledgeCheck.knowledge_answer_diagnostics.rewritten_queries)
                                    && knowledgeCheck.knowledge_answer_diagnostics.rewritten_queries.length > 0 && (
                                    <p className="text-xs text-zinc-600">
                                        检索改写：{(knowledgeCheck.knowledge_answer_diagnostics.rewritten_queries as string[]).join(" · ")}
                                    </p>
                                )}
                                {Array.isArray(knowledgeCheck.knowledge_answer_diagnostics.citations)
                                    && knowledgeCheck.knowledge_answer_diagnostics.citations.length > 0 && (
                                    <div className="space-y-2">
                                        {(knowledgeCheck.knowledge_answer_diagnostics.citations as Array<Record<string, unknown>>).map((citation, index) => {
                                            const kbName = typeof citation.knowledge_base_name === 'string' ? citation.knowledge_base_name : '';
                                            const docTitle = typeof citation.document_title === 'string' ? citation.document_title : '';
                                            const kbId = typeof citation.knowledge_base_id === 'string' ? citation.knowledge_base_id : '';
                                            const snippet = typeof citation.snippet === 'string' ? citation.snippet : '';
                                            const label = [kbName, docTitle].filter(Boolean).join(" · ") || kbId || "内部知识片段";
                                            return (
                                            <div key={`${docTitle || kbId || index}-${index}`} className="rounded-lg border border-white/70 bg-white/90 p-3">
                                                <p className="text-xs font-semibold text-zinc-700 mb-1">
                                                    {label}
                                                </p>
                                                {snippet && (
                                                    <p className="text-sm text-zinc-800">{snippet}</p>
                                                )}
                                            </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        )}

                        {knowledgeCheck && knowledgeCheck.recent_queries.length > 0 && (
                            <p className="text-xs text-zinc-500">
                                补充诊断记录：{knowledgeCheck.recent_queries.join(" · ")}
                            </p>
                        )}
                    </div>
                </GlassCard>
            )}

            {report.voice_policy_snapshot_ref && (
                <GlassCard className="p-6 mb-6">
                    <h2 className="text-lg font-semibold text-zinc-900 mb-4">会话策略快照基线</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                        <div className="rounded-xl bg-zinc-50 p-3">
                            <div className="text-xs text-zinc-500">语音模式</div>
                            <div className="font-semibold text-zinc-900 mt-1">
                                {report.voice_policy_snapshot_ref.voice_mode || "--"}
                            </div>
                        </div>
                        <div className="rounded-xl bg-zinc-50 p-3">
                            <div className="text-xs text-zinc-500">Runtime Profile</div>
                            <div className="font-semibold text-zinc-900 mt-1 break-all">
                                {report.voice_policy_snapshot_ref.runtime_profile_id || "--"}
                            </div>
                        </div>
                        <div className="rounded-xl bg-zinc-50 p-3">
                            <div className="text-xs text-zinc-500">解析时间</div>
                            <div className="font-semibold text-zinc-900 mt-1">
                                {formatSnapshotTime(report.voice_policy_snapshot_ref.resolved_at)}
                            </div>
                        </div>
                    </div>
                    <div className="text-xs text-zinc-500 mt-3">
                        来源链路：
                        {Object.entries(report.voice_policy_snapshot_ref.source || {})
                            .map(([key, value]) => `${key}:${value}`)
                            .join(" / ") || "--"}
                    </div>
                </GlassCard>
            )}

            {!isPresentationScenario && (
                <GlassCard className="p-6 mb-6">
                    <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
                        <h2 className="text-lg font-semibold text-zinc-900">销售能力总览</h2>
                        {report.evidence_completeness?.legacy_score_key_used ? (
                            <span className="text-xs text-zinc-500">兼容了 legacy score key</span>
                        ) : null}
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {dimensionScores.map((dimension) => (
                            <div key={dimension.name} className="rounded-xl bg-zinc-50 p-4">
                                <div className="flex items-center justify-between gap-3 mb-2">
                                    <p className="text-sm font-semibold text-zinc-700">{dimension.name}</p>
                                    <span className={cn("text-lg font-bold", getScoreColor(dimension.score))}>
                                        {dimension.score.toFixed(0)}
                                    </span>
                                </div>
                                <div className="relative w-full h-2 bg-zinc-200 rounded-full mb-2">
                                    <div
                                        className={cn(
                                            "absolute top-0 left-0 h-full rounded-full",
                                            dimension.score >= 80
                                                ? "bg-green-500"
                                                : dimension.score >= 60
                                                    ? "bg-yellow-500"
                                                    : "bg-red-500",
                                        )}
                                        style={{ width: `${dimension.score}%` }}
                                    />
                                </div>
                                <p className="text-xs text-zinc-500">{dimension.description}</p>
                            </div>
                        ))}
                    </div>
                </GlassCard>
            )}

            {!isPresentationScenario && report.stage_summary.length > 0 && (
                <GlassCard className="p-6 mb-6">
                    <h2 className="text-lg font-semibold text-zinc-900 mb-4">阶段事实</h2>
                    <div className="space-y-3">
                        {report.stage_summary.map((stage) => (
                            <div key={`${stage.stage}-${stage.duration_ms}`} className="flex items-center gap-4 p-3 bg-zinc-50 rounded-lg">
                                <div className="w-10 h-10 rounded-full bg-zinc-200 flex items-center justify-center font-semibold text-zinc-700">
                                    {stage.score.toFixed(0)}
                                </div>
                                <div className="flex-1">
                                    <div className="flex justify-between mb-1 gap-3 flex-wrap">
                                        <span className="text-sm font-medium">{formatSessionStageLabel(stage.stage)}</span>
                                        <span className={cn("text-sm font-semibold", getScoreColor(stage.score))}>
                                            {stage.score.toFixed(0)}分
                                        </span>
                                    </div>
                                    <p className="text-xs text-zinc-600">
                                        时长 {(stage.duration_ms / 1000).toFixed(0)} 秒
                                    </p>
                                </div>
                            </div>
                        ))}
                    </div>
                </GlassCard>
            )}

            {hasEnhancedInsights(enhancedReport) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    {enhancedReport?.key_strengths?.length ? (
                        <GlassCard className="p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <CheckCircle className="w-5 h-5 text-green-500" />
                                <h3 className="font-semibold text-zinc-900">综合洞察：主要优势</h3>
                            </div>
                            <ul className="space-y-2">
                                {enhancedReport.key_strengths.map((item, index) => (
                                    <li key={`${item}-${index}`} className="flex items-start gap-2 text-sm text-zinc-700">
                                        <span className="w-1 h-1 rounded-full bg-green-500 mt-2" />
                                        {item}
                                    </li>
                                ))}
                            </ul>
                        </GlassCard>
                    ) : null}

                    {enhancedReport?.key_improvements?.length ? (
                        <GlassCard className="p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <AlertTriangle className="w-5 h-5 text-amber-500" />
                                <h3 className="font-semibold text-zinc-900">综合洞察：改进建议</h3>
                            </div>
                            <ul className="space-y-2">
                                {enhancedReport.key_improvements.map((item, index) => (
                                    <li key={`${item}-${index}`} className="flex items-start gap-2 text-sm text-zinc-700">
                                        <span className="w-1 h-1 rounded-full bg-amber-500 mt-2" />
                                        {item}
                                    </li>
                                ))}
                            </ul>
                        </GlassCard>
                    ) : null}
                </div>
            )}

            {enhancedReport?.detailed_feedback?.trim() && (
                <GlassCard className="p-6 mb-6">
                    <h2 className="text-lg font-semibold text-zinc-900 mb-3">综合洞察补充</h2>
                    <p className="text-sm leading-7 text-zinc-700 whitespace-pre-wrap">
                        {enhancedReport.detailed_feedback}
                    </p>
                </GlassCard>
            )}

            {highlightsLoading ? (
                <GlassCard className="p-6 mb-6">
                    <div className="flex items-center gap-3">
                        <div className="w-5 h-5 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />
                        <span className="text-sm text-zinc-500">加载高光片段中...</span>
                    </div>
                </GlassCard>
            ) : highlightsUnavailableHint ? (
                <GlassCard className="p-4 mb-6 border border-slate-200 bg-slate-50/80">
                    <p className="text-sm text-slate-700">{highlightsUnavailableHint}</p>
                </GlassCard>
            ) : highlightsData && highlightsData.highlights.length > 0 ? (
                <GlassCard className="p-6 mb-6">
                    <div className="flex items-center gap-2 mb-6">
                        <Sparkles className="w-5 h-5 text-amber-500" />
                        <h2 className="text-lg font-semibold text-zinc-900">高光片段</h2>
                        <span className="text-xs text-zinc-500 ml-2">AI 识别的关键 moments</span>
                    </div>
                    <p className="text-xs text-zinc-500 mb-4">点击高光卡片可直接跳到当前 replay 中对应的轮次。</p>
                    <HighlightList
                        highlights={highlightsData.highlights}
                        totalGood={highlightsData.total_good}
                        totalBad={highlightsData.total_bad}
                        onJumpToMessage={(turnNumber) => openReplayDeepLink({
                            focus: "learning_evidence",
                            turnNumber,
                        })}
                    />
                </GlassCard>
            ) : (
                <GlassCard className="p-4 mb-6 border border-zinc-200 bg-zinc-50/70">
                    <p className="text-sm text-zinc-600">本次训练暂未识别出高光片段。</p>
                </GlassCard>
            )}

            {practiceSuggestions.length > 0 && (
                <GlassCard className="p-6 mb-6">
                    <div className="flex items-center gap-2 mb-4">
                        <Lightbulb className="w-5 h-5 text-amber-500" />
                        <h2 className="text-lg font-semibold text-zinc-900">
                            {isPresentationScenario ? "复盘建议" : "练习建议"}
                        </h2>
                    </div>
                    <ul className="space-y-2">
                        {practiceSuggestions.map((item, index) => (
                            <li key={`${item}-${index}`} className="flex items-start gap-2 text-sm text-zinc-700">
                                <Target className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
                                {item}
                            </li>
                        ))}
                    </ul>
                </GlassCard>
            )}

            <AudioAuditCard audioAudit={report.audio_audit} sessionId={sessionId} />
        </div>
    );
}
                          <li key={`${item}-${index}`} className="flex items-start gap-2 text-sm text-zinc-700">
                                <Target className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
                                {item}
                            </li>
                        ))}
                    </ul>
                </GlassCard>
            )}

            <AudioAuditCard audioAudit={report.audio_audit} sessionId={sessionId} />
        </div>
    );
}
   );
}
