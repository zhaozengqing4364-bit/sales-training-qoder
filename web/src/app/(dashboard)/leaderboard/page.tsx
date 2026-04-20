"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { ArrowRight, Loader2, Trophy, User, UsersRound } from "lucide-react";

type TimePeriod = "weekly" | "monthly" | "all_time";
type ScenarioFilter = "all" | "sales" | "presentation";
type LeaderboardMode = "score" | "improvement" | "issue_type";

type LeaderboardEntry = {
    rank: number;
    user_id: string;
    username: string;
    total_sessions: number;
    average_score: number;
    best_score: number;
    improvement_score?: number;
    first_score?: number;
    latest_score?: number;
    sample_size?: number;
    issue_type?: string | null;
};

type MyRank = {
    user_id?: string | null;
    rank: number | null;
    total_sessions: number;
    average_score: number;
    improvement_score?: number;
    latest_score?: number;
    sample_size?: number;
};

type NearbyRankInsight = {
    status: "ranked" | "not_enough_evidence" | "outside_current_page";
    title: string;
    description: string;
    nearbyEntries: LeaderboardEntry[];
};

type LeaderboardMeta = {
    evaluableSessions: number;
    notEvaluableSessions: number;
    eligibilityExplanation?: string;
    issueTypeBuckets: IssueTypeBucket[];
};

type IssueTypeBucket = {
    issue_type: string;
    count?: number;
    evaluable_sessions?: number;
};

const TIME_PERIOD_OPTIONS: Array<{ value: TimePeriod; label: string }> = [
    { value: "weekly", label: "本周" },
    { value: "monthly", label: "本月" },
    { value: "all_time", label: "总榜" },
];

const SCENARIO_OPTIONS: Array<{ value: ScenarioFilter; label: string }> = [
    { value: "all", label: "全部场景" },
    { value: "sales", label: "销售对练" },
    { value: "presentation", label: "PPT 演练" },
];

const LEADERBOARD_MODE_OPTIONS: Array<{ value: LeaderboardMode; label: string; shortLabel: string; description: string }> = [
    {
        value: "score",
        label: "综合分榜",
        shortLabel: "综合分",
        description: "按可评估训练均分排名，延续当前排行榜口径。",
    },
    {
        value: "improvement",
        label: "进步榜",
        shortLabel: "进步幅度",
        description: "按最近可评估训练相对最早可评估训练的提升幅度排名。",
    },
    {
        value: "issue_type",
        label: "同目标榜",
        shortLabel: "同目标",
        description: "选择一个主要训练问题后，只和同目标用户比较。",
    },
];

const ISSUE_TYPE_LABELS: Record<string, string> = {
    evidence_gap: "证据支撑",
    objection_handling_gap: "异议处理",
    next_step_gap: "下一步推进",
    value_translation_gap: "价值转译",
    main_capability_not_passed: "核心能力补强",
    continuous_expression: "连续表达",
    defense_under_followups: "追问防守",
    four_step_structure: "四步结构",
    no_blocking_issue: "暂无阻塞问题",
};

function getModeCopy(mode: LeaderboardMode) {
    return LEADERBOARD_MODE_OPTIONS.find((option) => option.value === mode) ?? LEADERBOARD_MODE_OPTIONS[0];
}

function formatIssueType(issueType: string): string {
    return ISSUE_TYPE_LABELS[issueType] ?? issueType
        .split("_")
        .filter(Boolean)
        .map((part) => part[0]?.toUpperCase() + part.slice(1))
        .join(" ");
}

function getRankMetricValue(mode: LeaderboardMode, item: LeaderboardEntry | MyRank): number {
    if (mode === "improvement") {
        return item.improvement_score ?? item.average_score;
    }
    return item.average_score;
}

function getRankMetricLabel(mode: LeaderboardMode): string {
    if (mode === "improvement") {
        return "进步";
    }
    return "均分";
}

