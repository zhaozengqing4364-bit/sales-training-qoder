"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2, Clock3, Lock, RotateCcw, Route } from "lucide-react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import { LearningPathNextTask, LearningPathResponse, LearningPathStage } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";

const stateCopy: Record<LearningPathStage["state"], string> = {
    locked: "未解锁",
    available: "可开始",
    in_progress: "进行中",
    completed: "已完成",
    failed: "未通过",
    pending_review: "等待主管复核",
    retraining_required: "需要复训",
};

function stageIcon(stage: LearningPathStage) {
    if (stage.state === "completed") return <CheckCircle2 className="w-5 h-5" />;
    if (stage.state === "locked") return <Lock className="w-5 h-5" />;
    if (stage.state === "failed" || stage.state === "retraining_required") return <RotateCcw className="w-5 h-5" />;
    return <Clock3 className="w-5 h-5" />;
}

function stageClassName(stage: LearningPathStage): string {
    if (stage.state === "completed") return "border-emerald-100 bg-emerald-50/80 text-emerald-700";
    if (stage.state === "locked") return "border-slate-100 bg-slate-50/80 text-slate-500";
    if (stage.state === "pending_review") return "border-amber-100 bg-amber-50/80 text-amber-700";
    if (stage.state === "failed" || stage.state === "retraining_required") return "border-red-100 bg-red-50/80 text-red-700";
    return "border-blue-100 bg-blue-50/80 text-blue-700";
}

function formatCompletionPolicy(policy: Record<string, unknown>): string {
    const parts = [
        typeof policy.min_score === "number" ? `最低 ${policy.min_score} 分` : null,
        typeof policy.min_rounds === "number" ? `至少 ${policy.min_rounds} 轮` : null,
        typeof policy.max_duration_seconds === "number" ? `限时 ${Math.max(1, Math.round(policy.max_duration_seconds / 60))} 分钟` : null,
    ].filter(Boolean);
    return parts.length > 0 ? parts.join(" · ") : "按模板默认完成标准";
}

function nextTaskHref(nextTask: LearningPathNextTask): string {
    if (nextTask.primary_cta === "continue learning" && nextTask.learning_content_id) {
        return `/study/${encodeURIComponent(nextTask.learning_content_id)}`;
    }
    return "/training";
}

function stageNameByKey(key: string, stages: LearningPathStage[]): string | null {
    const found = stages.find((s) => s.template_stage_key === key);
    return found?.name ?? null;
}

function formatStageResult(result: Record<string, unknown> | null | undefined): string {
    if (!result || Object.keys(result).length === 0) return "";
    const parts: string[] = [];

    if (typeof result.score === "number") {
        parts.push(`得分：${result.score}`);
    }
    if ("passed" in result && result.passed != null) {
        parts.push(result.passed ? "通过：已通过" : "通过：未通过");
    }
    if (typeof result.attempts === "number") {
        parts.push(`尝试次数：${result.attempts}`);
    }
    if ("completed_at" in result && result.completed_at != null && result.completed_at !== "") {
        parts.push("已完成");
    }

    if (parts.length > 0) return parts.join("，");
    return "阶段结果已记录";
}

