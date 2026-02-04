"use client";

/**
 * Comprehensive Report Display Page (C7)
 */

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { ArrowLeft, CheckCircle, AlertTriangle, Lightbulb, Target, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { api } from "@/lib/api/client";
import { ComprehensiveReport } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export default function ComprehensiveReportPage() {
    const router = useRouter();
    const params = useParams();
    const sessionId = params.sessionId as string;
    const [loading, setLoading] = useState(true);
    const [report, setReport] = useState<ComprehensiveReport | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadReport();
    }, [sessionId]);

    const loadReport = async () => {
        try {
            const data = await api.admin.getComprehensiveReport(sessionId);
            setReport(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : "加载失败");
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="container mx-auto px-4 py-12 text-center">
                <StatusIndicator status="processing" size={32} />
                <p className="mt-4 text-zinc-500">加载报告中...</p>
            </div>
        );
    }

    if (error || !report) {
        return (
            <div className="container mx-auto px-4 py-12 text-center">
                <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
                <p className="text-zinc-600">{error || "报告不存在"}</p>
                <Button variant="outline" onClick={() => router.back()} className="mt-4">返回</Button>
            </div>
        );
    }

    const getScoreColor = (score: number) => score >= 80 ? "text-green-600" : score >= 60 ? "text-yellow-600" : "text-red-600";

    return (
        <div className="container mx-auto px-4 py-6 max-w-5xl">
            <div className="flex items-center justify-between mb-6">
                <Button variant="ghost" size="sm" onClick={() => router.back()}>
                    <ArrowLeft className="w-4 h-4 mr-2" />返回
                </Button>
                <Button variant="outline" size="sm">
                    <Download className="w-4 h-4 mr-2" />导出报告
                </Button>
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
