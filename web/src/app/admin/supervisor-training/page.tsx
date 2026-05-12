"use client";

import { useEffect, useState } from "react";
import {
    BarChart3,
    Clock,
    Filter,
    RefreshCw,
    Target,
    X,
} from "lucide-react";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    TeamInsightsResponse,
    TeamInsightsLearnerDetail,
} from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { debug } from "@/lib/debug";

const READINESS_LABELS: Record<string, string> = {
    approved: "已批准",
    ready_for_trial: "可试用",
    shadow_only: "仅观摩",
    not_ready: "未就绪",
};

const READINESS_COLORS: Record<string, string> = {
    approved: "bg-emerald-100 text-emerald-800",
    ready_for_trial: "bg-blue-100 text-blue-800",
    shadow_only: "bg-amber-100 text-amber-800",
    not_ready: "bg-red-100 text-red-800",
};

function formatScore(score: number | null): string {
    if (score === null || score === undefined) return "暂无数据";
    return String(score);
}

function formatReadiness(status: string | null): string {
    if (!status) return "证据不足";
    return READINESS_LABELS[status] ?? status;
}

export default function SupervisorTrainingPage() {
    const [data, setData] = useState<TeamInsightsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [reloadToken, setReloadToken] = useState(0);

    const [scenarioFilter, setScenarioFilter] = useState("");
    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");

    const [selectedLearner, setSelectedLearner] = useState<string | null>(null);
    const [detailData, setDetailData] = useState<TeamInsightsLearnerDetail | null>(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [detailError, setDetailError] = useState<string | null>(null);

    function buildParams() {
        const params: Record<string, string> = {};
        if (scenarioFilter.trim()) params.scenario_type = scenarioFilter.trim();
        if (dateFrom.trim()) params.date_from = dateFrom.trim();
        if (dateTo.trim()) params.date_to = dateTo.trim();
        return params;
    }

    async function loadInsights() {
        setLoading(true);
        setError(null);
        try {
            const params = buildParams();
            const result = await api.supervisor.getTeamInsights(
                Object.keys(params).length > 0 ? params : undefined,
            );
            setData(result);
        } catch (err) {
            setError(getApiErrorMessage(err));
            debug.warn("[SupervisorTrainingPage] failed to load", { error: err });
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        void loadInsights();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [reloadToken]);

    function handleRefresh() {
        setReloadToken((t) => t + 1);
    }

    function handleFilterApply() {
        setReloadToken((t) => t + 1);
    }

    async function loadLearnerDetail(learnerId: string) {
        setSelectedLearner(learnerId);
        setDetailLoading(true);
        setDetailError(null);
        setDetailData(null);
        try {
            const params = buildParams();
            const result = await api.supervisor.getLearnerDetail(
                learnerId,
                Object.keys(params).length > 0 ? params : undefined,
            );
            setDetailData(result);
        } catch (err) {
            setDetailError(getApiErrorMessage(err));
            debug.warn("[SupervisorTrainingPage] failed to load detail", { error: err });
        } finally {
            setDetailLoading(false);
        }
    }

    function closeDetail() {
        setSelectedLearner(null);
        setDetailData(null);
        setDetailError(null);
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-black text-slate-900">
                    主管训练管理中心
                </h1>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRefresh}
                    disabled={loading}
                >
                    <RefreshCw className="mr-1 h-4 w-4" />
                    刷新
                </Button>
            </div>

            <GlassCard className="space-y-4 p-4">
                <div className="flex flex-wrap items-end gap-3">
                    <div className="flex-1 min-w-[120px]">
                        <label className="mb-1 block text-xs font-semibold text-slate-500">
                            场景类型
                        </label>
                        <Input
                            placeholder="场景类型"
                            value={scenarioFilter}
                            onChange={(e) => setScenarioFilter(e.target.value)}
                        />
                    </div>
                    <div className="flex-1 min-w-[120px]">
                        <label className="mb-1 block text-xs font-semibold text-slate-500">
                            开始日期
                        </label>
                        <Input
                            placeholder="开始日期"
                            value={dateFrom}
                            onChange={(e) => setDateFrom(e.target.value)}
                        />
                    </div>
                    <div className="flex-1 min-w-[120px]">
                        <label className="mb-1 block text-xs font-semibold text-slate-500">
                            结束日期
                        </label>
                        <Input
                            placeholder="结束日期"
                            value={dateTo}
                            onChange={(e) => setDateTo(e.target.value)}
                        />
                    </div>
                    <Button size="sm" onClick={handleFilterApply}>
                        <Filter className="mr-1 h-4 w-4" />
                        筛选
                    </Button>
                </div>
            </GlassCard>

            {loading && (
                <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-center text-slate-600">
                    正在加载主管训练数据...
                </div>
            )}

            {error && !loading && (
                <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8 text-center">
                    <p className="text-sm text-amber-800">{error}</p>
                    <Button onClick={handleRefresh}>重试加载</Button>
                </GlassCard>
            )}

            {!loading && !error && data && (
                data.learners.length === 0 &&
                data.retraining_candidates.length === 0 ? (
                    <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-center text-slate-500">
                        暂无团队训练数据
                        {data.completion.completion_rate === 0 && (
                            <span className="ml-2 text-2xl font-bold text-slate-300">0%</span>
                        )}
                    </div>
                ) : null
            )}

            {!loading && !error && data && data.learners.length > 0 && (
                <>
                    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
                        <CompletionCard completion={data.completion} />
                        <WeaknessCard weaknesses={data.top_weaknesses} />
                        <ReadinessCard readiness={data.readiness} onSelectLearner={(id) => void loadLearnerDetail(id)} />
                        <RetrainingCard candidates={data.retraining_candidates} />
                    </div>

                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                        <TopIssuesCard issues={data.top3_common_issues} />
                        <LearnerListCard
                            learners={data.learners}
                            onSelectLearner={(id) => void loadLearnerDetail(id)}
                        />
                    </div>

                    {selectedLearner && (
                        <LearnerDetailPanel
                            detail={detailData}
                            loading={detailLoading}
                            error={detailError}
                            onClose={closeDetail}
                        />
                    )}
                </>
            )}
        </div>
    );
}

function CompletionCard({ completion }: { completion: TeamInsightsResponse["completion"] }) {
    const rate = Math.round(completion.completion_rate);
    return (
        <GlassCard className="p-5">
            <div className="flex items-center gap-2 text-slate-500">
                <Target className="h-4 w-4" />
                <span className="text-xs font-semibold uppercase">团队训练完成率</span>
            </div>
            <div className="mt-3">
                <span className="text-3xl font-black text-slate-900">{rate}%</span>
            </div>
            <div className="mt-2 text-sm text-slate-500">
                <span className="font-bold text-slate-700">{completion.completed_tasks}</span>
                {" / "}
                <span>{completion.total_tasks}</span>
                <span className="ml-2">已完成</span>
            </div>
        </GlassCard>
    );
}

function WeaknessCard({ weaknesses }: { weaknesses: TeamInsightsResponse["top_weaknesses"] }) {
    return (
        <GlassCard className="p-5">
            <div className="flex items-center gap-2 text-slate-500">
                <BarChart3 className="h-4 w-4" />
                <span className="text-xs font-semibold uppercase">团队弱项维度</span>
            </div>
            <div className="mt-3 space-y-1.5">
                {weaknesses.length === 0 && (
                    <p className="text-sm text-slate-400">暂无数据</p>
                )}
                {weaknesses.map((w) => (
                    <div key={w.dimension} className="flex items-center justify-between text-sm">
                        <span className="text-slate-700">{w.dimension}</span>
                        <span className="tabular-nums text-slate-500">
                            {formatScore(w.average_score)}
                        </span>
                    </div>
                ))}
            </div>
        </GlassCard>
    );
}

function ReadinessCard({
    readiness,
    onSelectLearner,
}: {
    readiness: TeamInsightsResponse["readiness"];
    onSelectLearner: (id: string) => void;
}) {
    return (
        <GlassCard className="p-5">
            <div className="flex items-center gap-2 text-slate-500">
                <Clock className="h-4 w-4" />
                <span className="text-xs font-semibold uppercase">准备状态管道</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
                {Object.entries(readiness.by_status).map(([status, count]) => (
                    <Badge key={status} variant="secondary" className={READINESS_COLORS[status]}>
                        {formatReadiness(status)} {count}
                    </Badge>
                ))}
            </div>
            {readiness.learners.length > 0 && (
                <div className="mt-2 space-y-1">
                    {readiness.learners.map((l) => (
                        <button
                            key={l.learner_id}
                            type="button"
                            onClick={() => onSelectLearner(l.learner_id)}
                            className="block w-full text-left text-sm text-slate-600 hover:text-blue-600"
                        >
                            {l.learner_name ?? l.learner_id}
                        </button>
                    ))}
                </div>
            )}
        </GlassCard>
    );
}

function RetrainingCard({ candidates }: { candidates: TeamInsightsResponse["retraining_candidates"] }) {
    return (
        <GlassCard className="p-5">
            <div className="flex items-center gap-2 text-slate-500">
                <Clock className="h-4 w-4" />
                <span className="text-xs font-semibold uppercase">待复训学员</span>
            </div>
            <div className="mt-3 space-y-2">
                {candidates.length === 0 && (
                    <p className="text-sm text-slate-400">暂无数据</p>
                )}
                {candidates.map((c) => (
                    <div key={c.learner_id} className="flex items-center justify-between text-sm">
                        <span className="text-slate-700">
                            {c.learner_name ?? c.learner_id}
                        </span>
                        {c.reason && (
                            <span className="text-xs text-amber-600">{c.reason}</span>
                        )}
                    </div>
                ))}
            </div>
        </GlassCard>
    );
}

function TopIssuesCard({ issues }: { issues: TeamInsightsResponse["top3_common_issues"] }) {
    return (
        <GlassCard className="p-5">
            <div className="flex items-center gap-2 text-slate-500">
                <BarChart3 className="h-4 w-4" />
                <span className="text-xs font-semibold uppercase">Top3 共性问题</span>
            </div>
            <div className="mt-3 space-y-3">
                {issues.length === 0 && (
                    <p className="text-sm text-slate-400">暂无数据</p>
                )}
                {issues.map((issue, idx) => (
                    <div key={issue.issue} className="flex items-start gap-3">
                        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white">
                            {idx + 1}
                        </span>
                        <div>
                            <p className="text-sm font-bold text-slate-800">{issue.issue}</p>
                            <p className="text-xs text-slate-500">
                                {issue.dimension ?? "通用"}
                                {" · "}
                                {issue.count} 名学员
                            </p>
                        </div>
                    </div>
                ))}
            </div>
        </GlassCard>
    );
}

function LearnerListCard({
    learners,
    onSelectLearner,
}: {
    learners: TeamInsightsResponse["learners"];
    onSelectLearner: (id: string) => void;
}) {
    return (
        <GlassCard className="p-5">
            <div className="flex items-center gap-2 text-slate-500">
                <Target className="h-4 w-4" />
                <span className="text-xs font-semibold uppercase">学员列表</span>
            </div>
            <div className="mt-3 space-y-2">
                {learners.length === 0 && (
                    <p className="text-sm text-slate-400">暂无学员数据</p>
                )}
                {learners.map((l) => (
                    <button
                        key={l.learner_id}
                        type="button"
                        onClick={() => onSelectLearner(l.learner_id)}
                        className="flex w-full items-center justify-between rounded-lg p-2 text-left hover:bg-slate-50"
                    >
                        <div>
                            <p className="text-sm font-bold text-slate-800">
                                {l.learner_name ?? l.learner_id}
                            </p>
                            <p className="text-xs text-slate-500">
                                {l.completion.completed_tasks}/{l.completion.total_tasks} 完成
                                {" · "}
                                {formatReadiness(l.readiness_status)}
                            </p>
                        </div>
                        <div className="text-right">
                            <p className="text-sm font-bold tabular-nums text-slate-700">
                                {formatScore(l.latest_score)}
                            </p>
                        </div>
                    </button>
                ))}
            </div>
        </GlassCard>
    );
}

function LearnerDetailPanel({
    detail,
    loading,
    error,
    onClose,
}: {
    detail: TeamInsightsLearnerDetail | null;
    loading: boolean;
    error: string | null;
    onClose: () => void;
}) {
    return (
        <GlassCard className="relative space-y-4 p-6">
            <div className="flex items-center justify-between">
                <h2 className="text-lg font-black text-slate-900">学员详情</h2>
                <Button variant="ghost" size="sm" onClick={onClose}>
                    <X className="mr-1 h-4 w-4" />
                    关闭
                </Button>
            </div>

            {loading && (
                <p className="py-4 text-center text-sm text-slate-500">正在加载学员详情...</p>
            )}

            {error && !loading && (
                <div className="rounded-lg bg-amber-50 p-4 text-sm text-amber-800">
                    {error}
                </div>
            )}

            {!loading && !error && detail && (
                <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                            <span className="text-slate-500">姓名</span>
                            <p className="font-bold text-slate-800">
                                {detail.learner_name ?? detail.learner_id}
                            </p>
                        </div>
                        <div>
                            <span className="text-slate-500">邮箱</span>
                            <p className="text-slate-700">
                                {detail.learner_email ?? "暂无数据"}
                            </p>
                        </div>
                        <div>
                            <span className="text-slate-500">最新评分</span>
                            <p className="font-bold tabular-nums text-slate-800">
                                {formatScore(detail.latest_score)}
                            </p>
                        </div>
                        <div>
                            <span className="text-slate-500">准备状态</span>
                            <p className="text-slate-700">
                                {formatReadiness(detail.readiness_status)}
                            </p>
                        </div>
                    </div>

                    {detail.training_tasks.length > 0 && (
                        <div>
                            <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500">
                                训练任务
                            </h3>
                            <div className="space-y-1.5">
                                {detail.training_tasks.map((t) => (
                                    <div
                                        key={t.task_id}
                                        className="flex items-center justify-between rounded-lg bg-slate-50 p-2 text-sm"
                                    >
                                        <span className="text-slate-700">{t.title}</span>
                                        <Badge variant="secondary" className="text-xs">
                                            {t.status}
                                        </Badge>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {detail.common_issues.length > 0 && (
                        <div>
                            <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500">
                                共性问题
                            </h3>
                            <div className="space-y-1">
                                {detail.common_issues.map((ci) => (
                                    <div key={ci.issue} className="flex items-center justify-between text-sm">
                                        <span className="text-slate-700">{ci.issue}</span>
                                        <span className="text-xs text-slate-400">{ci.count} 次</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </GlassCard>
    );
}
