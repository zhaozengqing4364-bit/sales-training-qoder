"use client";

/**
 * Comprehensive Report Display Page (C7)
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { ArrowLeft, CheckCircle, AlertTriangle, Lightbulb, Target, Download, Home, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { HighlightList } from "@/components/highlights";
import { api, ApiRequestError, getApiErrorMessage } from "@/lib/api/client";
import { ComprehensiveReport, KnowledgeCheckDiagnostics, HighlightsResponse } from "@/lib/api/types";
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

export default function ComprehensiveReportPage() {
    const router = useRouter();
    const params = useParams();
    const sessionId = params.sessionId as string;
    const [loading, setLoading] = useState(true);
    const [report, setReport] = useState<ComprehensiveReport | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [knowledgeCheck, setKnowledgeCheck] = useState<KnowledgeCheckDiagnostics | null>(null);
    const [highlightsData, setHighlightsData] = useState<HighlightsResponse | null>(null);
    const [highlightsLoading, setHighlightsLoading] = useState(false);

    const loadReport = useCallback(async () => {
        const loadQuickReportFallback = async () => {
            const quickReport = await api.sessions.getReport(sessionId);
            setReport({
                session_id: quickReport.session_id,
                generated_at: new Date().toISOString(),
                overall_score: quickReport.overall_score,
                dimension_scores: [
                    {
                        name: "逻辑性",
                        score: quickReport.logic_score,
                        weight: 0.34,
                        description: "结构化表达与论证清晰度",
                    },
                    {
                        name: "准确性",
                        score: quickReport.accuracy_score,
                        weight: 0.33,
                        description: "信息准确与事实一致性",
                    },
                    {
                        name: "完整性",
                        score: quickReport.completeness_score,
                        weight: 0.33,
                        description: "要点覆盖与回答完整性",
                    },
                ],
                stage_summaries: [],
                key_strengths: [],
                key_improvements: [],
                detailed_feedback: "",
                recommendations: quickReport.suggestions || [],
                voice_policy_snapshot_ref: quickReport.voice_policy_snapshot_ref,
            });
        };

        try {
            // 优先走综合评测报告，失败时再回退到基础报告。
            const data = await api.admin.getComprehensiveReport(sessionId);
            setReport(data);
        } catch (err) {
            const isNotFound = err instanceof ApiRequestError
                ? err.errorCode === "[REPORT_NOT_FOUND]" || err.errorCode === "[SESSION_NOT_FOUND]" || err.status === 404
                : (err instanceof Error && /404|not found/i.test(err.message));
            if (isNotFound) {
                try {
                    const generated = await api.admin.generateComprehensiveReport(sessionId);
                    setReport(generated);
                } catch {
                    try {
                        await loadQuickReportFallback();
                    } catch (quickErr) {
                        setError(getApiErrorMessage(quickErr));
                    }
                }
            } else {
                try {
                    await loadQuickReportFallback();
                } catch (quickErr) {
                    setError(getApiErrorMessage(quickErr) || getApiErrorMessage(err));
                }
            }
        } finally {
            setLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        loadReport();
    }, [loadReport]);

    useEffect(() => {
        let cancelled = false;

        api.sessions.getKnowledgeCheck(sessionId)
            .then((data) => {
                if (!cancelled) {
                    setKnowledgeCheck(data);
                }
            })
            .catch(() => {
                if (!cancelled) {
                    setKnowledgeCheck(null);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [sessionId]);

    useEffect(() => {
        let cancelled = false;

        setHighlightsLoading(true);
        api.sessions.getHighlights(sessionId)
            .then((data) => {
                if (!cancelled) {
                    setHighlightsData(data);
                }
            })
            .catch(() => {
                if (!cancelled) {
                    setHighlightsData(null);
                }
            })
            .finally(() => {
                if (!cancelled) {
                    setHighlightsLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [sessionId]);

    const goHome = () => {
        router.push("/");
    };

    if (loading) {
        return (
            <div className="container mx-auto px-4 py-12 text-center">
                <StatusIndicator status="loading" />
                <p className="mt-4 text-zinc-500">加载报告中...</p>
            </div>
        );
    }

    if (error || !report) {
        return (
            <div className="container mx-auto px-4 py-12 text-center">
                <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
                <p className="text-zinc-600">{error || "报告不存在"}</p>
                <Button variant="outline" onClick={goHome} className="mt-4">返回首页</Button>
            </div>
        );
    }

    const getScoreColor = (score: number) => score >= 80 ? "text-green-600" : score >= 60 ? "text-yellow-600" : "text-red-600";
    const knowledgeStatusTone = knowledgeCheck?.status === "hit"
        ? "text-green-700 bg-green-50 border-green-200"
        : knowledgeCheck?.status === "miss"
            ? "text-amber-700 bg-amber-50 border-amber-200"
            : knowledgeCheck?.status === "disabled" || knowledgeCheck?.status === "no_knowledge_base"
                ? "text-red-700 bg-red-50 border-red-200"
                : "text-slate-700 bg-slate-50 border-slate-200";

    return (
        <div className="container mx-auto px-4 py-6 max-w-5xl">
            <div className="flex items-center justify-between mb-6">
                <Button variant="ghost" size="sm" onClick={goHome}>
                    <ArrowLeft className="w-4 h-4 mr-2" />返回首页
                </Button>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm">
                        <Download className="w-4 h-4 mr-2" />导出报告
                    </Button>
                    <Button variant="primary" size="sm" onClick={goHome}>
                        <Home className="w-4 h-4 mr-2" />退出到首页
                    </Button>
                </div>
            </div>

            <GlassCard className="p-6 mb-6">
                <div className="text-center">
                    <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white mb-4">
                        <span className="text-3xl font-bold">{report.overall_score.toFixed(0)}</span>
                    </div>
                    <h1 className="text-2xl font-bold text-zinc-900 mb-2">综合评估报告</h1>
                    <p className={cn("text-lg font-medium", getScoreColor(report.overall_score))}>
                        {report.overall_score >= 90 ? "优秀" : report.overall_score >= 80 ? "良好" : report.overall_score >= 60 ? "及格" : "待改进"}
                    </p>
                </div>
            </GlassCard>

            {knowledgeCheck && (
                <GlassCard className="p-6 mb-6">
                    <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
                        <h2 className="text-lg font-semibold text-zinc-900">知识库命中检测</h2>
                        <span className={cn("text-xs font-semibold px-3 py-1 rounded-full border", knowledgeStatusTone)}>
                            {knowledgeCheck.status === "hit"
                                ? "已命中"
                                : knowledgeCheck.status === "miss"
                                    ? "未命中"
                                    : knowledgeCheck.status === "not_triggered"
                                        ? "未触发检索"
                                        : knowledgeCheck.status === "no_knowledge_base"
                                            ? "未绑定知识库"
                                            : "已关闭检索"}
                        </span>
                    </div>

                    <p className="text-sm text-zinc-600 mb-4">{knowledgeCheck.summary}</p>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                        <div className="rounded-xl bg-zinc-50 p-3">
                            <div className="text-xs text-zinc-500">绑定知识库</div>
                            <div className="text-lg font-bold text-zinc-900">{knowledgeCheck.knowledge_base_count}</div>
                        </div>
                        <div className="rounded-xl bg-zinc-50 p-3">
                            <div className="text-xs text-zinc-500">检索次数</div>
                            <div className="text-lg font-bold text-zinc-900">{knowledgeCheck.attempt_count}</div>
                        </div>
                        <div className="rounded-xl bg-zinc-50 p-3">
                            <div className="text-xs text-zinc-500">命中问答</div>
                            <div className="text-lg font-bold text-zinc-900">{knowledgeCheck.hit_query_count}</div>
                        </div>
                        <div className="rounded-xl bg-zinc-50 p-3">
                            <div className="text-xs text-zinc-500">命中率</div>
                            <div className="text-lg font-bold text-zinc-900">{(knowledgeCheck.hit_rate * 100).toFixed(0)}%</div>
                        </div>
                    </div>

                    {knowledgeCheck.last_query && (
                        <div className="rounded-xl bg-blue-50 border border-blue-100 p-3 mb-3">
                            <div className="text-xs text-blue-600 mb-1">最近一次检索问题</div>
                            <div className="text-sm text-blue-900">{knowledgeCheck.last_query}</div>
                            <div className="text-xs text-blue-700 mt-1">命中片段数：{knowledgeCheck.last_result_count}</div>
                        </div>
                    )}

                    {knowledgeCheck.recent_queries.length > 0 && (
                        <div className="text-xs text-zinc-500">
                            近期检索：{knowledgeCheck.recent_queries.join(" · ")}
                        </div>
                    )}
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

            <GlassCard className="p-6 mb-6">
                <h2 className="text-lg font-semibold text-zinc-900 mb-4">分项评分</h2>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    {report.dimension_scores.map((dim) => (
                        <div key={dim.name} className="text-center">
                            <div className="relative w-full h-2 bg-zinc-200 rounded-full mb-2">
                                <div
                                    className={cn("absolute top-0 left-0 h-full rounded-full",
                                        dim.score >= 80 ? "bg-green-500" : dim.score >= 60 ? "bg-yellow-500" : "bg-red-500")}
                                    style={{ width: `${dim.score}%` }}
                                />
                            </div>
                            <p className="text-2xl font-bold text-zinc-900">{dim.score.toFixed(0)}</p>
                            <p className="text-xs text-zinc-600">{dim.name}</p>
                        </div>
                    ))}
                </div>
            </GlassCard>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <GlassCard className="p-6">
                    <div className="flex items-center gap-2 mb-4">
                        <CheckCircle className="w-5 h-5 text-green-500" />
                        <h3 className="font-semibold text-zinc-900">主要优势</h3>
                    </div>
                    <ul className="space-y-2">
                        {report.key_strengths.map((s, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-zinc-700">
                                <span className="w-1 h-1 rounded-full bg-green-500 mt-2" />{s}
                            </li>
                        ))}
                    </ul>
                </GlassCard>

                <GlassCard className="p-6">
                    <div className="flex items-center gap-2 mb-4">
                        <AlertTriangle className="w-5 h-5 text-amber-500" />
                        <h3 className="font-semibold text-zinc-900">改进建议</h3>
                    </div>
                    <ul className="space-y-2">
                        {report.key_improvements.map((imp, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-zinc-700">
                                <span className="w-1 h-1 rounded-full bg-amber-500 mt-2" />{imp}
                            </li>
                        ))}
                    </ul>
                </GlassCard>
            </div>

            {report.stage_summaries.length > 0 && (
                <GlassCard className="p-6 mb-6">
                    <h2 className="text-lg font-semibold text-zinc-900 mb-4">阶段分析</h2>
                    <div className="space-y-3">
                        {report.stage_summaries.map((stage) => (
                            <div key={stage.stage_number} className="flex items-center gap-4 p-3 bg-zinc-50 rounded-lg">
                                <div className="w-10 h-10 rounded-full bg-zinc-200 flex items-center justify-center font-semibold text-zinc-700">
                                    {stage.stage_number}
                                </div>
                                <div className="flex-1">
                                    <div className="flex justify-between mb-1">
                                        <span className="text-sm font-medium">第{stage.stage_number}阶段</span>
                                        <span className={cn("text-sm font-semibold", getScoreColor(stage.average_score))}>
                                            {stage.average_score.toFixed(0)}分
                                        </span>
                                    </div>
                                    <p className="text-xs text-zinc-600">{stage.summary}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </GlassCard>
            )}

            {/* Highlights Section */}
            {highlightsLoading ? (
                <GlassCard className="p-6 mb-6">
                    <div className="flex items-center gap-3">
                        <div className="w-5 h-5 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />
                        <span className="text-sm text-zinc-500">加载高光片段中...</span>
                    </div>
                </GlassCard>
            ) : highlightsData && highlightsData.highlights.length > 0 ? (
                <GlassCard className="p-6 mb-6">
                    <div className="flex items-center gap-2 mb-6">
                        <Sparkles className="w-5 h-5 text-amber-500" />
                        <h2 className="text-lg font-semibold text-zinc-900">高光片段</h2>
                        <span className="text-xs text-zinc-500 ml-2">
                            AI 识别的关键 moments
                        </span>
                    </div>
                    <HighlightList
                        highlights={highlightsData.highlights}
                        totalGood={highlightsData.total_good}
                        totalBad={highlightsData.total_bad}
                    />
                </GlassCard>
            ) : null}

            {report.recommendations.length > 0 && (
                <GlassCard className="p-6">
                    <div className="flex items-center gap-2 mb-4">
                        <Lightbulb className="w-5 h-5 text-amber-500" />
                        <h2 className="text-lg font-semibold text-zinc-900">练习建议</h2>
                    </div>
                    <ul className="space-y-2">
                        {report.recommendations.map((rec, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-zinc-700">
                                <Target className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />{rec}
                            </li>
                        ))}
                    </ul>
                </GlassCard>
            )}
        </div>
    );
}
