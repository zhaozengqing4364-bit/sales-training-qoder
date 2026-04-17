"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { Loader2, Trophy, User } from "lucide-react";

type TimePeriod = "weekly" | "monthly" | "all_time";
type ScenarioFilter = "all" | "sales" | "presentation";

type LeaderboardEntry = {
    rank: number;
    user_id: string;
    username: string;
    total_sessions: number;
    average_score: number;
    best_score: number;
};

type MyRank = {
    rank: number | null;
    total_sessions: number;
    average_score: number;
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

function rankBadge(rank: number): string {
    if (rank === 1) return "🥇";
    if (rank === 2) return "🥈";
    if (rank === 3) return "🥉";
    return "🎯";
}

export default function LeaderboardPage() {
    const [timePeriod, setTimePeriod] = useState<TimePeriod>("weekly");
    const [scenarioFilter, setScenarioFilter] = useState<ScenarioFilter>("all");
    const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
    const [myRank, setMyRank] = useState<MyRank | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [reloadVersion, setReloadVersion] = useState(0);

    useEffect(() => {
        let cancelled = false;

        const loadData = async () => {
            setIsLoading(true);
            const scenarioType =
                scenarioFilter === "all" ? undefined : scenarioFilter;
            const leaderboardResult = await api.dashboard
                .getPublicLeaderboard({
                    scenario_type: scenarioType,
                    time_period: timePeriod,
                    include_me: true,
                    limit: 20,
                })
                .catch((error) => ({ error }));

            if (cancelled) return;

            if (leaderboardResult && "error" in leaderboardResult) {
                setEntries([]);
                setMyRank(null);
                setLoadError(getApiErrorMessage(leaderboardResult.error));
                setIsLoading(false);
                return;
            }

            setLoadError(null);
            setEntries(leaderboardResult.entries || []);

            if (leaderboardResult.my_rank) {
                setMyRank({
                    rank: leaderboardResult.my_rank.rank,
                    total_sessions: leaderboardResult.my_rank.total_sessions,
                    average_score: leaderboardResult.my_rank.average_score,
                });
                setIsLoading(false);
                return;
            }

            const fallbackMyRank = await api.dashboard
                .getMyRank({
                    scenario_type: scenarioType,
                    time_period: timePeriod,
                })
                .catch(() => null);

            if (cancelled) return;

            if (fallbackMyRank) {
                setMyRank({
                    rank: fallbackMyRank.rank,
                    total_sessions: fallbackMyRank.total_sessions,
                    average_score: fallbackMyRank.average_score,
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
    }, [timePeriod, scenarioFilter, reloadVersion]);

    const topEntries = useMemo(() => entries.slice(0, 3), [entries]);
    const remainingEntries = useMemo(() => entries.slice(3), [entries]);

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
            <header className="flex justify-between items-center gap-4 flex-wrap">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">排行榜</h1>
                    <p className="text-sm text-slate-500 mt-1">
                        均分与排名只纳入可评估的已完成训练，证据不足会话会单独记账，不会混入榜单。
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

            {myRank && (
                <GlassCard className="p-4 flex items-center justify-between">
                    <div className="text-sm text-slate-500">我的排名</div>
                    <div className="flex items-center gap-4 text-sm">
                        <Badge variant="blue">#{myRank.rank ?? "--"}</Badge>
                        <span className="text-slate-700">{myRank.total_sessions} 次练习</span>
                        <span className="font-semibold text-slate-900">均分 {Math.round(myRank.average_score || 0)}</span>
                    </div>
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
                <GlassCard className="p-10 text-center text-slate-500">暂无排行榜数据，完成可评估练习后会自动上榜。</GlassCard>
            ) : (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {topEntries.map((entry) => (
                            <GlassCard key={entry.user_id} className="p-6 text-center">
                                <div className="text-4xl mb-2">{rankBadge(entry.rank)}</div>
                                <div className="text-lg font-bold text-slate-900">{entry.username}</div>
                                <div className="text-3xl font-black text-blue-600 mt-2">
                                    {Math.round(entry.average_score)}
                                    <span className="text-sm font-normal text-slate-400 ml-1">分</span>
                                </div>
                                <div className="text-xs text-slate-400 mt-1">{entry.total_sessions} 次练习</div>
                            </GlassCard>
                        ))}
                    </div>

                    <GlassCard className="p-0 overflow-hidden">
                        <div className="p-4 border-b border-slate-100 flex text-xs font-bold text-slate-400 uppercase tracking-widest bg-slate-50/50">
                            <div className="w-16 text-center">排名</div>
                            <div className="flex-1">用户</div>
                            <div className="w-24 text-center">平均分</div>
                            <div className="w-24 text-center hidden sm:block">最佳分</div>
                            <div className="w-24 text-center hidden sm:block">练习次数</div>
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
                                    <div className="w-24 text-center font-bold text-slate-900">{Math.round(entry.average_score)}</div>
                                    <div className="w-24 text-center text-slate-500 hidden sm:block">{Math.round(entry.best_score)}</div>
                                    <div className="w-24 text-center text-slate-500 hidden sm:block">{entry.total_sessions}</div>
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