function formatSignedScore(value: number): string {
    const rounded = Math.round(value);
    return `${rounded > 0 ? "+" : ""}${rounded}`;
}

function buildNearbyRankInsight(
    myRank: MyRank | null,
    entries: LeaderboardEntry[],
    leaderboardMode: LeaderboardMode,
): NearbyRankInsight {
    if (!myRank || myRank.rank === null || myRank.total_sessions <= 0) {
        return {
            status: "not_enough_evidence",
            title: "暂未进入我的附近排名",
            description: leaderboardMode === "improvement"
                ? "当前账号还没有至少 2 次可评估训练进入进步榜；继续完成有足够对话证据的训练后，会显示你的进步排名和邻近用户。"
                : "当前账号还没有足够的可评估训练进入当前榜单；完成一次有足够对话证据的训练后，会显示你的排名和邻近用户。",
            nearbyEntries: [],
        };
    }

    const myRankValue = myRank.rank;
    const myMetricValue = getRankMetricValue(leaderboardMode, myRank);
    const byRank = entries.filter((entry) => (
        Math.abs(entry.rank - myRankValue) <= 1
        && entry.user_id !== myRank.user_id
    ));
    const byScore = entries
        .filter((entry) => entry.user_id !== myRank.user_id)
        .map((entry) => ({
            entry,
            scoreDistance: Math.abs(getRankMetricValue(leaderboardMode, entry) - myMetricValue),
        }))
        .filter(({ scoreDistance }) => scoreDistance <= 2)
        .sort((left, right) => left.scoreDistance - right.scoreDistance || left.entry.rank - right.entry.rank)
        .map(({ entry }) => entry);
    const nearbyEntries = Array.from(new Map(
        [...byRank, ...byScore].map((entry) => [entry.user_id, entry]),
    ).values()).slice(0, 3);

    if (nearbyEntries.length === 0) {
        return {
            status: "outside_current_page",
            title: "我的附近排名暂不在本页范围",
            description: `你当前在${getModeCopy(leaderboardMode).shortLabel}榜排名 #${myRank.rank}，${getRankMetricLabel(leaderboardMode)} ${leaderboardMode === "improvement" ? formatSignedScore(myMetricValue) : Math.round(myMetricValue)}。本页还没有相邻名次用户；继续完成可评估训练后会刷新附近对比。`,
            nearbyEntries: [],
        };
    }

    return {
        status: "ranked",
        title: `我的附近排名 · ${getModeCopy(leaderboardMode).label}`,
        description: `基于当前${getModeCopy(leaderboardMode).label}中与你名次相邻或${getRankMetricLabel(leaderboardMode)}接近的用户生成；只使用已完成且可评估训练。`,
        nearbyEntries,
    };
}

function rankBadge(rank: number): string {
    if (rank === 1) return "🥇";
    if (rank === 2) return "🥈";
    if (rank === 3) return "🥉";
    return "🎯";
}

