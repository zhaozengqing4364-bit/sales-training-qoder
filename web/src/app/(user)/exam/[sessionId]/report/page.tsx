"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  FileText,
  Home,
  Sparkles,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { api, ApiRequestError, getApiErrorMessage } from "@/lib/api/client";
import type { ExaminerSessionReport } from "@/lib/api/types";
import { cn } from "@/lib/utils";

function completionReasonLabel(reason: string): string {
  switch (reason) {
    case "all_questions_answered":
      return "全部题目已答完";
    case "timed_out":
      return "考核时间已到";
    case "empty_question_bank":
      return "题库为空";
    case "reconnected":
      return "重连后考核已结束";
    case "in_progress":
      return "考核进行中";
    default:
      return reason || "考核已完成";
  }
}

function scoreTone(score: number): string {
  if (score >= 80) return "text-emerald-600";
  if (score >= 60) return "text-amber-600";
  return "text-rose-600";
}

function scoreRingColor(score: number): string {
  if (score >= 80) return "stroke-emerald-500";
  if (score >= 60) return "stroke-amber-500";
  return "stroke-rose-500";
}

/** 将后端评分占位符转为用户可读文案（兼容旧报告数据） */
function displayExamFeedback(feedback: string | undefined): string {
  const raw = (feedback ?? "").trim();
  if (!raw) return "暂无评语";
  if (raw === "scoring_unavailable") {
    return "AI 评分服务当时不可用，未生成评语。请重新完成一次考核，或联系管理员检查大模型配置。";
  }
  return raw;
}

function ScoreRing({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, score));
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div className="relative mx-auto h-36 w-36">
      <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
        <circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          strokeWidth="10"
          className="stroke-slate-200"
        />
        <circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={cn("transition-all duration-700", scoreRingColor(clamped))}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("text-4xl font-black tabular-nums", scoreTone(clamped))}>
          {score.toFixed(1)}
        </span>
        <span className="text-xs font-medium text-slate-500">平均分</span>
      </div>
    </div>
  );
}

export default function ExamReportPage() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const sessionId = params.sessionId;

  const [report, setReport] = useState<ExaminerSessionReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadReport = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.learnerStudy.getExamReport(sessionId);
      setReport(data);
    } catch (err) {
      setReport(null);
      setError(getApiErrorMessage(err as ApiRequestError));
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void loadReport();
  }, [loadReport]);

  const passLabel = useMemo(() => {
    if (!report) return "";
    return report.passed ? "考核通过" : "未达及格线";
  }, [report]);

  return (
    <div className="min-h-screen bg-[#FAFAF9] relative overflow-hidden">
      <div className="absolute top-[-20%] left-[-10%] w-[1000px] h-[1000px] bg-blue-100/40 rounded-full blur-[120px] opacity-60" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[1000px] h-[1000px] bg-purple-100/40 rounded-full blur-[120px] opacity-60" />

      <div className="relative z-10 mx-auto max-w-4xl px-4 py-6 md:py-10">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <Button
            variant="ghost"
            className="rounded-full text-slate-600 hover:text-slate-900"
            onClick={() => router.back()}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回
          </Button>
          <Button asChild variant="outline" className="rounded-full">
            <Link href="/learning-path">
              <Home className="mr-2 h-4 w-4" />
              学习路径
            </Link>
          </Button>
        </div>

        {isLoading && (
          <GlassCard className="p-10 text-center">
            <StatusIndicator status="loading" message="正在生成考核报告..." />
          </GlassCard>
        )}

        {!isLoading && error && (
          <GlassCard className="p-10 text-center space-y-4">
            <StatusIndicator status="error" message={error} />
            <Button onClick={() => void loadReport()} className="rounded-full">
              重新加载
            </Button>
          </GlassCard>
        )}

        {!isLoading && report && (
          <div className="space-y-6">
            <GlassCard className="p-6 md:p-8">
              <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-indigo-700">
                    <Sparkles className="h-5 w-5" />
                    <span className="text-sm font-semibold">AI 考核报告</span>
                  </div>
                  <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">
                    考核结果总览
                  </h1>
                  <p className="text-sm text-slate-600">
                    {completionReasonLabel(report.completion_reason)}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={report.passed ? "green" : "red"}>
                      {passLabel}
                    </Badge>
                    <Badge variant="gray">
                      已答 {report.answered_count}/{report.total_questions} 题
                    </Badge>
                  </div>
                </div>

                <ScoreRing score={report.overall_score} />
              </div>
            </GlassCard>

            <div className="space-y-4">
              <div className="flex items-center gap-2 px-1">
                <FileText className="h-5 w-5 text-slate-600" />
                <h2 className="text-lg font-bold text-slate-900">逐题评分详情</h2>
              </div>

              {report.items.map((item) => (
                <GlassCard key={`${item.question_id}-${item.question_index}`} className="p-5 md:p-6">
                  <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="gray">第 {item.question_index + 1} 题</Badge>
                        <span className={cn("text-lg font-bold tabular-nums", scoreTone(item.score))}>
                          {item.score} 分
                        </span>
                        {item.score >= 60 ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                        ) : (
                          <XCircle className="h-4 w-4 text-rose-500" />
                        )}
                      </div>
                      {item.title && (
                        <h3 className="text-base font-semibold text-slate-900">{item.title}</h3>
                      )}
                    </div>
                  </div>

                  {item.stem && (
                    <div className="mb-4 rounded-xl border border-slate-100 bg-white/70 p-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                        题目
                      </p>
                      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{item.stem}</p>
                    </div>
                  )}

                  <div className="mb-4 rounded-xl border border-slate-100 bg-white/70 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                      你的回答
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">
                      {item.answer_text || "（未作答）"}
                    </p>
                  </div>

                  <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-indigo-500">
                      AI 评语
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-indigo-900">
                      {displayExamFeedback(item.feedback)}
                    </p>
                  </div>
                </GlassCard>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
