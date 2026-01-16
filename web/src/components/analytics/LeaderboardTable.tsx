"use client";

import { LeaderboardEntry } from "@/lib/api/types";
import { cn } from "@/lib/utils";

interface LeaderboardTableProps {
    data: LeaderboardEntry[];
}

export function LeaderboardTable({ data }: LeaderboardTableProps) {
    if (!data || data.length === 0) {
        return (
            <div className="h-72 flex items-center justify-center text-slate-400">
                暂无排行榜数据
            </div>
        );
    }

    // Rank medal emojis
    const getMedal = (rank: number) => {
        switch (rank) {
            case 1:
                return "🥇";
            case 2:
                return "🥈";
            case 3:
                return "🥉";
            default:
                return null;
        }
    };

    return (
        <div className="h-72 overflow-y-auto">
            <div className="space-y-2">
                {data.slice(0, 10).map((entry) => {
                    const medal = getMedal(entry.rank);

                    return (
                        <div
                            key={entry.user_id}
                            className={cn(
                                "flex items-center gap-4 p-3 rounded-xl transition-colors",
                                entry.rank <= 3 ? "bg-amber-50/50" : "bg-slate-50/50 hover:bg-slate-100/50"
                            )}
                        >
                            {/* Rank */}
                            <div className="w-10 text-center">
                                {medal ? (
                                    <span className="text-xl">{medal}</span>
                                ) : (
                                    <span className="text-sm font-bold text-slate-400">
                                        #{entry.rank}
                                    </span>
                                )}
                            </div>

                            {/* User Info */}
                            <div className="flex-1 min-w-0">
                                <p className="font-bold text-slate-900 truncate">
                                    {entry.user_name}
                                </p>
                                <p className="text-xs text-slate-500 truncate">
                                    {entry.department || "未分配部门"}
                                </p>
                            </div>

                            {/* Stats */}
                            <div className="text-right">
                                <p className="text-lg font-black text-slate-900">
                                    {entry.average_score.toFixed(1)}
                                </p>
                                <p className="text-xs text-slate-500">
                                    {entry.total_sessions} 次练习
                                </p>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* View More Hint */}
            {data.length > 10 && (
                <div className="text-center mt-4 text-sm text-slate-400">
                    共 {data.length} 位用户参与
                </div>
            )}
        </div>
    );
}