export default function LeaderboardPage() {
    const [timePeriod, setTimePeriod] = useState<TimePeriod>("weekly");
    const [scenarioFilter, setScenarioFilter] = useState<ScenarioFilter>("all");
    const [leaderboardMode, setLeaderboardMode] = useState<LeaderboardMode>("score");
    const [selectedIssueType, setSelectedIssueType] = useState<string | null>(null);
    const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
    const [myRank, setMyRank] = useState<MyRank | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [reloadVersion, setReloadVersion] = useState(0);
    const [leaderboardMeta, setLeaderboardMeta] = useState<LeaderboardMeta>({
        evaluableSessions: 0,
        notEvaluableSessions: 0,
        issueTypeBuckets: [],
    });

    useEffect(() => {
        let cancelled = false;

        const loadData = async () => {
            setIsLoading(true);
            const scenarioType =
                scenarioFilter === "all" ? undefined : scenarioFilter;
            const issueType = leaderboardMode === "issue_type" ? selectedIssueType ?? undefined : undefined;
            const leaderboardResult = await api.dashboard
                .getPublicLeaderboard({
                    scenario_type: scenarioType,
                    time_period: timePeriod,
                    leaderboard_mode: leaderboardMode,
                    issue_type: issueType,
                    include_me: true,
                    limit: 20,
                })
                .catch((error) => ({ error }));

            if (cancelled) return;

            if (leaderboardResult && "error" in leaderboardResult) {
                setEntries([]);
                setMyRank(null);
                setLeaderboardMeta({
                    evaluableSessions: 0,
                    notEvaluableSessions: 0,
                    issueTypeBuckets: [],
                });
                setLoadError(getApiErrorMessage(leaderboardResult.error));
                setIsLoading(false);
                return;
            }

            setLoadError(null);
            setEntries(leaderboardResult.entries || []);
            setLeaderboardMeta({
                evaluableSessions: leaderboardResult.evaluable_sessions ?? 0,
                notEvaluableSessions: leaderboardResult.not_evaluable_sessions ?? 0,
                eligibilityExplanation: leaderboardResult.eligibility?.explanation,
                issueTypeBuckets: leaderboardResult.issue_type_buckets ?? [],
            });

            if (leaderboardResult.my_rank) {
                setMyRank({
                    user_id: leaderboardResult.my_rank.user_id,
                    rank: leaderboardResult.my_rank.rank,
                    total_sessions: leaderboardResult.my_rank.total_sessions,
                    average_score: leaderboardResult.my_rank.average_score,
                    improvement_score: leaderboardResult.my_rank.improvement_score,
                    latest_score: leaderboardResult.my_rank.latest_score,
                    sample_size: leaderboardResult.my_rank.sample_size,
                });
                setIsLoading(false);
                return;
            }

            const fallbackMyRank = await api.dashboard
                .getMyRank({
                    scenario_type: scenarioType,
                    time_period: timePeriod,
                    leaderboard_mode: leaderboardMode,
                    issue_type: issueType,
                })
                .catch(() => null);

            if (cancelled) return;

            if (fallbackMyRank) {
                setMyRank({
                    user_id: fallbackMyRank.user_id,
                    rank: fallbackMyRank.rank,
                    total_sessions: fallbackMyRank.total_sessions,
                    average_score: fallbackMyRank.average_score,
                    improvement_score: fallbackMyRank.improvement_score,
                    latest_score: fallbackMyRank.latest_score,
                    sample_size: fallbackMyRank.sample_size,
                });
            } else {
                setMyRank(null);
            }

            setIsLoading(false);
        };

        loadData();

        return () => {
            cancelled = true;
        };
    }, [timePeriod, scenarioFilter, leaderboardMode, selectedIssueType, reloadVersion]);

    const topEntries = useMemo(() => entries.slice(0, 3), [entries]);
    const remainingEntries = useMemo(() => entries.slice(3), [entries]);
    const nearbyRankInsight = useMemo(
        () => buildNearbyRankInsight(myRank, entries, leaderboardMode),
        [entries, leaderboardMode, myRank],
    );
    const selectedModeCopy = getModeCopy(leaderboardMode);
    const emptyStateCopy = useMemo(() => {
        if (leaderboardMode === "improvement") {
            return {
                title: "进步榜样本不足",
                body: leaderboardMeta.eligibilityExplanation
                    ?? "进步榜至少需要 2 次可评估训练，证据不足或只有一次可评估训练的用户不会进入榜单。",
            };
        }

        if (leaderboardMode === "issue_type") {
            return {
                title: selectedIssueType ? "当前目标样本不足" : "先选择一个训练目标",
                body: selectedIssueType
                    ? `「${formatIssueType(selectedIssueType)}」当前还没有足够可评估训练进入同目标榜；完成同目标训练后会自动刷新。`
                    : "同目标榜不会随机造榜；请选择一个已有目标问题后，再查看同目标用户排名。",
            };
        }

        return {
            title: "暂无排行榜数据",
            body: "当前筛选范围还没有可评估训练进入榜单；至少完成一次有足够对话证据的训练后，均分和排名会自动刷新。",
        };
    }, [leaderboardMeta.eligibilityExplanation, leaderboardMode, selectedIssueType]);

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
            <header className="flex justify-between items-center gap-4 flex-wrap">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">排行榜</h1>
                    <p className="text-sm text-slate-500 mt-1">
                        均分与排名只纳入可评估的已完成训练，证据不足会话会单独记账，不会混入榜单。
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                        当前榜单纳入 {leaderboardMeta.evaluableSessions} 次可评估训练，{leaderboardMeta.notEvaluableSessions} 次证据不足训练未计入排名。
                    </p>
                </div>
                <div className="flex bg-white p-1 rounded-full shadow-sm border border-slate-100">
                    {TIME_PERIOD_OPTIONS.map((option) => (
                        <button
                            key={option.value}
                            onClick={() => setTimePeriod(option.value)}
                            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                                timePeriod === option.value
                                    ? "bg-slate-900 text-white shadow-md"
                                    : "text-slate-500 hover:bg-slate-50"
                            }`}
                        >
                            {option.label}
                        </button>
                    ))}
                </div>
            </header>

            <div className="flex bg-white p-1 rounded-full shadow-sm border border-slate-100 w-fit">
                {SCENARIO_OPTIONS.map((option) => (
                    <button
                        key={option.value}
                        onClick={() => setScenarioFilter(option.value)}
                        className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                            scenarioFilter === option.value
                                ? "bg-blue-600 text-white shadow-md"
                                : "text-slate-500 hover:bg-slate-50"
                        }`}
                    >
                        {option.label}
                    </button>
                ))}
            </div>

            <GlassCard className="p-4">
                <div className="flex flex-wrap items-center gap-2">
                    {LEADERBOARD_MODE_OPTIONS.map((option) => (
                        <button
                            key={option.value}
                            type="button"
                            onClick={() => {
                                setLeaderboardMode(option.value);
                                if (option.value !== "issue_type") {
                                    setSelectedIssueType(null);
                                }
                            }}
                            className={`rounded-full px-4 py-2 text-sm font-bold transition-colors ${
                                leaderboardMode === option.value
                                    ? "bg-slate-900 text-white shadow-md"
                                    : "bg-slate-50 text-slate-600 hover:bg-slate-100"
                            }`}
                        >
                            {option.label}
                        </button>
                    ))}
                </div>
                <p className="mt-3 text-sm text-slate-500">{selectedModeCopy.description}</p>
                {leaderboardMode === "issue_type" && (
                    <div className="mt-4">
                        <p className="text-xs font-semibold text-slate-500">可选训练目标</p>
                        {leaderboardMeta.issueTypeBuckets.length > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-2">
                                {leaderboardMeta.issueTypeBuckets.map((bucket) => (
                                    <button
                                        key={bucket.issue_type}
                                        type="button"
                                        onClick={() => setSelectedIssueType(bucket.issue_type)}
                                        className={`rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
                                            selectedIssueType === bucket.issue_type
                                                ? "border-blue-600 bg-blue-600 text-white"
                                                : "border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:bg-blue-50"
                                        }`}
                                    >
                                        {formatIssueType(bucket.issue_type)}
                                        <span className="ml-1 text-xs opacity-75">
                                            {bucket.evaluable_sessions ?? bucket.count ?? 0} 次
                                        </span>
                                    </button>
                                ))}
                            </div>
                        ) : (
                            <p className="mt-2 text-sm text-slate-500">
                                当前筛选范围还没有可选择的同目标分组；只有已完成且可评估，并带有主问题类型的训练会进入分组。
                            </p>
                        )}
                    </div>
                )}
            </GlassCard>

            {myRank && (
                <GlassCard className="p-4 flex items-center justify-between">
                    <div className="text-sm text-slate-500">我的排名 · {selectedModeCopy.label}</div>
                    <div className="flex items-center gap-4 text-sm">
                        <Badge variant="blue">#{myRank.rank ?? "--"}</Badge>
                        <span className="text-slate-700">{myRank.total_sessions} 次练习</span>
                        <span className="font-semibold text-slate-900">
                            {leaderboardMode === "improvement"
                                ? `进步 ${formatSignedScore(getRankMetricValue(leaderboardMode, myRank))}`
                                : `均分 ${Math.round(myRank.average_score || 0)}`}
                        </span>
                    </div>
                </GlassCard>
            )}

            {!isLoading && !loadError && (
                <GlassCard className="p-5 border border-blue-100 bg-blue-50/60">
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                        <div>
                            <p className="text-xs font-semibold text-blue-700">附近排名</p>
                            <h2 className="text-lg font-bold text-slate-900 mt-1">{nearbyRankInsight.title}</h2>
                            <p className="text-sm text-slate-600 mt-1 max-w-3xl">{nearbyRankInsight.description}</p>
                        </div>
                        {nearbyRankInsight.status !== "ranked" && (
                            <Link
                                href="/training"
                                className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-blue-700"
                            >
                                去训练大厅
                                <ArrowRight className="w-4 h-4" />
                            </Link>
                        )}
                    </div>

                    {nearbyRankInsight.nearbyEntries.length > 0 && (
                        <div className="mt-4">
                            <p className="mb-2 text-xs font-semibold text-blue-700">
                                {leaderboardMode === "improvement" ? "同进步幅度邻近用户" : "同分邻近用户"}
                            </p>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                {nearbyRankInsight.nearbyEntries.map((entry) => (
                                    <div key={entry.user_id} className="rounded-2xl border border-white/80 bg-white/85 p-4 shadow-sm">
                                        <div className="flex items-center justify-between gap-3">
                                            <div className="flex items-center gap-2 font-bold text-slate-900">
                                                <UsersRound className="w-4 h-4 text-blue-600" />
                                                {entry.username}
                                            </div>
                                            <Badge variant="blue" className="text-[11px]">#{entry.rank}</Badge>
                                        </div>
                                        <div className="mt-3 text-sm text-slate-600">
                                            {leaderboardMode === "improvement"
                                                ? `进步 ${formatSignedScore(getRankMetricValue(leaderboardMode, entry))} · 当前 ${Math.round(entry.latest_score ?? entry.average_score)} · ${entry.sample_size ?? entry.total_sessions} 次样本`
                                                : `均分 ${Math.round(entry.average_score)} · 最佳 ${Math.round(entry.best_score)} · ${entry.total_sessions} 次练习`}
                                        </div>
                                        <p className="mt-2 text-xs text-slate-500">
                                            与你{getRankMetricLabel(leaderboardMode)}差 {Math.abs(getRankMetricValue(leaderboardMode, entry) - (myRank ? getRankMetricValue(leaderboardMode, myRank) : getRankMetricValue(leaderboardMode, entry))).toFixed(1)} 分
                                        </p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </GlassCard>
            )}

            {isLoading ? (
                <GlassCard className="p-10 flex items-center justify-center text-slate-500 gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    正在加载排行榜...
                </GlassCard>
            ) : loadError ? (
                <GlassCard className="p-10 text-center text-amber-700 bg-amber-50 border border-amber-200">
                    <div>排行榜暂时无法加载：{loadError}</div>
                    <button
                        type="button"
                        onClick={() => setReloadVersion((version) => version + 1)}
                        className="mt-4 rounded-full border border-amber-300 bg-white px-4 py-2 text-sm font-bold text-amber-800 shadow-sm hover:bg-amber-100"
                    >
                        重试排行榜
                    </button>
                </GlassCard>
            ) : entries.length === 0 ? (
                <GlassCard className="p-10 text-center">
                    <p className="text-sm font-semibold text-slate-900">{emptyStateCopy.title}</p>
                    <p className="mt-2 text-sm text-slate-500">
                        {emptyStateCopy.body}
                    </p>
                    <div className="mt-5 flex justify-center">
                        <Link
                            href="/training"
                            className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-blue-700"
                        >
                            去训练大厅
                            <ArrowRight className="w-4 h-4" />
                        </Link>
                    </div>
                </GlassCard>
            ) : (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {topEntries.map((entry) => (
                            <GlassCard key={entry.user_id} className="p-6 text-center">
                                <div className="text-4xl mb-2">{rankBadge(entry.rank)}</div>
                                <div className="text-lg font-bold text-slate-900">{entry.username}</div>
                                <div className="text-3xl font-black text-blue-600 mt-2">
                                    {leaderboardMode === "improvement"
                                        ? formatSignedScore(getRankMetricValue(leaderboardMode, entry))
                                        : Math.round(entry.average_score)}
                                    <span className="text-sm font-normal text-slate-400 ml-1">
                                        {leaderboardMode === "improvement" ? "进步" : "分"}
                                    </span>
                                </div>
                                <div className="text-xs text-slate-400 mt-1">
                                    {leaderboardMode === "improvement"
                                        ? `当前 ${Math.round(entry.latest_score ?? entry.average_score)} · ${entry.sample_size ?? entry.total_sessions} 次样本`
                                        : `${entry.total_sessions} 次练习`}
                                </div>
                            </GlassCard>
                        ))}
                    </div>

                    <GlassCard className="p-0 overflow-hidden">
                        <div className="p-4 border-b border-slate-100 flex text-xs font-bold text-slate-400 uppercase tracking-widest bg-slate-50/50">
                            <div className="w-16 text-center">排名</div>
                            <div className="flex-1">用户</div>
                            <div className="w-24 text-center">{leaderboardMode === "improvement" ? "进步" : "平均分"}</div>
                            <div className="w-24 text-center hidden sm:block">{leaderboardMode === "improvement" ? "当前分" : "最佳分"}</div>
                            <div className="w-24 text-center hidden sm:block">{leaderboardMode === "improvement" ? "样本数" : "练习次数"}</div>
                        </div>
                        <div className="divide-y divide-slate-100">
                            {remainingEntries.map((entry) => (
                                <div key={entry.user_id} className="flex items-center p-4 hover:bg-slate-50 transition-colors">
                                    <div className="w-16 text-center font-bold text-slate-500">{entry.rank}</div>
                                    <div className="flex-1 flex items-center gap-3">
                                        <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center shrink-0">
                                            <User className="w-4 h-4 text-slate-500" />
                                        </div>
                                        <span className="font-medium text-slate-700 truncate">{entry.username}</span>
                                    </div>
                                    <div className="w-24 text-center font-bold text-slate-900">
                                        {leaderboardMode === "improvement"
                                            ? formatSignedScore(getRankMetricValue(leaderboardMode, entry))
                                            : Math.round(entry.average_score)}
                                    </div>
                                    <div className="w-24 text-center text-slate-500 hidden sm:block">
                                        {leaderboardMode === "improvement"
                                            ? Math.round(entry.latest_score ?? entry.average_score)
                                            : Math.round(entry.best_score)}
                                    </div>
                                    <div className="w-24 text-center text-slate-500 hidden sm:block">
                                        {leaderboardMode === "improvement"
                                            ? entry.sample_size ?? entry.total_sessions
                                            : entry.total_sessions}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </GlassCard>
                </>
            )}

            <div className="text-xs text-slate-400 flex items-center gap-2">
                <Trophy className="w-3 h-3" />
                若某次训练因证据不足暂不可评估，它会保留在训练记录里，但不会拉高或拉低排行榜均分。
            </div>
        </div>
    );
}