export default function LearningPathPage() {
    const router = useRouter();
    const [path, setPath] = useState<LearningPathResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        void api.learningPath.getMine()
            .then((value) => {
                if (!cancelled) {
                    setPath(value);
                    setError(null);
                }
            })
            .catch((err) => {
                if (!cancelled) setError(getApiErrorMessage(err));
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, []);

    if (isLoading) {
        return (
            <main className="min-h-screen bg-slate-50 px-6 py-8">
                <GlassCard className="p-8" role="status" aria-live="polite" aria-busy="true">
                    <p className="text-slate-600 font-medium">学习路径加载中...</p>
                </GlassCard>
            </main>
        );
    }

    if (error || path === null) {
        return (
            <main className="min-h-screen bg-slate-50 px-6 py-8">
                <GlassCard className="p-8 border border-red-100 bg-red-50/80">
                    <p className="text-sm font-bold text-red-600">学习路径暂不可用</p>
                    <p className="text-slate-600 mt-2">{error ?? "无法读取学习路径。"}</p>
                    <Button asChild className="rounded-full mt-5 bg-slate-900 text-white">
                        <Link href="/training">先去训练大厅</Link>
                    </Button>
                </GlassCard>
            </main>
        );
    }

    return (
        <main className="min-h-screen bg-slate-50 px-4 py-8 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-6xl space-y-8">
                <section className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-blue-600">
                            <Route className="w-4 h-4" /> LearningPath
                        </div>
                        <h1 className="text-4xl font-black text-slate-900 mt-4">我的学习路径</h1>
                        <p className="text-slate-500 mt-3 max-w-2xl">
                            {path.path_type === "weakness_driven"
                                ? "根据最近报告弱项排序推荐，原因可追溯到报告、维度和分数。"
                                : "暂无足够报告证据，先从默认路径开始。"}
                        </p>
                    </div>
                    <Button asChild className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
                        <Link href={nextTaskHref(path.next_task)}>
                            {path.next_task.primary_cta} <ArrowRight className="ml-2 w-4 h-4" />
                        </Link>
                    </Button>
                </section>

                <GlassCard className="p-6 border border-blue-100 bg-white/80">
                    <p className="text-xs font-bold uppercase tracking-wider text-blue-500">下一步任务</p>
                    <h2 className="text-2xl font-black text-slate-900 mt-2">{path.next_task.title}</h2>
                    <p className="text-sm text-slate-600 mt-3">
                        状态：{stateCopy[path.next_task.state]}
                        {path.next_task.estimated_duration_minutes ? ` · 建议 ${path.next_task.estimated_duration_minutes} 分钟` : ""}
                    </p>
                    <p className="mt-3 text-sm text-slate-600">推荐原因：{path.next_task.reason}</p>
                        {path.next_task.failure_reason && (
                            <p className="mt-3 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">
                                失败原因：{path.next_task.failure_reason}
                            </p>
                        )}
                        {path.next_task.retry_action && (
                            <p className="mt-3 text-sm font-bold text-blue-600">复训动作：{path.next_task.retry_action}</p>
                        )}
                </GlassCard>

                <section className="grid gap-4">
                    {path.stages.length === 0 ? (
                        <EmptyState
                            title="学习路径阶段暂未配置"
                            description="当前还没有可展示的阶段，请先进入训练大厅完成一次训练，或联系管理员发布课程路径。"
                            actionLabel="去训练大厅"
                            onAction={() => router.push("/training")}
                        />
                    ) : path.stages.map((stage) => (
                        <GlassCard key={stage.template_stage_key} className="p-5 bg-white/80">
                            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                                <div className="flex gap-4">
                                    <div className={cn("w-11 h-11 rounded-2xl border flex items-center justify-center", stageClassName(stage))}>
                                        {stageIcon(stage)}
                                    </div>
                                    <div>
                                        <h3 className="font-black text-slate-900">{stage.name}</h3>
                                         {stage.prerequisites.length > 0 && (
                                            <p className="text-sm text-slate-600 mt-2">
                                                前置条件：{stage.prerequisites.map((item) => stageNameByKey(item.template_stage_key, path.stages) ?? "前置阶段").join("、")}
                                            </p>
                                        )}
                                        <p className="text-sm text-slate-600 mt-2">
                                            完成标准：{formatCompletionPolicy(stage.completion_policy)}
                                        </p>
                                        {stage.result && Object.keys(stage.result).length > 0 && (
                                            <p className="text-sm text-slate-600 mt-2">
                                                阶段结果：{formatStageResult(stage.result)}
                                            </p>
                                        )}
                                        {stage.failure_reason && (
                                            <p className="text-sm text-red-600 mt-2">失败原因：{stage.failure_reason}</p>
                                        )}
                                        {stage.retry_action && (
                                            <p className="text-sm text-blue-600 mt-2">复训动作：{stage.retry_action}</p>
                                        )}
                                         {stage.state === "pending_review" && (
                                             <p className="text-sm text-amber-700 mt-2">认证路径已进入等待主管复核占位状态。</p>
                                         )}
                                        {stage.state === "retraining_required" && (
                                            <p className="text-sm text-red-700 mt-2">主管已要求复训，请完成复训后再回到认证路径。</p>
                                        )}
                                     </div>
                                 </div>
                                <div className="flex flex-col items-start gap-2 md:items-end">
                                    <span className={cn("rounded-full px-3 py-1 text-xs font-bold", stageClassName(stage))}>
                                        {stateCopy[stage.state]}
                                    </span>
                                    {stage.report_url && (
                                        <Link href={stage.report_url} className="text-sm font-bold text-blue-600 hover:text-blue-700">
                                            查看报告
                                        </Link>
                                    )}
                                </div>
                            </div>
                        </GlassCard>
                    ))}
                </section>

                {path.recommendation_reasons.length > 0 && (
                    <GlassCard className="p-6 bg-white/80">
                        <h2 className="text-xl font-black text-slate-900">推荐原因</h2>
                        <div className="mt-4 grid gap-3">
                            {path.recommendation_reasons.map((reason) => (
                                <div key={`${reason.source_report_id}-${reason.dimension_name}`} className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
                                    报告 {reason.source_report_id} · {reason.dimension_name} · {reason.score} 分
                                </div>
                            ))}
                        </div>
                    </GlassCard>
                )}
            </div>
        </main>
    );
}
